import json
import os
import re
import cloudscraper  # New library to bypass bot protection
from bs4 import BeautifulSoup
from datetime import datetime

# --- Configuration ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
PRODUCTS_FILE = 'products.json'

# Initialize the scraper
scraper = cloudscraper.create_scraper()

# --- Helper Functions ---
def send_telegram_message(message):
    """Sends a message to your Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def get_price_from_url(url):
    """Scrapes the price from a given product URL."""
    # More realistic headers to look like a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    try:
        response = scraper.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # --- Amazon Price Selectors ---
        if 'amazon' in url:
            # Try multiple potential selectors
            price_element = soup.select_one('.a-price-whole, #priceblock_ourprice, .a-offscreen, #priceblock_dealprice')
            if price_element:
                price_text = price_element.get_text().strip()
                return float(re.sub(r'[^\d.]', '', price_text))
        
        # --- Flipkart Price Selectors ---
        elif 'flipkart' in url:
            # Try multiple potential selectors
            price_element = soup.select_one('._30jeq3._16Jk6d, ._1vC4OE, ._3qQ9m1, ._25b18c')
            if price_element:
                price_text = price_element.get_text().strip()
                return float(re.sub(r'[^\d.]', '', price_text))

    except Exception as e:
        print(f"Error fetching price for {url}: {e}")
    return None

# --- Main Logic ---
def main():
    # Load product data
    with open(PRODUCTS_FILE, 'r') as f:
        products = json.load(f)

    alerts = []
    updated_products = []

    for product in products:
        print(f"Checking: {product['name']}")
        current_price = get_price_from_url(product['url'])
        
        if current_price is None:
            print(f"Could not fetch price for {product['name']}")
            updated_products.append(product) # Keep original if fetch fails
            continue

        # Prepare alert message components
        name = product['name']
        target = product.get('target_price')
        last = product.get('last_price')

        # Update the product's last_price for the next run
        updated_product = product.copy()
        updated_product['last_price'] = current_price
        updated_products.append(updated_product)

        # Check for changes and targets
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

        # Build the final message
        message = (
            f"*Price Update for {name}*\n"
            f"*Current Price:* ₹{current_price:.2f}\n"
            f"{change_msg}\n"
            f"{target_msg}\n"
            f"[View Product]({product['url']})"
        )
        alerts.append(message)

    # Save the updated product list (with new last_price) back to the file
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(updated_products, f, indent=2)

    # Send all alerts as a single message
    if alerts:
        final_message = "\n\n---\n\n".join(alerts)
        send_telegram_message(final_message)

if __name__ == "__main__":
    main()
