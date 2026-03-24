# HTB: Pirate

## Target Info
- **IP:** 10.129.244.95
- **OS:** Windows Server 2019 (Build 17763)
- **Domain:** pirate.htb
- **DC Hostname:** DC01.pirate.htb
- **Role:** Active Directory Domain Controller
- **CA:** pirate-DC01-CA (ADCS present)
- **Internal network:** 192.168.100.0/24 (DC01=.1, WEB01=.2)

## Setup
- [x] Add `pirate.htb` and `dc01.pirate.htb` to `/etc/hosts` → 10.129.244.95
- [x] `adfs.pirate.htb` → 192.168.100.2 (WEB01 — ADFS runs here, NOT on DC01)
- [x] Sync clock with DC (`sudo date -s "$(net time -S 10.129.244.95 2>&1)"`)
- [x] BloodHound data collected: `20260228184227_bloodhound.zip`
- [x] Kerberoast hash saved: `kerberoast.txt`
- [x] Ligolo-ng tunnel: DC01 agent → Kali proxy, route 192.168.100.0/24 (user sets up manually)

## Credentials Found
| User               | Password/Hash                           | Source                                                     |
| ------------------ | --------------------------------------- | ---------------------------------------------------------- |
| pentest            | `p3nt3st2025!&`                         | Given in scope, Domain Users only                          |
| **a.white**        | **`E2nvAOKSz5Xz2MJu`**                  | **WEB01 secretsdump — LSA DefaultPassword (autologin)**    |
| **a.white_adm**    | **`Str0ngP@ss99`**                      | **ForceChangePassword via a.white (Session 7)**            |
| YOURPC$            | `Password123!`                          | Machine account we created                                 |
| OLDWWINV$          | `#gI:texb4l!mQm4`                       | Created by ntlmrelayx during RBCD attack                   |
| PIRATEDEV07$       | `P@ssw0rd123!`                          | Created via SAMR during DRS testing                        |
| MS01$              | `ms01`                                  | Pre-Windows 2000 default password (machine name lowercase) |
| EXCH01$            | `exch01`                                | Pre-Windows 2000 default password (machine name lowercase) |
| gMSA_ADCS_prod$    | NT:`304106f739822ea2ad8ebe23f802d078`   | ReadGMSAPassword via MS01$                                 |
| gMSA_ADFS_prod$    | NT:`8126756fb2e69697bfcb04816e685839`   | ReadGMSAPassword via MS01$                                 |
| WEB01$             | NT:`feba09cf0013fbf5834f50def734bca9`   | secretsdump from WEB01                                     |
| WEB01 local Admin  | NT:`b1aac1584c2ea8ed0a9429684e4fc3e5`   | secretsdump from WEB01                                     |
| Administrator (DC) | DCC2:`8baf09ddc5830ac4456ee8639dd89644` | WEB01 cached creds (NOT crackable directly)                |

**Password gotcha:** The `!&` breaks CLI tools. Use **impacket Python directly** or `subprocess.run()` wrappers. Example: `SMBConnection('pirate.htb','10.129.244.95').login('pentest','p3nt3st2025!&')`

**Machine account gotcha:** MS01$/EXCH01$ passwords work but SMB login returns `STATUS_NOLOGON_WORKSTATION_TRUST_ACCOUNT`. Use **Kerberos** instead (impacket-getTGT).

---

## Domain Users
| sAMAccountName | Notes |
|----------------|-------|
| Administrator | Domain/Enterprise/Schema Admin |
| a.white_adm | IT group, SPN: ADFS/a.white, constrained deleg to HTTP/WEB01 |
| a.white | ForceChangePassword on a.white_adm, actively logging in (logonCount=46) |
| j.sparrow | No special perms |
| pentest | Our account — Domain Users only, no group memberships |

## Computer Accounts
| Name | Notes |
|------|-------|
| DC01$ | Domain Controller, unconstrained delegation |
| WEB01$ | 192.168.100.2, target of a.white_adm constrained delegation |
| MS01$ | Member of "Domain Secure Servers" — can ReadGMSAPassword. **Pre-Win2000, pw=ms01** |
| EXCH01$ | In Pre-Windows 2000 group. **pw=exch01** |

## gMSA Accounts
- **gMSA_ADCS_prod$** — Remote Management Users (WinRM on DC01)
- **gMSA_ADFS_prod$** — Remote Management Users (WinRM on DC01)
- Only **Domain Secure Servers** (MS01$) can ReadGMSAPassword (confirmed via msDS-GroupMSAMembership DACL)

---

## Attack Graph (UPDATED — bypass found!)

The original chain through a.white was a rabbit hole. We found a shorter path:

```
ORIGINAL (not needed):
[pentest] ──???──> [a.white] ──ForceChangePassword──> [a.white_adm] ──> ...

ACTUAL PATH TAKEN:
[pentest] ──(enum)──> Pre-Windows 2000 accounts discovered
                            |
                            v
                      [MS01$] pw="ms01" (Pre-Win2000 default)
                            |
                            v  (Kerberos TGT, then ReadGMSAPassword)
                      [gMSA_ADFS_prod$] NT hash obtained
                            |
                            v  (WinRM — Remote Management Users on DC01)
                      DC01 shell → game over
```

### Why this works — step by step:
1. MS01$ is in "Pre-Windows 2000 Compatible Access" → password = "ms01"
2. Machine accounts can't SMB login, but CAN get Kerberos TGTs
3. MS01$ is in "Domain Secure Servers" group → has ReadGMSAPassword permission
4. gMSA_ADFS_prod$ is in Remote Management Users → WinRM to DC01

---

## Exhaustive List: What's Been Tried & Ruled Out

### Authentication Attacks
- [x] Kerberoast a.white_adm (hash in `kerberoast.txt`) — won't crack with rockyou
- [x] AS-REP roasting — no users without preauth
- [x] Password spray ~350+ passwords (seasonal, pirate-themed, name-based, common) against a.white & j.sparrow — nothing
- [x] No lockout (threshold=0) — spraying is safe

### ADCS Attacks
- [x] **CA:** pirate-DC01-CA on DC01.pirate.htb
- [x] **ADFSSSLSigning template** — KEY TEMPLATE:
  - **EnrolleeSuppliesSubject: True** (attacker specifies subject/SAN)
  - Enrollment Rights: **Domain Computers**, Domain Controllers, Domain Admins, Enterprise Admins
  - EKU: Server Authentication ONLY (not Client Auth)
  - No manager approval, no authorized signatures, schema v2
  - Validity: 9999 years
- [x] Got cert with admin UPN BUT **Server Auth EKU only** — can't PKINIT
- [x] Tried `-application-policies 'Client Authentication'` — CA ignores it, still issues Server Auth only
- [x] Schannel LDAPS auth with admin cert — rejected (DC enforces proper cert mapping)
- [x] ESC1-ESC13 checked — no directly exploitable templates for our access level
- [x] **Web enrollment: DISABLED** (HTTP and HTTPS both off) — no ESC8
- [x] `Enforce Encryption for Requests: Enabled` — blocks ESC11
- [x] User Specified SAN: Disabled on CA

### Relay/Coercion Attacks
- [x] Coercion works (DFSCoerce, PetitPotam, PrinterBug all succeed)
- [x] **WEB01 SMB signing NOT REQUIRED** (server-side) — can relay TO WEB01
- [x] DC01 SMB signing IS required
- [x] Both DC01 and WEB01 REQUEST signing as SMB clients → SMB→LDAP relay blocked from both
- [x] LDAP signing NOT enforced (simple bind works) — relay WOULD work if we could get HTTP auth (no signing)
- [x] DC01$ relay to WEB01 SMB: Auth SUCCEEDS but DC01$ is NOT local admin on WEB01
- [x] WEB01 local admins: **Only Administrator and PIRATE\Domain Admins**
- [x] WebClient service on WEB01: Registry exists (Start=2) but NOT properly installed (no Desktop Experience)
- [x] WEB01 CAN reach 10.10.14.40:445 (confirmed Test-NetConnection)
- [x] PetitPotam works against both DC01 and WEB01 (with gMSA hash for WEB01)

### DNS/Network
- [x] ADIDNS injection works — added wildcard `*.pirate.htb → our IP`
- [x] Responder with wildcard DNS — caught NOTHING after several minutes
- [x] DNS zone transfer — denied
- [x] WEB01 at 192.168.100.2 (internal, unreachable)
- **CLEANUP NEEDED:** Delete wildcard DNS record `*` from ADIDNS

### Web/Services
- [x] Port 80: Default IIS page only (all vhosts return same 703-byte page)
- [x] Port 443: Only responds to `adfs.pirate.htb` vhost — ADFS fully alive!
- [x] ADFS on adfs.pirate.htb:443: login page, WS-Trust, OAuth2, WIA (Negotiate), federation metadata
- [x] ADFS WS-Trust usernamemixed: works for auth (confirmed with pentest creds)
- [x] ADFS password spray for a.white: ~50 more passwords tried via WS-Trust, no hits
- [x] ADFS cert auth (certificatemixed): rejected — Server Auth EKU not accepted
- [x] Gobuster with dirb/common.txt + dirbuster medium — nothing on port 80
- [x] Port 2179: open, vmrdp service, not HTTP, no banner

### Shadow Credentials
- [x] msDS-KeyCredentialLink on a.white: **NO controlled account has write access**
- [x] Only Domain Admins, EA, Key Admins (empty), Account Operators (empty) can write it
- [x] Confirmed with DACL analysis + practical pywhisker tests → INSUFF_ACCESS_RIGHTS
- [x] a.white currently has EMPTY msDS-KeyCredentialLink

### Windows Hello Certificate Provisioning
- [x] ADFS Certificate Authority is **DISABLED** (`ModeValue=Disabled` in ServiceSettings XML)
- [x] No cert templates configured for ADFS CA (all nil)
- [x] No issuer certificate exists
- [x] `/adfs/CertificateAuthority`, `/adfs/windowshello` → 503
- [x] `srv_challenge` grant returns nonces, device_code flow with winhello_cert scope works
- [x] Inserted signing cert into ClientJWTSigningKeys, JWT bearer OBO → HTTP 500 (CA module not initialized)
- [x] **Cannot get Client Auth EKU certs through Windows Hello**

### DRS Enrollment (Session 6 deep dive)
- [x] DRS was **NEVER initialized in AD** — no msDS-DeviceRegistrationService object, no RegisteredDevices container
- [x] All `/adfs/EnrollmentServer/*` → 503, all `/EnrollmentServer/*` → 404 (WCF not configured)
- [x] `/adfs/oauth2/deviceregistration` POST → 404 regardless of format
- [x] Tried: REST JSON (AADInternals format), SOAP 1.1/1.2 (MS-DVRE), WS-Trust RST, forged tokens as a.white — ALL fail
- [x] DRS enrollment script at `/home/kali/Desktop/Pirate/drs_enroll.py` (REST, SOAP, direct LDAP methods)
- [x] Token forging works perfectly (x5t `Xc0DX8dOLZIPKCNNDzACneKsFqA`)

### Other
- [x] LAPS — schema not present
- [x] GPP passwords in SYSVOL — nothing
- [x] User descriptions — nothing useful
- [x] ADFS DKM key — **EXTRACTED** as gMSA_ADFS_prod$: `fFtRNXRYzZjwD37MB/Rgu/x96WiVB0xO/SkbWnU6LOQ=`
- [x] BloodHound ACLs from Domain Users/Authenticated Users/Domain Computers — nothing
- [x] PassTheCert (admin cert) — TLS connects but anonymous bind (no actual auth, Server Auth EKU)
- [x] ESC15 check: pKIExtendedKeyUsage == msPKI-Certificate-Application-Policy (both Server Auth) — no discrepancy
- [x] dacledit ACL checks: gMSA accounts have NO write perms on DC01$, WEB01$, Administrator, a.white, domain root
- [x] EXCH01$/MS01$ have NO special group memberships beyond Pre-Windows 2000
- [x] gMSA accounts are NOT CA admins/officers — no ManageCa/ManageCertificates
- [x] ADFS service (ADFSSRV) NOT installed on DC01 — ADFS runs on WEB01, DC01 is just a proxy
- [x] WID (Windows Internal Database) NOT on DC01 — ADFS config is on WEB01
- [x] No scheduled tasks, SYSVOL scripts, PS history, or cached creds found on DC01
- [x] gMSA_ADFS_prod$ SPN: host/adfs.pirate.htb — no delegation configured
- [x] gMSA_ADCS_prod$ — no SPNs, no delegation
- [x] Neither gMSA has SeImpersonate or other useful privileges

---

## CURRENT STATE (SESSION 7): WEB01 OWNED, need DC01 Domain Admin

### SESSION 7 MAJOR WINS
1. **user.txt CAPTURED**: `5fc90264057fda4207981f25728087be`
2. **WEB01 fully compromised** via NTLM relay + RBCD (PetitPotam coerce WEB01 → relay to DC01 LDAP → RBCD → S4U2Proxy → secretsdump)
3. **a.white cleartext password found**: `E2nvAOKSz5Xz2MJu` (LSA DefaultPassword from WEB01 autologin)
4. **ForceChangePassword on a.white_adm**: Changed to `Str0ngP@ss99` — verified working
5. **S4U2Proxy working**: a.white_adm → impersonate Administrator → HTTP/WEB01.pirate.htb (but we already own WEB01)
6. **a.white_adm can write SPN on DC01$** (bloodyAD confirmed — IT group ACL)
7. **RBCD write on DC01 FAILED** — insufficientAccessRights despite bloodyAD showing WRITE

### SESSION 7 DEAD ENDS
- Pirate School Marks Portal: No actual web app exists on WEB01 (just an RP trust config entry)
- Port 1500 on WEB01: ADFS internal WCF service (not a separate app)
- DRS via WID: DeviceAuthentication enabled, Enable-AdfsDeviceRegistration succeeded, but DRS AD objects don't exist (need DA)
- Direct LDAP device registration: Can't create msDS-DeviceContainer (insufficientAccessRights for all accounts)
- a.white/a.white_adm: NOT in Remote Management Users (no WinRM on DC01)
- a.white_adm SMB: Works via Kerberos TGT, LDAP works
- WEB01$ has NO unconstrained delegation, NO special group memberships
- ADCS: certipy found 0 vulnerable templates with a.white, ADFSSSLSigning still Server Auth only

### KEY FINDING: a.white_adm ACLs (bloodyAD)
- **CN=DC01$**: `servicePrincipalName: WRITE` ← KEY ATTACK VECTOR
- **CN=Angela W. ADM (self)**: msDS-AllowedToActOnBehalfOfOtherIdentity: WRITE (RBCD on self, not useful alone)
- Cannot write msDS-AllowedToActOnBehalfOfOtherIdentity on DC01$ (tested, fails)
- Cannot write msDS-AllowedToDelegateTo on self (not in writable list)

### PATH TO DC01 ADMIN — SOLVED: SPN Jacking
**Attack:** IT group has WriteSPN on ALL computer accounts (DC01$, WEB01$, MS01$, EXCH01$)
1. Remove HTTP/WEB01 + HTTP/WEB01.pirate.htb from WEB01$
2. Add http/WEB01 + http/WEB01.pirate.htb to DC01$
3. S4U2Proxy with a.white_adm → HTTP/WEB01 → KDC resolves to DC01$ → ticket encrypted with DC01$ key
4. `-altservice ldap/DC01.pirate.htb` → DCSync as Administrator → full NTDS dump
5. Pass-the-hash with Administrator NTLM → root.txt

**Why it works:** Constrained delegation resolves the target SPN to a computer account at ticket-issuance time. By moving the SPN to DC01$, the S4U2Proxy ticket is encrypted with DC01$'s key. The `-altservice` flag changes the service name in the unencrypted sname field without affecting encryption.

**Ruled out:**
- msDS-AllowedToDelegateTo on a.white_adm: NOT writable (only Key Admins can modify)
- RBCD on DC01$: insufficientAccessRights (bloodyAD false positive)
- ADCS: IT group has NO access to any cert templates
- GPOs: Only default policies exist, IT has no write access

### SESSION 6 FINDINGS (still relevant)
1. **WID full CRUD confirmed** — gMSA_ADFS_prod$ has INSERT/UPDATE/DELETE on ALL tables
2. **Custom RP trust found**: "Pirate School Marks Portal" (WSFed — no real app behind it)
3. **DRS never initialized in AD** — all enrollment endpoints dead (503/404)
4. **ADFS CA disabled** — no WHfB cert provisioning possible
5. **Shadow creds impossible** — no write to msDS-KeyCredentialLink on a.white
6. **a.white SID**: `S-1-5-21-4107424128-4158083573-1300325248-3101`

### Impacket CLI Tools BROKEN
- All impacket-* CLI tools crash: `logger.init() takes from 0 to 1 positional arguments but 2 were given`
- **Workaround:** Use Python API directly, or use evil-winrm/nxc instead

### Infrastructure
- **Ligolo-ng tunnel** active: DC01 agent → Kali proxy (port 8081), TUN `ligolo`, route 192.168.100.0/24
- **WinRM on DC01**: gMSA_ADFS_prod$ and gMSA_ADCS_prod$ (non-admin, Remote Management Users only)
- **WinRM on WEB01**: gMSA_ADFS_prod$ (non-admin)
- **WID database**: read/write access on WEB01 via named pipe `\\.\pipe\MICROSOFT##WID\tsql\query`

### Architecture
- DC01 runs HTTP.SYS (NOT full IIS — no WebAdministration, no WAP module, no ADFS registry keys)
- WEB01 runs actual ADFS service (adfssrv) + WID database + IIS
- ADFS endpoints respond on `adfs.pirate.htb:443` (proxied through DC01)
- ADFS realm: **"Pirate School Corporation"**
- ADFS service account: gMSA_ADFS_prod$ (SID ends in -4108)
- Custom theme: `pirateTheme` in `C:\ADFSTheme\` (just "under construction" banner, no cred harvesting)
- a.white logonCount=46 but **NOT actively logging in** (count unchanged during testing)

### ADFS Artifacts Obtained
- **DKM key**: `fFtRNXRYzZjwD37MB/Rgu/x96WiVB0xO/SkbWnU6LOQ=`
- **Token Signing cert + private key DECRYPTED**: CN=ADFS Signing - adfs.pirate.htb (self-signed RSA)
  - PFX: `/tmp/adfs_signing.pfx` (2541 bytes)
  - Private key: `/tmp/adfs_signing_clean.pem`
  - Certificate: `/tmp/adfs_signing_cert.pem`
  - Thumbprint: `5DCD035FC74E2D920F28234D0F30029DE2AC16A0`
- **Token Encryption cert**: Also in WID (encrypted PFX present, NOT yet decrypted)
  - Thumbprint: `E6B7912B27AE2D53F3DC90A524DAF9CA50ACE33C`
- **ADFS config XML**: `/tmp/adfs_config.xml` (67K bytes ServiceSettingsData)
- **ADFS Issuer**: `http://adfs.pirate.htb/adfs/services/trust`
- **IdToken Issuer**: `https://adfs.pirate.htb/adfs`

### WID Database Contents
**Clients (5):** All built-in, no custom clients
| ClientIdentifier | Name | Type |
|---|---|---|
| 168f3ee4-... | Windows Server Work Folders Client | 2 |
| 38aa3b87-a06d-4817-b275-7a316988d93b | Windows Logon Client | 2 |
| dd762716-... | Device Registration Client | 2 |
| 1DA3723C-... | AllowAllClient | 0 |
| 29d9ed98-... | Token Broker Client | 2 |

**Scopes/RP Trusts (7):** 6 built-in + 1 custom
- SelfScope, ProxyTrustProvisionRelyingParty, Device Registration Service, UserInfo, PRTUpdateRp, Windows Hello - Certificate Provisioning Service
- **Pirate School Marks Portal** (custom) — WSFed=`http://10.10.14.40:8888/callback`, pass-through ALL claims, AllowAllAuthzRule

**Other:** 0 WebApplicationProxyData, 0 ApplicationGroups, 7 standard OAuthPermissions

### WID Database Permissions (Session 6 confirmed)
- **Full CRUD** on ALL 52 tables as gMSA_ADFS_prod$
- Key writable tables: Scopes, Policies, ScopePolicies, ScopeIdentities, ServiceSettings, ServiceStateSummary, Clients, ClientJWTSigningKeys, ProxyTrusts
- **Auto-reload**: Increment SerialNumber in ServiceStateSummary + update LastUpdateTime → ADFS reloads config
- **PollDurationInSeconds**: 300 (5-min for secondary nodes, faster on primary)
- ServiceStateSummary serials: IssuanceScope=6, ServiceSettings=19/v23, FarmNode=55, Client=4

### ADFS Endpoints (all enabled)
- WS-Trust 2005: windowstransport, usernamemixed, certificatemixed, kerberosmixed, issuedtoken
- WS-Trust 1.3: usernamemixed, certificatemixed, kerberosmixed, issuedtoken
- OAuth2: /adfs/oauth2/ (ROPC confirmed working), /adfs/userinfo, device auth, JWKS
- WS-Federation: /adfs/ls/ (passive)
- WAP proxy endpoints: /adfs/proxy/, /adfs/proxy/EstablishTrust/ (enabled but no WAP configured)
- Account lockout: **DISABLED** (threshold=2147483647)

### OAuth2 ROPC Working
- **Windows Logon Client** (`38aa3b87-a06d-4817-b275-7a316988d93b`) accepts ROPC with `scope=openid`
- Successfully obtained JWT for pentest user
- Forged JWT as Administrator with signing key — signs correctly
- But no RP trusts to present the token to

### ADFS Device Registration Service (DRS) — TOKEN WORKS, ENROLLMENT FORMAT UNKNOWN
- **Discovery endpoint works:** `GET /EnrollmentServer/contract?api-version=1.0` returns:
  - RegistrationEndpoint: `https://adfs.pirate.htb/EnrollmentServer/DeviceEnrollmentWebService.svc`
  - RegistrationResourceId: `urn:ms-drs:434DF4A9-3CF2-4C1D-917E-2CD2B72F515A`
  - ServiceVersion: 1.0
  - OAuth2 TokenEndpoint: `https://adfs.pirate.htb/adfs/oauth2/token`
- **Token generation WORKS:** ROPC with `resource=urn:ms-drs:434DF4A9-3CF2-4C1D-917E-2CD2B72F515A` → 200, valid JWT
- **WS-Trust token also works:** `POST /adfs/services/trust/13/usernamemixed` → returns JWT for DRS resource
- **Can forge DRS tokens** as any user using stolen signing key
- **Enrollment endpoint status:**
  - `/EnrollmentServer/DeviceEnrollmentWebService.svc` — WCF service page loads but all POSTs → 404 "Endpoint not found"
  - `/adfs/oauth2/deviceregistration` — **EXISTS** (OPTIONS→200, GET→405, PUT→405) but POST→404 (empty body, ADFS headers)
  - `/adfs/services/deviceregistration` → 503 Service Unavailable
  - Tried: REST JSON, SOAP 1.1, SOAP 1.2, WS-Trust RST with JWT in Security header, form-encoded, various api-versions, various body formats — ALL 404
- **MISSING:** Correct request format/protocol for the final enrollment POST
- **Hint:** "earn your stripes and show up physically" = register a device?

### WEB01 Enumeration Results
- user.txt in `C:\Users\a.white\Desktop\user.txt` — **ACCESS DENIED** as gMSA_ADFS_prod$
- Users: a.white, Administrator, Administrator.PIRATE, gMSA_ADFS_prod$
- No PS history, no stored creds, no custom scheduled tasks
- Can't read a.white's home directory at all
- IIS/ADFS config requires elevation — access denied
- `C:\inetpub` has standard ACLs (gMSA not special)

### Cert store on DC01 (readable as gMSA_ADCS_prod$):
| Subject | HasPrivateKey | EKU | Notes |
|---------|--------------|-----|-------|
| CN=adfs.pirate.htb | True | Server Auth | ADFS SSL cert |
| CN=pirate-DC01-CA | True | None (CA) | Export fails: "Keyset does not exist" |
| CN=DC01.pirate.htb | True | Client Auth + Server Auth | DC cert |

- CA private key: CNG key file, Access DENIED to gMSA accounts
- CA security: Only Administrators/DA/EA have CA Admin/Officer rights

### ADFS AD Container
- `CN=aee666c3-...` — DKM group container (thumbnailPhoto = DKM key) ✓
- `CN=CryptoPolicy,...` — description="EncryptThenMac", OIDs, employeeid=365
- `CN=0bf71fd6-...` — **UNEXPLORED** container, children NOT enumerated

---

## PUZZLE PIECES — WHAT WE HAVE vs WHAT WE NEED

### THE GOAL
1. **user.txt**: `C:\Users\a.white\Desktop\user.txt` on WEB01 → need to become a.white or admin on WEB01
2. **root.txt**: On DC01 → need admin on DC01

### THE CHAIN (from BloodHound)
```
a.white ──ForceChangePassword──> a.white_adm ──ConstrainedDeleg──> HTTP/WEB01 (as any user)
```
- If we get a.white's password → change a.white_adm's password → S4U2Proxy to HTTP/WEB01 as Administrator
- a.white_adm SPN: ADFS/a.white (Kerberoasted but won't crack)

### WHAT WE HAVE
1. ADFS Token Signing private key (can forge SAML/JWT tokens as anyone)
2. WID database write access (can create RP trusts, clients, modify config)
3. WinRM on DC01 (gMSA_ADFS_prod$, gMSA_ADCS_prod$) — non-admin
4. WinRM on WEB01 (gMSA_ADFS_prod$) — non-admin
5. ROPC endpoint works — can test passwords with no lockout
6. Multiple Kerberos TGTs (MS01$, EXCH01$, pentest)
7. gMSA NT hashes for both service accounts

### WHAT WE'RE MISSING
- a.white's password (for ForceChangePassword chain)
- OR admin access on DC01/WEB01 through another path
- OR a way to use the ADFS signing key for privilege escalation

### WEB01 Network Details
- **Full port scan results:** 80, 135, 139, 443, 445, 1500, 49668, 49687
- **SPNs on WEB01$:** HTTP/WEB01, RestrictedKrbHost/WEB01, HOST/WEB01, `tapinego/WEB01`, `tapinego/WEB01.pirate.htb` (unusual!)
- **No hidden shares:** Only ADMIN$, C$, IPC$ — C$ access denied as gMSA
- **DNS:** No adfs or tapinego DNS records in AD zone. Only dc01 and WEB01 A records.

### a.white_adm Details
- **UAC flags:** TRUSTED_TO_AUTH_FOR_DELEGATION (0x1000000)
- **msDS-AllowedToDelegateTo:** `http/WEB01.pirate.htb`, `HTTP/WEB01`
- **SPN:** ADFS/a.white
- **Kerberoast:** $krb5tgs$23$ RC4 hash in kerberoast.txt — NOT CRACKED (rockyou not tried yet, needs gunzip)

### UNEXPLORED ANGLES
- [x] Full port scan on WEB01 — DONE (80,135,139,443,445,1500,49668,49687)
- [x] ADFS event logs on WEB01 — Unauthorized
- [x] C:\inetpub on WEB01 — only default IIS files
- [x] Windows Hello Certificate Provisioning Service — DEAD END (CA disabled)
- [x] DRS enrollment format — DEAD END (DRS never initialized in AD)
- [x] Shadow Credentials on a.white — DEAD END (no write access)
- [x] Kerberoast a.white_adm with rockyou — won't crack
- [x] **NTLM relay to WEB01** — DONE, WEB01 OWNED via RBCD (Session 7)
- [x] **Pirate School Marks Portal** — No web app, just RP trust config (Session 7)
- [x] **Enable DRS via WID** — Enabled config but DRS still broken, no AD objects (Session 7)
- [x] **Direct LDAP device registration** — insufficientAccessRights for all accounts (Session 7)
- [x] Port 1500 on WEB01 — ADFS internal WCF service (Session 7)
- [ ] IIS applicationHost.config on WEB01 — **CAN READ NOW as admin** (need tunnel)
- [ ] ADFS AD container `CN=0bf71fd6-...` children
- [ ] gMSA_ADCS_prod$ on WEB01 (only tried ADFS account)
- [ ] Decrypt ADFS encryption certificate
- [x] **SPN jacking on DC01$ via a.white_adm** — DONE, got Domain Admin (Session 7)
- [x] **a.white_adm constrained delegation + SPN jacking for DC01 access** — DONE (Session 7)

```bash
# Current working commands
evil-winrm -i dc01.pirate.htb -u 'gMSA_ADFS_prod$' -H '8126756fb2e69697bfcb04816e685839'
evil-winrm -i dc01.pirate.htb -u 'gMSA_ADCS_prod$' -H '304106f739822ea2ad8ebe23f802d078'
evil-winrm -i 192.168.100.2 -u 'gMSA_ADFS_prod$' -H '8126756fb2e69697bfcb04816e685839'
printf '%s\n' 'COMMAND' 'exit' | evil-winrm -i 192.168.100.2 -u 'gMSA_ADFS_prod$' -H '8126756fb2e69697bfcb04816e685839' 2>&1 | tail -n +10

# Get TGTs
impacket-getTGT 'pirate.htb/MS01$:ms01' -dc-ip 10.129.244.95
impacket-getTGT 'pirate.htb/EXCH01$:exch01' -dc-ip 10.129.244.95

# Read gMSA passwords
export KRB5CCNAME=MS01\$.ccache
nxc ldap dc01.pirate.htb -k --use-kcache --gmsa
```

---

## Key Commands Reference
```bash
# SMB with special chars (use impacket Python)
python3 -c "from impacket.smbconnection import SMBConnection; c=SMBConnection('pirate.htb','10.129.244.95'); c.login('pentest','p3nt3st2025!&'); print([s['shi1_netname'] for s in c.listShares()])"

# LDAP queries (use ldap3 with NTLM)
python3 -c "import ldap3; s=ldap3.Server('pirate.htb'); c=ldap3.Connection(s,user='PIRATE\\\\pentest',password='p3nt3st2025!&',authentication=ldap3.NTLM); c.bind(); ..."

# Bloodhound (use subprocess wrapper)
python3 -c "import subprocess; subprocess.run(['bloodhound-python','-u','pentest','-p','p3nt3st2025!&','-d','pirate.htb','-ns','10.129.244.95','-c','All','--zip'])"

# Clock sync before Kerberos
sudo date -s "$(net time -S 10.129.244.95 2>&1)"

# Certipy cert request (use machine account)
certipy-ad req -u 'YOURPC$@pirate.htb' -p 'Password123!' -target 10.129.244.95 -ca pirate-DC01-CA -template ADFSSSLSigning -upn administrator@pirate.htb
```

## SESSION 5 KEY HINTS FROM USER
- "earn your stripes and show up physically" — register a device / get physical presence?
- "What's going on with WEB01 and SMB?" — led to SMB signing discovery
- "There is no SMB signing on WEB01. Need some sort of relay."
- "DRSE is enabled, we were able to get a token, we were having trouble on the last hurdle with formatting"
- Linked PetitPotam GitHub — coercion is part of the solution

## Flags
- [x] user.txt: `5fc90264057fda4207981f25728087be` (WEB01, C:\Users\a.white\Desktop\user.txt)
- [x] root.txt: `2dfd4a54ac693a7fe08f8fefce7a2dff` (DC01, C:\Users\Administrator\Desktop\root.txt)

## Final Domain Admin Credentials
| Account | NTLM Hash |
|---------|-----------|
| Administrator | `598295e78bd72d66f837997baf715171` |
| krbtgt | `33071738496aba54a991ccc80875c97e` |
| DC01$ | `230600b8b669ffa1dccf403058170dae` |

## COMPLETE ATTACK CHAIN

```
[pentest] → enum Pre-Windows 2000 accounts
    → [MS01$] pw="ms01" → Kerberos TGT → ReadGMSAPassword
    → [gMSA_ADFS_prod$] → WinRM DC01/WEB01 → WID access → ADFS signing key
    → PetitPotam coerce WEB01 → ntlmrelayx to DC01 LDAP → RBCD on WEB01
    → S4U2Proxy as Administrator → secretsdump WEB01
    → [a.white] pw from LSA DefaultPassword → ForceChangePassword
    → [a.white_adm] → SPN Jacking (WriteSPN on DC01$ via IT group)
        → Remove HTTP/WEB01 from WEB01$, add to DC01$
        → S4U2Proxy -altservice ldap/DC01 → DCSync → Domain Admin
    → root.txt
```

## Session 7 Attack Files
- `/home/kali/Desktop/Pirate/Administrator@cifs_WEB01.pirate.htb@PIRATE.HTB.ccache` — Admin CIFS ticket for WEB01
- `/home/kali/Desktop/Pirate/Administrator@HTTP_WEB01.pirate.htb@PIRATE.HTB.ccache` — Admin HTTP ticket for WEB01
- `/home/kali/Desktop/Pirate/a.white_adm.ccache` — a.white_adm TGT
- `/home/kali/Desktop/Pirate/forge_golden_saml.py` — Golden SAML forging script
- `/tmp/golden_saml_*.xml` — Forged SAML tokens as a.white
- `/tmp/ntlmrelayx_ldap_rbcd.log` — Relay attack log
