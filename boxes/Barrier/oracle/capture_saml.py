#!/usr/bin/env python3
"""Capture SAML response using Playwright - intercept via route."""

import sys
import re
import time
from base64 import b64decode
from urllib.parse import unquote, parse_qs
from playwright.sync_api import sync_playwright

GITLAB_URL = "https://gitlab.barrier.vl"
USERNAME = "satoru"
PASSWORD = "dGJ2V72SUEMsM3Ca"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    saml_data = {}

    # Use route to intercept the SAML callback POST
    def intercept_saml(route, request):
        if request.method == "POST":
            pd = request.post_data or ""
            # Parse form data
            params = parse_qs(pd)
            if "SAMLResponse" in params:
                saml_data["b64"] = params["SAMLResponse"][0]
                print(f"\n[!] INTERCEPTED SAMLResponse ({len(saml_data['b64'])} bytes)")
            elif "SAMLResponse" in pd:
                # Try raw extraction
                for part in pd.split("&"):
                    if part.startswith("SAMLResponse="):
                        saml_data["b64"] = unquote(part.split("=", 1)[1])
                        print(f"\n[!] INTERCEPTED SAMLResponse raw ({len(saml_data['b64'])} bytes)")
        # Continue the request
        route.continue_()

    # Intercept requests to the SAML callback
    page.route("**/users/auth/saml/callback*", intercept_saml)

    # Step 1: GitLab sign-in
    print("[*] Navigating to GitLab...")
    page.goto(f"{GITLAB_URL}/users/sign_in", wait_until="networkidle")

    # Step 2: Click SAML button
    print("[*] Clicking SAML login...")
    page.click('button[data-testid="saml-login-button"]')

    # Wait for authentik
    print("[*] Waiting for authentik...")
    page.wait_for_selector('input[name="uidField"]', timeout=15000)
    time.sleep(1)

    # Step 3: Username
    print("[*] Entering username...")
    page.fill('input[name="uidField"]', USERNAME)
    page.click('button[type="submit"]')
    page.wait_for_selector('input[name="password"]', timeout=15000)
    time.sleep(1)

    # Step 4: Password
    print("[*] Entering password...")
    page.fill('input[name="password"]', PASSWORD)
    page.click('button[type="submit"]')

    # Wait for consent page
    print("[*] Waiting for consent...")
    try:
        page.wait_for_url("**/consent**", timeout=15000)
    except:
        time.sleep(3)
    print(f"    URL: {page.url[:80]}...")

    # Handle consent
    if "consent" in page.url:
        time.sleep(2)
        try:
            btn = page.wait_for_selector('button[type="submit"]', timeout=10000)
            print("[*] Clicking consent approve...")
            btn.click()
        except Exception as e:
            print(f"    Consent button error: {e}")

    # Wait for redirect to GitLab (or SAML interception)
    print("[*] Waiting for SAML response...")
    try:
        page.wait_for_url("**gitlab.barrier.vl**", timeout=20000)
    except:
        time.sleep(5)

    print(f"    Final URL: {page.url[:80]}...")

    # Save if captured
    if saml_data.get("b64"):
        saml_b64 = saml_data["b64"]
        saml_xml = b64decode(saml_b64)
        with open("/home/kali/Desktop/IRONTHREAD/boxes/Barrier/oracle/saml_response.b64", "w") as f:
            f.write(saml_b64)
        with open("/home/kali/Desktop/IRONTHREAD/boxes/Barrier/oracle/saml_response.xml", "wb") as f:
            f.write(saml_xml)
        print(f"\n[+] SAML Response saved! ({len(saml_b64)} bytes)")
        nameid_match = re.search(rb'NameID[^>]*>([^<]+)</', saml_xml)
        if nameid_match:
            print(f"    NameID: {nameid_match.group(1).decode()}")
    else:
        print("[-] SAMLResponse not intercepted via route")
        # Try checking page content
        page.screenshot(path="/home/kali/Desktop/IRONTHREAD/boxes/Barrier/oracle/debug_final.png")

    browser.close()
