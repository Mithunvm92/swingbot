#!/usr/bin/env python3
"""Generate access token from request_token"""
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("ZERODHA_API_KEY")
api_secret = os.getenv("ZERODHA_API_SECRET")

kite = KiteConnect(api_key=api_key)

print("\nOpen this URL in browser and login:\n")
print(kite.login_url())

request_token = input("\nPaste request_token here: ").strip()

data = kite.generate_session(
    request_token,
    api_secret=api_secret
)

access_token = data["access_token"]

print("\n==============================")
print("ACCESS TOKEN:")
print(access_token)
print("==============================\n")
