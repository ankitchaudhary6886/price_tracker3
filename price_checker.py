import json
import os
import re
from playwright.sync_api import sync_playwright
from datetime import datetime

# --- Configuration ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
PRODUCTS_FILE = 'products.json'

# --- Helper Functions ---
def send_telegram_message(message):
    """Sends a message to your Telegram chat."""
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def get_price_from_url(url):
    """Scrapes the price from a given product URL using Playwright."""
    price = None
    with sync_playwright() as p:
        # Launch a headless Chromium browser
        browser = p.chromium.launch(headless=True)
        # Create a new context with a realistic user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        try:
            # Go to the page and wait for the network to be idle
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000) # Wait 3 seconds for JS to load prices

            if 'amazon' in url:
                # Amazon selectors
                price_selectors = ['.a-price-whole', '#priceblock_ourprice', '.a-offscreen', '#priceblock_dealprice']
                for selector in price_selectors:
                    if page.locator(selector).count() > 0:
                        price_text = page.locator(selector).first.inner_text()
                        price = float(re.sub(r'[^\d.]', '', price_text))
                        break
            
            elif 'flipkart' in url:
                # Flipkart selectors
                price_selectors = ['._30jeq3._16Jk6d', '._1vC4OE', '._3qQ9m1', '._25b18c']
                for selector in price_selectors:
                    if page.locator(selector).count() > 0:
                        price_text = page.locator(selector).first.inner_text()
                        price = float(re.sub(r'[^\d.]', '', price_text))
                        break

        except Exception as e:
            print(f"Error fetching price for {url}: {e}")
        finally:
            browser.close()
            
    return price

# --- Main Logic ---
def main():
    with open(PRODUCTS_FILE, 'r') as f:
        products = json.load(f)

    alerts = []
    updated_products = []

    for product in products:
        print(f"Checking: {product['name']}")
        current_price = get_price_from_url(product['url'])
        
        if current_price is None:
            print(f"Could not fetch price for {product['name']}")
            updated_products.append(product)
            continue

        name = product['name']
        target = product.get('target_price')
        last = product.get('last_price')

        updated_product = product.copy()
        updated_product['last_price'] = current_price
        updated_products.append(updated_product)

        change_msg = ""
        if last is not None:
            change = current_price - last
            if change < 0:
                change_msg = f"📉 *Dropped by ₹{abs(change):.2f}* from ₹{last:.2f}"
            elif change > 0:
                change_msg = f"📈 *Increased by ₹{change:.2f}* from ₹{last:.2f}"
            else:
                change_msg = "No change from last check."

        target_msg = ""
        if target is not None:
            distance = current_price - target
            if distance <= 0:
                target_msg = f"🎉 *TARGET HIT!* Below your target of ₹{target:.2f}"
            else:
                target_msg = f"Distance to target (₹{target:.2f}): ₹{distance:.2f} away"

        message = (
            f"*Price Update for {name}*\n"
            f"*Current Price:* ₹{current_price:.2f}\n"
            f"{change_msg}\n"
            f"{target_msg}\n"
            f"[View Product]({product['url']})"
        )
        alerts.append(message)

    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(updated_products, f, indent=2)

    if alerts:
        final_message = "\n\n---\n\n".join(alerts)
        send_telegram_message(final_message)

if __name__ == "__main__":
    main()
