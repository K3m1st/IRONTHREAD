#!/usr/bin/env python3
"""Register account on CamaleonCMS with manual CAPTCHA solving"""
import requests
import re
import sys
from bs4 import BeautifulSoup

BASE = "http://facts.htb"
s = requests.Session()

# Step 1: Get registration page
r = s.get(f"{BASE}/admin/register")
soup = BeautifulSoup(r.text, "html.parser")
token = soup.find("input", {"name": "authenticity_token"})["value"]

# Step 2: Get CAPTCHA image from same session
captcha_img = s.get(f"{BASE}/captcha?len=5&t=9999999999")
with open("/home/kali/Desktop/IRONTHREAD/boxes/Facts/shared/raw/captcha_session.png", "wb") as f:
    f.write(captcha_img.content)

print(f"[*] CSRF token: {token}")
print(f"[*] CAPTCHA saved to captcha_session.png")
print(f"[*] Session cookies: {dict(s.cookies)}")

# Step 3: Wait for CAPTCHA input
captcha_val = input("[?] Enter CAPTCHA value: ").strip()

# Step 4: Submit registration
data = {
    "authenticity_token": token,
    "user[first_name]": "Oracle",
    "user[last_name]": "Test",
    "user[email]": "oracle@facts.htb",
    "user[username]": "oracletest",
    "user[password]": "P@ssw0rd123!",
    "user[password_confirmation]": "P@ssw0rd123!",
    "captcha": captcha_val,
}

r = s.post(f"{BASE}/admin/register", data=data, allow_redirects=True)
print(f"[*] Status: {r.status_code}")
print(f"[*] Final URL: {r.url}")

if "error" in r.text.lower():
    errors = re.findall(r'<li>(.*?)</li>', r.text)
    for e in errors:
        print(f"[!] Error: {e}")
else:
    print("[+] Registration appears successful!")
    # Save cookies for later use
    print(f"[+] Session cookies: {dict(s.cookies)}")
