#!/usr/bin/env python3
"""Auto-generate access token using Playwright"""
from playwright.sync_api import sync_playwright
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import pyotp
import os
from pathlib import Path

load_dotenv()

API_KEY = os.getenv("ZERODHA_API_KEY")
API_SECRET = os.getenv("ZERODHA_API_SECRET")
USER_ID = os.getenv("ZERODHA_USER_ID")
PASSWORD = os.getenv("ZERODHA_PASSWORD")
TOTP_SECRET = os.getenv("ZERODHA_TOTP_SECRET")

kite = KiteConnect(api_key=API_KEY)
login_url = kite.login_url()

print("Opening browser for login...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    page = browser.new_page()
    page.goto(login_url)
    page.wait_for_load_state("networkidle")

    # Login
    page.fill("#userid", USER_ID)
    page.fill("#password", PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_timeout(2000)

    # TOTP
    totp = pyotp.TOTP(TOTP_SECRET).now()
    page.fill("input[type='text']", totp)
    page.click("button[type='submit']")
    page.wait_for_timeout(5000)

    final_url = page.url
    browser.close()

# Extract request token
from urllib.parse import urlparse, parse_qs
parsed = urlparse(final_url)
request_token = parse_qs(parsed.query)["request_token"][0]

# Generate access token
data = kite.generate_session(request_token, api_secret=API_SECRET)
access_token = data["access_token"]

print(f"\nACCESS TOKEN:\n{access_token}")

# Update .env
env_path = Path(__file__).parent / ".env"
updated = False

if env_path.exists():
    lines = env_path.read_text().splitlines(keepends=True)
    with open(env_path, "w") as f:
        for line in lines:
            if line.startswith("ACCESS_TOKEN="):
                f.write(f"ACCESS_TOKEN={access_token}\n")
                updated = True
            else:
                f.write(line)
        if not updated:
            f.write(f"\nACCESS_TOKEN={access_token}\n")

print("\n.env updated!")
