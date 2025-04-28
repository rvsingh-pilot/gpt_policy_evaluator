import requests
from requests.exceptions import Timeout, ConnectionError
from urllib3.exceptions import ProtocolError
from http.client import RemoteDisconnected
from bs4 import BeautifulSoup
import openai
from openai import OpenAI
import os
import fitz  # PyMuPDF
import json
from dotenv import load_dotenv
import tldextract
from duckduckgo_search import DDGS
import time
from playwright.sync_api import sync_playwright
import undetected_chromedriver as uc


MAX_RETRIES = 5 #Max retries for OpenAPI call
RETRY_DELAY = 30  #How long to wait if we get a rate limit error
MAX_CHARS = 20000 #Max characters for OpenAPI call

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

with open('dmv_urls.json') as f:
    dmv_urls = json.load(f)

manual_overrides = {}
if os.path.exists('manual_overrides.json'):
    with open('manual_overrides.json') as f:
        manual_overrides = json.load(f)

log_file = open('manual_overrides_log.txt', 'a')


def fetch_content_with_undetected_chromedriver(url, retries=3):
    print(f"🌐 Fetching using Undetected ChromeDriver: {url}")
    for attempt in range(retries):
        try:
            options = uc.ChromeOptions()
            options.headless = True
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("start-maximized")
            options.add_argument("disable-infobars")
            options.add_argument("--disable-extensions")

            driver = uc.Chrome(options=options)
            driver.get(url)
            time.sleep(5)

            page_source = driver.page_source
            driver.quit()

            soup = BeautifulSoup(page_source, "html.parser")
            for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            print(f"✅ Successfully fetched {url} with UC (attempt {attempt + 1})")
            return text.strip()

        except Exception as e:
            print(f"⚠️ UC attempt {attempt + 1} failed for {url}: {e}")
            try:
                driver.quit()
            except:
                pass
            time.sleep(2)

    print(f"❌ All UC attempts failed for {url}")
    return None


def is_valid_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)

        if r.status_code == 200:
            return True
        elif r.status_code in [301, 302]:
            return True
        elif r.status_code in [403, 404, 500]:
            print(f"⚠️ HTTP error {r.status_code} for {url}. Trying Playwright fallback...")
            content = fetch_content_with_playwright(url)
            if content and len(content) > 100:
                print(f"✅ URL loaded with Playwright for {url}")
                return True
            else:
                print(f"❌ URL failed even with Playwright for {url}")
                return False
        else:
            print(f"→ URL responded with unexpected status {r.status_code}")
            return False

    except (Timeout, ConnectionError, ProtocolError, RemoteDisconnected) as e:
        print(f"⚠️ Network issue: {e} when validating {url}. Trying Playwright fallback...")
        content = fetch_content_with_playwright(url)
        if content and len(content) > 100:
            print(f"✅ URL loaded with Playwright for {url}")
            return True
        else:
            print(f"❌ URL failed even with Playwright for {url}")
            return False
    except Exception as e:
        print(f"→ General Exception checking URL: {e}")
        return False



def is_valid_url_old(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if r.status_code in [200, 301, 302]:
            return True
        else:
            print(f"→ URL responded with status code {r.status_code}")
            return False
    except (Timeout, ConnectionError, ProtocolError, RemoteDisconnected) as e:
        print(f"⚠️ Network issue: {e} when validating {url}. Trying with Playwright...")
        # Try playwright browser as fallback before rejecting
        content = fetch_content_with_playwright(url)
        if content and len(content) > 100:
            print(f"✅ URL loaded with Playwright for {url}")
            return True
        else:
            print(f"❌ URL failed even with Playwright for {url}")
            return False
    except Exception as e:
        print(f"→ General Exception checking URL: {e}")
        return False


def is_valid_url_old(url):
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

def fetch_content_with_playwright_old(url):
    print(f"🌐 Fetching using real browser: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Run Chrome headless
        page = browser.new_page()
        try:
            print(f"🌐 Playwright trying to load URL: {url}")
            page.goto(url, timeout=60000)  # 60 seconds timeout
            page_content = page.content()
            browser.close()
            print(f"✅ Successfully fetched {url} with Playwright browser")


            soup = BeautifulSoup(page_content, "html.parser")

            for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            return text.strip()

        except Exception as e:
            print(f"⚠️ Playwright exception: {e}")
            browser.close()
            return None

def fetch_content_with_playwright(url):
    print(f"🌐 Fetching using real browser (Playwright): {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

            for attempt in range(3):
                try:
                    page.goto(url, timeout=60000, wait_until="domcontentloaded")  # Wait only until DOM is ready
                    page_content = page.content()

                    soup = BeautifulSoup(page_content, "html.parser")
                    for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                        tag.decompose()

                    text = soup.get_text(separator="\n", strip=True)
                    browser.close()
                    print(f"✅ Successfully fetched {url} with Playwright on attempt {attempt + 1}")
                    return text.strip()

                except Exception as e:
                    print(f"⚠️ Playwright attempt {attempt + 1} failed for {url}: {e}")
                    time.sleep(2 * (attempt + 1))  # Exponential backoff between retries
                    continue

            print(f"❌ All Playwright attempts failed for {url}")
            browser.close()
            return None

    except Exception as e:
        print(f"❌ General Playwright failure: {e}")
        return None


#Retry logic for URLs incase of timeouts
def fetch_url_with_retry(url, retries=3, timeout=30):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=timeout)
            return response
        except requests.exceptions.Timeout:
            print(f"⏳ Timeout when accessing {url}. Retrying {attempt + 1}/{retries}...")
            time.sleep(2)  # brief wait before retry
        except Exception as e:
            print(f"⚠️ Error accessing {url}: {e}")
            break
    return None

def fetch_content(url, retries=3, timeout=(30, 180)):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    session = requests.Session()

    if url.lower().endswith(".pdf"):
        print(f"📄 Detected PDF, downloading: {url}")
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                temp_pdf_path = "temp_downloaded_file.pdf"
                with open(temp_pdf_path, "wb") as f:
                    f.write(response.content)

                text = ""
                try:
                    doc = fitz.open(temp_pdf_path)
                    for page in doc:
                        text += page.get_text()
                finally:
                    doc.close()
                    os.remove(temp_pdf_path)
                return text.strip()
            else:
                print(f"❌ Failed to download PDF. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ Exception fetching PDF: {e}")
            return None

    # HTML case
    for attempt in range(retries):
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                    tag.decompose()
                page_text = soup.get_text(separator="\n", strip=True)
                return page_text.strip()
            else:
                print(f"⚠️ Non-200 status code {response.status_code} for {url}")
        except (Timeout, ConnectionError, ProtocolError, RemoteDisconnected) as e:
            print(f"⚠️ Network issue: {type(e).__name__} on {url}. Attempt {attempt + 1}/{retries}. Retrying...")
        except Exception as e:
            print(f"⚠️ General error {e} on {url}. Attempt {attempt + 1}/{retries}. Retrying...")

        time.sleep(5 * (attempt + 1))

    # All retries failed → try Playwright
    print(f"⚡ Falling back to Playwright for {url}")
    content = fetch_content_with_playwright(url)

    if not content:
        print(f"⚡ Playwright failed, falling back to Undetected ChromeDriver for {url}")
        content = fetch_content_with_undetected_chromedriver(url)

    return content


def fetch_content_old6(url, retries=3, timeout=(30, 180)):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    session = requests.Session()

    if url.lower().endswith(".pdf"):
        print(f"📄 Detected PDF, downloading: {url}")
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                temp_pdf_path = "temp_downloaded_file.pdf"
                with open(temp_pdf_path, "wb") as f:
                    f.write(response.content)

                text = ""
                try:
                    doc = fitz.open(temp_pdf_path)
                    for page in doc:
                        text += page.get_text()
                finally:
                    doc.close()
                    os.remove(temp_pdf_path)
                return text.strip()
            else:
                print(f"❌ Failed to download PDF. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ Exception fetching PDF: {e}")
            return None

    # HTML case
    for attempt in range(retries):
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                    tag.decompose()
                page_text = soup.get_text(separator="\n", strip=True)
                return page_text.strip()
            else:
                print(f"⚠️ Non-200 status code {response.status_code} for {url}")
        except (Timeout, ConnectionError, ProtocolError, RemoteDisconnected) as e:
            print(f"⚠️ Network issue: {type(e).__name__} on {url}. Attempt {attempt + 1}/{retries}. Retrying...")
        except Exception as e:
            print(f"⚠️ General error {e} on {url}. Attempt {attempt + 1}/{retries}. Retrying...")

        time.sleep(5 * (attempt + 1))

    # All retries failed, try Playwright
    print(f"⚡ Falling back to Playwright for {url}")
    return fetch_content_with_playwright(url)


#Updated to use Playwright 
def fetch_content_old6(url, retries=3, timeout=(30, 180)):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }

    session = requests.Session()

    if url.lower().endswith(".pdf"):
        print(f"📄 Detected PDF, downloading: {url}")
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                temp_pdf_path = "temp_downloaded_file.pdf"
                with open(temp_pdf_path, "wb") as f:
                    f.write(response.content)
                text = ""
                try:
                    doc = fitz.open(temp_pdf_path)
                    for page in doc:
                        text += page.get_text()
                finally:
                    doc.close()
                    os.remove(temp_pdf_path)
                return text.strip()
            else:
                print(f"❌ Failed to download PDF. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ Exception fetching PDF: {e}")
            return None

    # HTML handling
    for attempt in range(retries):
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                    tag.decompose()
                page_text = soup.get_text(separator="\n", strip=True)
                return page_text.strip()
            else:
                print(f"⚠️ Non-200 status code {response.status_code} for {url}")

        except (Timeout, ConnectionError, ProtocolError, RemoteDisconnected) as e:
            print(f"⚠️ Network issue: {type(e).__name__} on {url}. Attempt {attempt + 1}/{retries}. Retrying...")

        except Exception as e:
            print(f"⚠️ General error {e} on {url}. Attempt {attempt + 1}/{retries}. Retrying...")

        time.sleep(5 * (attempt + 1))

    # All retries failed, use Playwright
    print(f"⚡ Falling back to Playwright for {url}")
    return fetch_content_with_playwright(url)




#Older fetch, no longer used
def fetch_content_old6(url, retries=7, timeout=(15, 120)):  # connect timeout, read timeout
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }

    session = requests.Session()

    for attempt in range(retries):
        try:
            if url.lower().endswith(".pdf"):
                print(f"📄 Detected PDF, downloading: {url}")
                response = session.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    temp_pdf_path = "temp_downloaded_file.pdf"
                    with open(temp_pdf_path, "wb") as f:
                        f.write(response.content)

                    text = ""
                    try:
                        doc = fitz.open(temp_pdf_path)
                        for page in doc:
                            text += page.get_text()
                    finally:
                        doc.close()
                        os.remove(temp_pdf_path)
                    return text.strip()
                else:
                    print(f"❌ Failed to download PDF. Status code: {response.status_code}")
                    return None

            else:
                response = session.get(url, headers=headers, timeout=timeout)
                if response.status_code != 200:
                    print(f"❌ Failed to fetch HTML page. Status code: {response.status_code}")
                    return None

                soup = BeautifulSoup(response.text, "html.parser")

                for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                    tag.decompose()

                page_text = soup.get_text(separator="\n", strip=True)
                return page_text.strip()

        except requests.exceptions.Timeout:
            print(f"⏳ Timeout when accessing {url}. Retrying ({attempt + 1}/{retries})...")
            time.sleep(5 + attempt)  # Slightly longer wait each time
        except Exception as e:
            print(f"⚠️ Exception fetching {url}: {e}")
            time.sleep(5)

    print(f"❌ Giving up fetching {url} after {retries} retries.")
    return None


def fetch_content_old4(url, retries=5, timeout=60):  # Increase retries and timeout
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }

    session = requests.Session()

    for attempt in range(retries):
        try:
            if url.lower().endswith(".pdf"):
                print(f"📄 Detected PDF, downloading: {url}")
                response = session.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    temp_pdf_path = "temp_downloaded_file.pdf"
                    with open(temp_pdf_path, "wb") as f:
                        f.write(response.content)

                    text = ""
                    try:
                        doc = fitz.open(temp_pdf_path)
                        for page in doc:
                            text += page.get_text()
                    finally:
                        doc.close()
                        os.remove(temp_pdf_path)  # Clean up temporary file
                    return text.strip()
                else:
                    print(f"❌ Failed to download PDF. Status code: {response.status_code}")
                    return None

            else:
                response = session.get(url, headers=headers, timeout=timeout)
                if response.status_code != 200:
                    print(f"❌ Failed to fetch HTML page. Status code: {response.status_code}")
                    return None

                soup = BeautifulSoup(response.text, "html.parser")

                for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                    tag.decompose()

                page_text = soup.get_text(separator="\n", strip=True)
                return page_text.strip()

        except requests.exceptions.Timeout:
            print(f"⏳ Timeout when accessing {url}. Retrying ({attempt + 1}/{retries})...")
            time.sleep(5)  # Sleep a bit longer before retry
        except Exception as e:
            print(f"⚠️ Exception fetching {url}: {e}")
            time.sleep(5)

    print(f"❌ Giving up fetching {url} after {retries} retries.")
    return None


def fetch_content_old3(url, retries=3, timeout=30):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }

    session = requests.Session()

    for attempt in range(retries):
        try:
            if url.lower().endswith(".pdf"):
                print(f"📄 Detected PDF, downloading: {url}")
                response = session.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    temp_pdf_path = "temp_downloaded_file.pdf"
                    with open(temp_pdf_path, "wb") as f:
                        f.write(response.content)

                    text = ""
                    try:
                        doc = fitz.open(temp_pdf_path)
                        for page in doc:
                            text += page.get_text()
                    finally:
                        doc.close()
                        os.remove(temp_pdf_path)  # Clean up temporary file
                    return text.strip()
                else:
                    print(f"❌ Failed to download PDF. Status code: {response.status_code}")
                    return None

            else:
                response = session.get(url, headers=headers, timeout=timeout)
                if response.status_code != 200:
                    print(f"❌ Failed to fetch HTML page. Status code: {response.status_code}")
                    return None

                soup = BeautifulSoup(response.text, "html.parser")

                # Remove non-content elements to improve content quality
                for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
                    tag.decompose()

                page_text = soup.get_text(separator="\n", strip=True)
                return page_text.strip()

        except requests.exceptions.Timeout:
            print(f"⏳ Timeout when accessing {url}. Retrying ({attempt + 1}/{retries})...")
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ Exception fetching {url}: {e}")
            time.sleep(5)

    print(f"❌ Giving up fetching {url} after {retries} retries.")
    return None

def fetch_content_old2(url, retries=3, timeout=30):
    #Mimic normal browser traffic, otherwises 403 errors from bot detection on DMV sites
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }

    for attempt in range(retries):
        try:
            if url.lower().endswith(".pdf"):
                print(f"📄 Detected PDF, downloading: {url}")
                response = requests.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    temp_pdf_path = "temp_downloaded_file.pdf"
                    with open(temp_pdf_path, "wb") as f:
                        f.write(response.content)

                    text = ""
                    try:
                        doc = fitz.open(temp_pdf_path)
                        for page in doc:
                            text += page.get_text()
                    finally:
                        doc.close()
                        os.remove(temp_pdf_path)  # Clean up temp file
                    return text
                else:
                    print(f"❌ Failed to download PDF. Status code: {response.status_code}")
                    return None

            else:
                response = requests.get(url, headers=headers, timeout=timeout)
                if response.status_code != 200:
                    print(f"❌ Failed to fetch HTML page. Status code: {response.status_code}")
                    return None

                soup = BeautifulSoup(response.text, "html.parser")
                for script in soup(["script", "style", "header", "footer", "nav", "aside"]):
                    script.decompose()
                page_text = soup.get_text(separator="\n", strip=True)
                return page_text

        except requests.exceptions.Timeout:
            print(f"⏳ Timeout when accessing {url}. Retrying {attempt + 1}/{retries}...")
            time.sleep(3)  # slight pause between retries
        except Exception as e:
            print(f"⚠️ Exception fetching {url}: {e}")
            return None

    print(f"❌ Giving up fetching {url} after {retries} retries.")
    return None

#original, no longer used
#Modified to handle PDFs
def fetch_content_old(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)"
        }

        if url.lower().endswith(".pdf"):
            print(f"📄 Detected PDF, downloading: {url}")
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                temp_pdf_path = "temp_downloaded_file.pdf"
                with open(temp_pdf_path, "wb") as f:
                    f.write(response.content)

                text = ""
                try:
                    doc = fitz.open(temp_pdf_path)
                    for page in doc:
                        text += page.get_text()
                finally:
                    doc.close()
                    os.remove(temp_pdf_path)  # Clean up the temporary file
                return text
            else:
                print(f"❌ Failed to download PDF. Status code: {response.status_code}")
                return None

        else:
            # Normal HTML page
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"❌ Failed to fetch HTML page. Status code: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove common non-content elements
            for script in soup(["script", "style", "header", "footer", "nav", "aside"]):
                script.decompose()

            page_text = soup.get_text(separator="\n", strip=True)
            return page_text

    except Exception as e:
        print(f"❌ Exception during fetch_content for {url}: {e}")
        return None
    
#def fetch_content(url):
#    try:
#        headers = {'User-Agent': 'Mozilla/5.0'}
#        r = requests.get(url, headers=headers, timeout=15)
#        r.raise_for_status()
#        soup = BeautifulSoup(r.text, 'html.parser')
#
#        content_blocks = set()
#
        # Headers + sibling <p>
#        for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
#            block = header.get_text(strip=True)
#            next_p = header.find_next_sibling('p')
#            if next_p:
#                block += " " + next_p.get_text(strip=True)
#            content_blocks.add(block.strip())

        # Broader tag types
#        for tag in soup.find_all(['p', 'li', 'span', 'div']):
#            text = tag.get_text(strip=True)
#            if text and len(text.split()) > 4:
#                content_blocks.add(text.strip())

#        full_text = "\n\n".join(content_blocks)
#        return full_text

#    except Exception as e:
#        print(f"Failed to fetch {url}: {e}")
#        return None

#Estimate Token Count Before GPT Call
def estimate_tokens(text):
    # Roughly 4 characters per token for English
    return int(len(text) / 4)



def search_dmv_url(state):
    print(f"Searching DuckDuckGo for {state} DMV...")
    ##with DDGS() as ddgs:
        ##results = ddgs.text(f"{state} DMV site:.gov license plate transfer", max_results=5)
        ##results = ddgs.text(
        ##    f"{state} DMV site:.gov OR site:{state.lower()}.us OR site:.{state.lower()} license plate transfer", max_results=5
        ##)
    query = f"What should I do with the license plates when I sell a vehicle in {state} site:.gov OR site:{state.lower()}.us OR site:.{state.lower()}"
    print(f"🔍 DuckDuckGo query: {query}")
    ddgs = DDGS()

    try:
        results = ddgs.text(query, max_results=5)
        time.sleep(5)  # <-- Pause 5 seconds after each query
    except Exception as e:
        print(f"⚠️ DuckDuckGo search error: {e}")
        return None

        #results = ddgs.text(query, max_results=5)

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
        - Plate stays with seller (must surrender to DMV or destroy)
        - Plate stays with seller (can transfer)
   
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

    print(f"\n📄 Full content length for {state}: {len(found_content)} characters")
    print("\n📄 Content provided to GPT for evaluation:\n")
    print(f"📏 Content length for {state}: {len(found_content)} characters")
    print(found_content[:4000])  # Adjust length as needed (1000 is a good starting point). This is just the output that is used for debugging.
    
    # Chunk the content into 20,000-character blocks
    chunks = [found_content[i:i + MAX_CHARS] for i in range(0, len(found_content), MAX_CHARS)]
    print(f"🔍 Processing {len(chunks)} chunks for {state}")

    for idx, chunk in enumerate(chunks):
        print(f"\n🧩 Evaluating chunk {idx + 1} / {len(chunks)} for {state}...")

        prompt = f"""
        You are an API system that must ONLY return valid JSON.

        Given this DMV content below for {state}, please assess whether the content
        identifies whether the license plate should stay with the seller (and for example transferred to another vehicle owned by the
        seller), if the license plate must stay with the same vehicle when the vehicle is sold, or if the license plate must be surrendered to the DMV. 
        If the content explicitly states a policy, summarize it in a concise manner.
        If the content implies a rule but does not directly say it, infer the likely policy and explain your reasoning.
        When the website or document does not explicitly state what happens to license plates, infer policy if strongly implied from registration rules and the context of the page or document (e.g., from the heading or document title)
            For example, if the document states that the registration or license plates may only be transferred to a vehicle with the same owner, assume the plates stay with the seller unless otherwise stated.
            Be cautious: Only infer if the connection is clear and reasonable.
        If the content is vague or indirect, summarize the likely policy based on the content.
        If the content is not relevant to license plates, return "Policy not found - manual validation needed".
        
        Disregard content that refers to personalized plates as these are edge cases not relevant to the general plate retention policy.

        IMPORTANT: Ignore policies that only refer to personalized, specialty, or vanity plates.
                    
        Extract:
        1. Concise policy summary clearly identifying whether the plate stays with the seller, must be transferred with the vehicle, must be 
            destoyed or defaced by the seller, or must be surrendered to the DMV.
        2. A **direct quote** from the content (not a heading), that clearly supports the policy summary. Only include the specific sentence(s) that state or strongly imply the policy. Do not include section titles or headers. 
            These phrases are strong signals of the plate policy. If such a phrase is found, prioritize quoting it over any vague or indirect references.
            - "plates remain with the vehicle"
            - "plates should be destroyed by the seller"
            - "plates must be returned to the DMV"
            - "plates stay with the seller"
            - "is a plate with owner state" (indicates the plate stays with the seller)
            - "plate belongs with an owner" (which indicates the plate stays with the seller)
            - "plate belongs to a vehicle" (which indicates the plate stays with the vehicle)
            - "plate stays with the vehicle"
            - "plates are ratained by the owner" (which indicates the plate stays with the seller)
            - "previous owner should keep the vehicle’s license plate"
            - "plates must be surrendered"
            - "remove your license plates before selling"
            These phrases often indicate the license plate retention policy. 
            If multiple sentences communicate the same rule, return only the most concise and direct one.
            If the most relevant text explicitly provides instructions for the seller, 
                but does not say to remove tags or license plates, this may be an indication that 
                plates should stay with the vehicle - but this should be a low confidence assessment.
            Disregard policies that provide instructions on what to do when selling or transferring a vehicle to an out-of-state buyer, as this is an exception as we are primarily focused on policies when transferring to an in-state buyer.
        3. A field called "highlighted_quote": return the same quote as "dmv_excerpt" but bold the 1–3 word phrase that most clearly supports the policy assessment using Markdown (e.g., **remain with the vehicle**). Do not bold entire sentences — only the keywords or phrases that indicate the retention policy.
        4. Provide the source URL

        Content:
        \"\"\"
        {chunk}
        \"\"\"

        Output only valid JSON like:

        ```json
        {{
        "state": "{state}",
        "policy_summary": "",
        "dmv_excerpt": "",
        "highlighted_quote": "",
        "plate_retention_policy": "",
        "source_url": "{used_url}"
        }}
        ```
        """

        #    response = client.chat.completions.create(
        #        model="gpt-4",
        #        messages=[{"role": "user", "content": prompt}]
        #    )
        estimated_tokens = estimate_tokens(prompt)
        print(f"🔢 Estimated token count for chunk {idx + 1}: {estimated_tokens} tokens")

        #Retry logic to get around OpenAI per-minute rate limits
        for attempt in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}]
                )
                break
            except openai.RateLimitError:
                print(f"⚠️ Rate limit hit. Retrying in {RETRY_DELAY} seconds... (Attempt {attempt + 1})")
                time.sleep(RETRY_DELAY)
            except Exception as e:
                print(f"❌ GPT error: {e}")
                continue
        else:
            print(f"❌ Failed all attempts for chunk {idx + 1}")
            continue

        gpt_output = response.choices[0].message.content.strip()
        ##print(f"GPT raw output for {state}:\n{gpt_response}")
        print(f"📤 GPT response for chunk {idx + 1}:\n{gpt_output}")

        try:
            if "```json" in gpt_output:
                gpt_output = gpt_output.split("```json")[1].split("```")[0].strip()

            result = json.loads(gpt_output)
            # Normalize field names for evaluator compatibility
            if "direct_quote" in result:
                result["dmv_excerpt"] = result["direct_quote"]
            summary = result.get("policy_summary", "")
            if summary:
                classification = classify_plate_policy(state, summary)
                result["plate_retention_policy"] = classification  #Get a simplified output - plate stays with owner, etc.

            if result.get("plate_retention_policy") and result["plate_retention_policy"] != "Manual validation required":
                return result  # ✅ Found a valid policy — stop

#            if result.get("plate_retention_policy") and result["plate_retention_policy"] != "Manual validation required":
#                return result  # ✅ Found a valid policy — stop
        except Exception as e:
            print(f"❌ Failed to parse JSON for chunk {idx + 1}: {e}")
            continue

    # ❌ If no valid response found
    print(f"❌ No confident answer found for {state}. Returning fallback.")
    return {
        "state": state,
        "policy_summary": "Policy not found - manual validation needed",
        "dmv_excerpt": "Manual validation required",
        "highlighted_quote": "",
        "source_url": used_url or "Not found",
        "plate_retention_policy": "Manual validation required"
    }


#    for attempt in range(MAX_RETRIES):
#        try:
#            response = client.chat.completions.create(
#                model="gpt-4",
#                messages=[{"role": "user", "content": prompt}]
#            )
#            break  # Success
#        except openai.RateLimitError as e:
#            print(f"⚠️ Token rate limit hit for {state}. Retrying in {RETRY_DELAY} seconds... (Attempt {attempt + 1})")
#            time.sleep(RETRY_DELAY)
#            RETRY_DELAY *= 2  # Exponential backoff
#        except Exception as e:
#            print(f"❌ GPT call failed for {state}: {e}")
#            return {
#                "state": state,
#                "policy_summary": "Policy not found - GPT error",
#                "dmv_excerpt": "",
#                "highlighted_quote": "",
#                "plate_retention_policy": "Manual validation required",
#                "source_url": used_url or url or "Not found"
#            }
#    else:
#        print(f"❌ Max retries reached for {state}. Skipping.")
#        return {
#            "state": state,
#            "policy_summary": "Policy not found - GPT rate limit",
#            "dmv_excerpt": "",
#            "highlighted_quote": "",
#            "plate_retention_policy": "Manual validation required",
#            "source_url": used_url or url or "Not found"
#        }
#    gpt_response = response.choices[0].message.content.strip()
#
#    print(f"GPT raw output for {state}:\n{gpt_response}")
#
#
#    try:
#        if "```json" in gpt_response:
#            gpt_response = gpt_response.split("```json")[1].split("```")[0].strip()
#
#        policy_data = json.loads(gpt_response)
#
##       classification = classify_plate_policy(state, policy_data['policy_summary'])
##        policy_data["plate_retention_policy"] = classification
#        return policy_data
#    except Exception as e:
#        print(f"Failed to parse GPT output for {state}: {e}")
#    return {
#            "state": state,
#            "policy_summary": "Policy not found - manual validation needed",
#            "dmv_excerpt": "Manual validation required",
#            "source_url": used_url or url or "Not found",
#            "plate_retention_policy": "Manual validation required"
#        }


def save_manual_overrides():
    with open('manual_overrides.json', 'w') as f:
        json.dump(manual_overrides, f, indent=2)
    log_file.close()
