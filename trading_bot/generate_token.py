#!/usr/bin/env python3
"""Auto-generate access token using Playwright"""
from playwright.sync_api import sync_playwright
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import pyotp
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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

    # Wait for TOTP
    page.wait_for_timeout(5000)

    # Generate TOTP
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print("Generated TOTP:", totp)

    # Fill OTP
    page.locator("input").last.fill(totp)
    page.wait_for_timeout(2000)

    # Submit OTP
    page.locator("button").last.click()

    # Wait for redirect
    page.wait_for_timeout(8000)

    final_url = page.url
    print("Final URL:", final_url)

    # Extract request token
    parsed = urlparse(final_url)
    query = parse_qs(parsed.query)
    request_token = query["request_token"][0]
    print("Request Token:", request_token)

    browser.close()

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
