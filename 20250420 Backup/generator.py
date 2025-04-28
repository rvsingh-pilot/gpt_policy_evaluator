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


def fetch_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        content_blocks = []

        # Grab headings and paragraphs near them
        for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
            text = header.get_text(strip=True)
            next_p = header.find_next_sibling('p')
            if next_p:
                text += " " + next_p.get_text(strip=True)
            content_blocks.append(text)

        focused_content = "\n\n".join(content_blocks)[:4000]  # GPT input token-safe
        return focused_content

    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None


def search_dmv_url(state):
    print(f"Searching DuckDuckGo for {state} DMV...")
    with DDGS() as ddgs:
        results = ddgs.text(f"{state} DMV site:.gov license plate transfer", max_results=5)

    for r in results:
        url = r['href']
        if is_valid_url(url):
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

Only respond with one of the two exact phrases.
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

        if not is_valid_url(url):
            print(f"→ Result: INVALID or UNREACHABLE URL")
            continue

        content = fetch_content(url)
        if not content:
            print(f"→ Result: FAILED TO FETCH CONTENT")
            continue

        print(f"→ Result: SUCCESS - Content fetched from {url}")
        found_content = content
        used_url = url
        break

    if not found_content:
        print(f"No valid or usable URL found for {state} in dmv_urls.json.")
        print(f"Trying manual_overrides.json...")
        url = manual_overrides.get(state)

        if url and is_valid_url(url):
            content = fetch_content(url)
            if content:
                print(f"→ Manual override succeeded for {state} with {url}")
                found_content = content
                used_url = url

    if not found_content:
        print(f"Trying DuckDuckGo search for {state}...")
        url = search_dmv_url(state)
        if url and is_valid_url(url):
            content = fetch_content(url)
            if content:
                print(f"→ DuckDuckGo fallback succeeded for {state} with {url}")
                found_content = content
                used_url = url

    if not found_content:
        print(f"❌ No valid content found for {state}. Flagging for manual validation.")
        return {
            "state": state,
            "policy_summary": "Policy not found - manual validation needed",
            "dmv_excerpt": "Manual validation required",
            "source_url": "Not found",
            "plate_retention_policy": "Manual validation required"
        }

    prompt = f"""
        You are an API system that must ONLY return valid JSON.

        Given this DMV content below for {state}, please assess whether the content
        identifies whether the license plate should stay with the seller (and for example transferred to another vehicle owned by the
        seller) or if the license plate must be transferred to the buyer when the vehicle is sold.

        If the content implies a rule but does not directly say it, infer the likely policy and explain your reasoning.

        Extract:
        1. Concise policy summary clearly identifying whether the plate stays with the owner or transferred with the vehicle
        2. Concise direct quote from content if available
        3. Provide the source URL

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
        "source_url": "{used_url}"
        }}
        """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    gpt_response = response.choices[0].message.content.strip()
    print(f"GPT raw output for {state}:\n{gpt_response}")

    if "```json" in gpt_response:
        gpt_response = gpt_response.split("```json")[1].split("```")[0].strip()

    policy_data = json.loads(gpt_response)

    try:
        classification = classify_plate_policy(state, policy_data['policy_summary'])
        policy_data["plate_retention_policy"] = classification
        return policy_data
    except Exception as e:
        print(f"Failed to parse GPT output for {state}: {e}")
    return {
            "state": state,
            "policy_summary": "Policy not found - manual validation needed",
            "dmv_excerpt": "Manual validation required",
            "source_url": used_url if used_url else "Not found",
            "plate_retention_policy": "Manual validation required"
        }


def save_manual_overrides():
    with open('manual_overrides.json', 'w') as f:
        json.dump(manual_overrides, f, indent=2)
    log_file.close()
