import os
import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import pytz

# ============================================================
#  CONFIG — Reads from GitHub Secrets
# ============================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

RATE_FILE = "last_gold_rate.json"
# ============================================================


# --- CHECK IF WITHIN 9:00 AM - 7:30 PM IST ---
def is_within_operating_hours():
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)
    current_time = now_ist.time()

    start_time = now_ist.replace(hour=9,  minute=0,  second=0).time()
    end_time   = now_ist.replace(hour=19, minute=30, second=0).time()

    print(f"[INFO] Current IST time: {now_ist.strftime('%d %b %Y, %I:%M %p')}")

    if start_time <= current_time <= end_time:
        print("[INFO] Within operating hours (9AM - 7:30PM IST) ✅")
        return True
    else:
        print("[INFO] Outside operating hours. No alert sent. ⏸️")
        return False


# --- LOAD LAST SAVED RATE ---
def load_last_rate():
    try:
        if os.path.exists(RATE_FILE):
            with open(RATE_FILE, "r") as f:
                data = json.load(f)
                return data.get("rate")
    except Exception as e:
        print(f"[WARNING] Could not load last rate: {e}")
    return None


# --- SAVE CURRENT RATE ---
def save_current_rate(rate):
    try:
        with open(RATE_FILE, "w") as f:
            json.dump({
                "rate": rate,
                "updated_at": time.strftime("%d %b %Y, %I:%M %p")
            }, f)
        print(f"[INFO] Rate saved: ₹{rate}")
    except Exception as e:
        print(f"[WARNING] Could not save rate: {e}")


# --- FETCH 22K GOLD RATE from GRT Jewels ---
def get_22k_gold_rate():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        print("[INFO] Opening GRT Jewels page...")
        driver.get("https://www.grtjewels.com/grtlive/")

        wait = WebDriverWait(driver, 15)
        element = wait.until(
            EC.presence_of_element_located((By.ID, "dropdown-basic-button1"))
        )

        full_text = element.text.strip()
        print(f"[INFO] Raw element text: {full_text}")

        for part in full_text.replace(",", "").split():
            cleaned = part.replace("₹", "").strip()
            if cleaned.isdigit() and 5000 < int(cleaned) < 100000:
                return float(cleaned)

        print("[ERROR] Could not parse rate from text.")
        return None

    except Exception as e:
        print(f"[ERROR] Selenium error: {e}")
        return None

    finally:
        if driver:
            driver.quit()
            print("[INFO] Browser closed.")


# --- SEND MESSAGE TO TELEGRAM GROUP ---
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("[✓] Message sent to Telegram Group!")
        else:
            print(f"[ERROR] Telegram error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")


# --- MAIN JOB ---
def gold_rate_job():
    print(f"\n{'='*45}")
    print(f"Running Gold Rate Job...")
    print(f"{'='*45}")

    # Step 1 — Check operating hours
    if not is_within_operating_hours():
        return

    # Step 2 — Fetch current rate
    current_rate = get_22k_gold_rate()
    if not current_rate:
        print("[WARNING] Could not fetch rate. Skipping alert.")
        return

    # Step 3 — Compare with last saved rate
    last_rate = load_last_rate()
    print(f"[INFO] Current rate : ₹{current_rate}")
    print(f"[INFO] Last rate    : ₹{last_rate}")

    # if last_rate is not None and current_rate == last_rate:
    #     print("[INFO] Rate unchanged. No alert sent. ✅")
    #     return

    # Step 4 — Rate changed (or first run) — send alert
    rate_8g = round(current_rate * 8, 2)

    # Show change direction if not first run
    if last_rate is not None:
        change    = round(current_rate - last_rate, 2)
        direction = "📈 Up" if change > 0 else "📉 Down"
        change_line = f"Change : {direction} by ₹{abs(change):,.2f}"
    else:
        change_line = "Change : First reading of the day"

    ist     = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist).strftime("%d %b %Y, %I:%M %p")

    message = (
        f"🪙 *GRT Jewels - Gold Rate Alert*\n"
        f"{'='*25}\n"
        f"📅 Date   : {now_ist}\n\n"
        f"💛 *22K Gold Rate*\n"
        f"  • 1g  : ₹{current_rate:,.2f}\n"
        f"  • 8g  : ₹{rate_8g:,.2f}\n\n"
        f"{change_line}\n\n"
        f"🔗 Source: grtjewels.com/grtlive\n"
        f"_(Excl. GST & making charges)_"
    )

    send_telegram(message)

    # Step 5 — Save new rate
    save_current_rate(current_rate)


# --- RUN ---
gold_rate_job()