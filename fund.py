import os
import time
import random
import string
import logging
import requests
from playwright.sync_api import sync_playwright
from dotenv import set_key

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("FinalUnstoppableBot")

# जो Sitekey और वर्शन हमने कन्फर्म किया, उसे यहाँ फिक्स कर दिया है
SITE_KEY = "6LcwtHkpAAAAABHUXtvKCZQ645083zUdeimy8NLP"
MAIN_URL = "https://join.autismspeaks.org/fundraiser/7339411"
PAGE_URL = "https://join.autismspeaks.org/campaign/2026-fundraise-your-way/c732607/search"

# 🔴 अपनी कैप्चा सॉल्वर सर्विस की API KEY यहाँ डालो (जैसे Capsolver या 2Captcha)
CAPTCHA_API_KEY = "8387db1ecb2408dd46c5b9d15b06de1c" 

def get_all_proxies():
    possible_names = ["Webshare proxies.txt", "Webshare proxies", "proxies.txt", "proxy.txt"]
    for name in possible_names:
        if os.path.exists(name):
            with open(name, "r") as f:
                return [line.strip() for line in f if line.strip()]
    return []

def parse_proxy(selected_line):
    try:
        if "@" in selected_line:
            auth_part, server_part = selected_line.replace("http://", "").split("@")
            username, password = auth_part.split(":")
            return {"server": f"http://{server_part}", "username": username, "password": password}
        parts = selected_line.split(":")
        if len(parts) == 4:
            ip, port, username, password = parts
            return {"server": f"http://{ip}:{port}", "username": username, "password": password}
        return {"server": f"http://{selected_line}", "username": "", "password": ""}
    except:
        return None

def check_proxy_invisible(proxy_config):
    """चुपचाप बैकग्राउंड में (Headless) चेक करेगा कि प्रॉक्सी ब्लॉक है या नहीं"""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, proxy=proxy_config)
            page = browser.new_page()
            page.set_default_timeout(15000) # क्विक 15 सेकंड चेक
            page.goto(MAIN_URL, wait_until="load")
            content = page.content().lower()
            browser.close()
            if "blocked" in content or "unable to access" in content or "cloudflare" in content:
                return False
            return True
        except:
            return False

def get_captcha_token():
    """reCAPTCHA v2 Invisible टोकन जनरेट करने के लिए Capsolver API कॉल"""
    if CAPTCHA_API_KEY == "YOUR_CAPTCHA_SOLVER_API_KEY":
        logger.warning("⚠️ Captcha API Key नहीं डाली गई है! स्क्रिप्ट बिना टोकन के ट्राई करेगी।")
        return None
        
    logger.info("📡 Requesting solved reCAPTCHA v2 token from API...")
    try:
        payload = {
            "clientKey": CAPTCHA_API_KEY,
            "task": {
                "type": "ReCaptchaV2TaskProxyLess",
                "websiteURL": PAGE_URL,
                "websiteKey": SITE_KEY
            }
        }
        res = requests.post("https://api.capsolver.com/createTask", json=payload, timeout=20).json()
        task_id = res.get("taskId")
        
        if not task_id:
            return None
            
        for _ in range(20): # 1 मिनट तक पोलिंग करेगा
            time.sleep(3)
            result = requests.post("https://api.capsolver.com/getTaskResult", json={"clientKey": CAPTCHA_API_KEY, "taskId": task_id}).json()
            if result.get("status") == "ready":
                token = result.get("solution", {}).get("gRecaptchaResponse")
                logger.info("✅ Captcha successfully solved by API!")
                return token
        return None
    except Exception as e:
        logger.error(f"Captcha Solver Error: {e}")
        return None

def run_bot():
    all_proxies = get_all_proxies()
    if not all_proxies:
        logger.error("No proxies found in your file!")
        return

    logger.info(f"Loaded {len(all_proxies)} proxies. Finding a clean, unblocked IP first...")

    clean_proxy = None
    # 1. बैकग्राउंड चेक लूप (ताकि फालतू में ब्लॉक प्रॉक्सी पर ब्राउज़र न खुले)
    for idx, proxy_line in enumerate(all_proxies, start=1):
        config = parse_proxy(proxy_line)
        if not config:
            continue
            
        if check_proxy_invisible(config):
            logger.info(f"🎯 Clean IP found at index {idx}: {config['server']}")
            clean_proxy = config
            break
        else:
            logger.warning(f"❌ Proxy {idx} is blocked/dead. Checking next...")

    if not clean_proxy:
        logger.error("No clean proxies found in the list!")
        return

    # 2. जब अनब्लॉक प्रॉक्सी मिल जाए, सिर्फ तभी असली ब्राउज़र खुलेगा
    logger.info("Opening the live browser with the unblocked proxy now!")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=False, # लाइव स्क्रीन दिखेगी
                proxy=clean_proxy,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = browser.new_page()
            page.set_default_timeout(60000)
            
            page.goto(MAIN_URL, wait_until="load")
            
            # स्टेप 1: Search बटन क्लिक
            logger.info("Clicking Search Icon...")
            search_btn = "a.header-block_search"
            page.wait_for_selector(search_btn, state="visible")
            page.locator(search_btn).click(force=True)
            
            # स्टेप 2: बैकग्राउंड में कैप्चा टोकन मंगाना और इंजेक्ट करना
            token = get_captcha_token()
            if token:
                logger.info("Injecting reCAPTCHA v2 Token into hidden forms...")
                page.evaluate(f"""(solvedToken) => {{
                    const textarea = document.getElementById('g-recaptcha-response');
                    if (textarea) textarea.innerHTML = solvedToken;
                    
                    const nameElements = document.getElementsByName('g-recaptcha-response');
                    if (nameElements.length > 0) nameElements[0].innerHTML = solvedToken;
                }}""", token)
            
            # स्टेप 3: Teams फ़िल्टर बटन हिट करना
            logger.info("Hitting 'Teams' button...")
            filter_btn = "button.p2p-search-filters-item-button"
            page.wait_for_selector(filter_btn, state="visible")
            page.locator(filter_btn).first.click(force=True)
            logger.info("🎯 BOOM! Teams filter clicked successfully with Captcha token!")
            time.sleep(3)
            
            # स्टेप 4: पहली टीम पर क्लिक
            page.wait_for_selector(".p2p-search-results a", state="visible")
            page.locator(".p2p-search-results a").first.click(force=True)
            time.sleep(3)
            
            # स्टेप 5: JOIN TEAM पर क्लिक
            page.wait_for_selector("text=JOIN TEAM", state="visible")
            page.locator("text=JOIN TEAM").first.click(force=True)
            time.sleep(3)
            
            # स्टेप 6: CREATE AN ACCOUNT पर क्लिक
            page.wait_for_selector("text=CREATE AN ACCOUNT", state="visible")
            page.locator("text=CREATE AN ACCOUNT").first.click(force=True)
            
            logger.info("🎉 SUCCESS! Reached the registration form without any blocks.")
            time.sleep(15) # आराम से देख लो, फिर ब्राउज़र बंद होगा
            browser.close()
            
        except Exception as e:
            logger.error(f"Error in active browser flow: {e}")

if __name__ == "__main__":
    run_bot()