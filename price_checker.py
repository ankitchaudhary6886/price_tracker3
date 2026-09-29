import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- Configuration ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
SCRAPER_API_KEY = os.environ.get('SCRAPER_API_KEY')
PRODUCTS_FILE = 'products.json'

# --- Helper Functions ---
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def get_price_from_url(url):
    """Scrapes the price using ScraperAPI to bypass bot detection."""
    # ScraperAPI URL - Add special parameters for Flipkart
    if 'flipkart' in url:
        # Switch to mobile URL and force premium proxies to bypass Flipkart's strict blocking
        mobile_url = url.replace('www.flipkart.com', 'm.flipkart.com')
        api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={mobile_url}&render=true&country_code=in&premium=true&device_type=mobile"
    else:
        api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}"
    
    try:
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # --- Amazon Price Selectors ---
        if 'amazon' in url:
            price_element = soup.select_one('.a-price-whole, #priceblock_ourprice, .a-offscreen, #priceblock_dealprice')
            if price_element:
                price_text = price_element.get_text().strip()
                return float(re.sub(r'[^\d.]', '', price_text))
        
        # --- Flipkart Price Selectors ---
        elif 'flipkart' in url:
            price_element = soup.select_one('._30jeq3._16Jk6d, ._1vC4OE, ._3qQ9m1, ._25b18c, ._30jeq3')
            if price_element:
                price_text = price_element.get_text().strip()
                return float(re.sub(r'[^\d.]', '', price_text))

    except Exception as e:
        print(f"Error fetching price for {url}: {e}")
    return None

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
