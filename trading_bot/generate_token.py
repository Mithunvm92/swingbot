#!/usr/bin/env python3
"""Generate access token from request_token"""
import os
from dotenv import load_dotenv
from kiteconnect import KiteConnect

load_dotenv()

API_KEY = os.getenv("ZERODHA_API_KEY")
API_SECRET = os.getenv("ZERODHA_API_SECRET")
REQUEST_TOKEN = os.getenv("REQUEST_TOKEN")  # Get from kite.login_url()

if not all([API_KEY, API_SECRET, REQUEST_TOKEN]):
    print("Missing: ZERODHA_API_KEY, ZERODHA_API_SECRET, REQUEST_TOKEN in .env")
    exit(1)

kite = KiteConnect(api_key=API_KEY)

print(f"Login URL: {kite.login_url()}")
print(f"\nSet REQUEST_TOKEN in .env, then run again to get access_token")

# Generate access token
if REQUEST_TOKEN:
    data = kite.generate_session(REQUEST_TOKEN, api_secret=API_SECRET)
    access_token = data["access_token"]
    print(f"ACCESS_TOKEN={access_token}")
    print(f"Public Token: {data.get('public_token', 'N/A')}")
