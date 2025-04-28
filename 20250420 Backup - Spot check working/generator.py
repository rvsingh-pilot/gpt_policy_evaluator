import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import os
import json
from dotenv import load_dotenv
import tldextract
from duckduckgo_search import DDGS

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

with open('dmv_urls.json') as f:
    dmv_urls = json.load(f)

manual_overrides = {}
if os.path.exists('manual_overrides.json'):
    with open('manual_overrides.json') as f:
        manual_overrides = json.load(f)

log_file = open('manual_overrides_log.txt', 'a')


def is_valid_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if r.status_code in [200, 301, 302]:
            return True
        else:
            print(f"→ URL responded with status code {r.status_code}")
            return False
    except Exception as e:
        print(f"→ Exception checking URL: {e}")
        return False
    
def is_official_dmv_url(url):
    ext = tldextract.extract(url)
    domain = ext.domain
    suffix = ext.suffix

    is_gov = suffix.endswith("gov")
    is_us_state = suffix.endswith("us")

    state_code_match = any(state.lower().replace(" ", "") in url.lower() for state in dmv_urls.keys())

    return is_gov or (is_us_state and state_code_match)


def fetch_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        content_blocks = set()

        # 1. Collect h1–h4 + first <p> sibling
        for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
            block = header.get_text(strip=True)
            next_p = header.find_next_sibling('p')
            if next_p:
                block += " " + next_p.get_text(strip=True)
            content_blocks.add(block.strip())

        # 2. Collect all standalone <p> tags (maximizes recall)
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                content_blocks.add(text.strip())

        # 3. Assemble and truncate
        full_text = "\n\n".join(content_blocks)
        ##return full_text[:4000]  # Stay within GPT prompt token limits
        return full_text  # Send full content (as long as your GPT model supports it)


    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None



def search_dmv_url(state):
    print(f"Searching DuckDuckGo for {state} DMV...")
    with DDGS() as ddgs:
        ##results = ddgs.text(f"{state} DMV site:.gov license plate transfer", max_results=5)
        ##results = ddgs.text(
        ##    f"{state} DMV site:.gov OR site:{state.lower()}.us OR site:.{state.lower()} license plate transfer", max_results=5
        ##)
        query = f"What should I do with the license plates when I sell a vehicle in {state} site:.gov OR site:{state.lower()}.us OR site:.{state.lower()}"
        print(f"🔍 DuckDuckGo query: {query}")
        results = ddgs.text(query, max_results=5)

    for r in results:
        url = r['href']
        if is_valid_url(url) and is_official_dmv_url(url):
            print(f"→ DuckDuckGo found: {url}")
            manual_overrides[state] = url
            log_file.write(f"[DuckDuckGo] {state}: {url}\n")
            return url
    return None


def classify_plate_policy(state, summary):
    prompt = f"""
        Given this DMV plate policy summary for {state}:

        "{summary}"

        Classify the policy into one of:
        - Plate stays with vehicle
        - Plate stays with seller
        - Plate must be surrendered to DMV

        Only respond with one of the three exact phrases.
        """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def generate_policy_data(state):
    urls = dmv_urls.get(state, [])

    found_content = None
    used_url = None

    for url in urls:
        print(f"Attempting {state} URL from dmv_urls.json: {url}")

        if not (is_valid_url(url) and is_official_dmv_url(url)):
            print(f"→ Result: INVALID or UNOFFICIAL  URL")
            continue

        content = fetch_content(url)
        if not content:
            print(f"→ Result: FAILED TO FETCH CONTENT")
            continue

        print(f"→ Result: SUCCESS - Content fetched from {url}")
        found_content = content
        used_url = url
        break
        print(f"✅ Used canonical URL from dmv_urls.json for {state}: {used_url}")


    if not found_content:
        print(f"No valid or usable URL found for {state} in dmv_urls.json.")

        # Try DuckDuckGo fallback → must be official
        print(f"Trying DuckDuckGo search for {state}...")
        url = search_dmv_url(state)
        print(f"🔍 DuckDuckGo query: {state} DMV site:.gov OR site:{state.lower()}.us OR site:.{state.lower()} license plate transfer")
        if url and is_valid_url(url) and is_official_dmv_url(url):
            content = fetch_content(url)
            if content:
                print(f"→ DuckDuckGo fallback succeeded for {state} with {url}")
                print(f"🔍 Used DuckDuckGo fallback URL for {state}: {url}")
                found_content = content
                used_url = url

    # As LAST resort, allow manual override even if not official
    if not found_content:
        print(f"Trying manual_overrides.json for {state}...")
        url = manual_overrides.get(state)
        if url and is_valid_url(url):  # ✅ NOTICE: NO is_official_dmv_url() CHECK HERE
            content = fetch_content(url)
            if content:
                print(f"→ Manual override used for {state} with {url}")
                if not is_official_dmv_url(url):
                    print(f"⚠️ Used NON-OFFICIAL manual override for {state}: {url}")
                else:
                    print(f"🛠 Used official manual override for {state}: {url}")
                used_url = url

##    if not found_content:
##        print(f"No valid or usable URL found for {state} in dmv_urls.json.")
##        print(f"Trying manual_overrides.json...")
##        url = manual_overrides.get(state)

##        if url and is_valid_url(url) and is_official_dmv_url(url):
##            content = fetch_content(url)
##            if content:
##                print(f"→ Manual override succeeded for {state} with {url}")
##                found_content = content
##                used_url = url

##    if not found_content:
##        print(f"Trying DuckDuckGo search for {state}...")
##        url = search_dmv_url(state)
##        if url and is_valid_url(url) and is_official_dmv_url(url):
##            content = fetch_content(url)
##            if content:
##                print(f"→ DuckDuckGo fallback succeeded for {state} with {url}")
##                found_content = content
##                used_url = url


    if not found_content:
        print(f"❌ No valid content found for {state}. Flagging for manual validation.")
        return {
            "state": state,
            "policy_summary": "Policy not found - manual validation needed",
            "dmv_excerpt": "Manual validation required",
            "source_url": "Not found",
            "plate_retention_policy": "Manual validation required"
        }

    print("\n📄 Content provided to GPT for evaluation:\n")
    print(f"📏 Content length for {state}: {len(found_content)} characters")
    print(found_content[:1000])  # Adjust length as needed (1000 is a good starting point)

    prompt = f"""
        You are an API system that must ONLY return valid JSON.

        Given this DMV content below for {state}, please assess whether the content
        identifies whether the license plate should stay with the seller (and for example transferred to another vehicle owned by the
        seller), if the license plate must stay with the same vehicle when the vehicle is sold, or if the license plate must be surrendered to the DMV. 
        If the content explicitly states a policy, summarize it in a concise manner.
        If the content implies a rule but does not directly say it, infer the likely policy and explain your reasoning.
        If the content is vague or indirect, summarize the likely policy based on the content.
        If the content is not relevant to license plates, return "Policy not found - manual validation needed"..
        Disregard content that refers to personalized plates as these are edge cases not relevant to the general plate retention policy.

        Extract:
        1. Concise policy summary clearly identifying whether the plate stays with the owner or transferred with the vehicle
        2. A **direct quote** from the content (not a heading), that clearly supports the policy summary. Only include the specific sentence(s) that state or strongly imply the policy. Do not include section titles or headers. 
            These phrases are strong signals of the plate policy. If such a phrase is found, prioritize quoting it over any vague or indirect references.
            - "plates remain with the vehicle"
            - "plates must be returned to the DMV"
            - "plates stay with the seller"
            - "plates must be surrendered"
            - "remove your license plates before selling"
            These phrases often indicate the license plate retention policy. 
            If multiple sentences communicate the same rule, return only the most concise and direct one.
        3. A field called "highlighted_quote": return the same quote as "dmv_excerpt" but bold the 1–3 word phrase that most clearly supports the policy assessment using Markdown (e.g., **remain with the vehicle**). Do not bold entire sentences — only the keywords or phrases that indicate the retention policy.
        4. Provide the source URL

        Content:
        \"\"\"
        {found_content}
        \"\"\"

        Output only valid JSON like:

        ```json
        {{
        "state": "{state}",
        "policy_summary": "",
        "dmv_excerpt": "",
        "highlighted_quote": "",
        "source_url": "{used_url}"
        }}
        """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    gpt_response = response.choices[0].message.content.strip()
    print(f"GPT raw output for {state}:\n{gpt_response}")


    try:
        if "```json" in gpt_response:
            gpt_response = gpt_response.split("```json")[1].split("```")[0].strip()

        policy_data = json.loads(gpt_response)

        classification = classify_plate_policy(state, policy_data['policy_summary'])
        policy_data["plate_retention_policy"] = classification
        return policy_data
    except Exception as e:
        print(f"Failed to parse GPT output for {state}: {e}")
    return {
            "state": state,
            "policy_summary": "Policy not found - manual validation needed",
            "dmv_excerpt": "Manual validation required",
            "source_url": used_url or url or "Not found",
            "plate_retention_policy": "Manual validation required"
        }


def save_manual_overrides():
    with open('manual_overrides.json', 'w') as f:
        json.dump(manual_overrides, f, indent=2)
    log_file.close()
