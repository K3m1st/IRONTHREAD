"""
wintools-mcp — Windows/AD enumeration tool server for IRONTHREAD.

Wraps Windows reconnaissance CLI tools (nxc, impacket, rpcclient,
ldapsearch, bloodhound-python, kerbrute) as MCP tools. All tools run
FROM the attacker box against the target — no session required.
"""

import asyncio
import json
import glob as _glob
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import ts as _ts, save_output as _save, run_cmd as _run, truncate_output as _trunc

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("wintools-mcp")


# ---------------------------------------------------------------------------
# Shared credential schema properties (reused across tools)
# ---------------------------------------------------------------------------

_CRED_PROPS = {
    "username": {"type": "string", "description": "Username for authentication"},
    "password": {"type": "string", "description": "Password for authentication"},
    "domain": {"type": "string", "description": "AD domain (e.g. htb.local)"},
    "hashes": {"type": "string", "description": "NTLM hash for pass-the-hash (LM:NT format)"},
}


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, default=str))]


def _result(tool: str, target: str, cmd: list[str], rc: int,
            raw_file: str, output: str, stderr: str) -> list[TextContent]:
    """Standard tool response with output truncation."""
    return _ok({
        "tool": tool,
        "target": target,
        "command": " ".join(cmd),
        "return_code": rc,
        "raw_output_file": raw_file,
        "output": _trunc(output),
        "errors": stderr if stderr else None,
    })


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="wintools_smb_enum",
            description=(
                "SMB enumeration via NetExec. Returns OS info, signing status, "
                "shares, and more. Works with null session (no creds) or authenticated. "
                "Wraps: nxc smb"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP address"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                    **_CRED_PROPS,
                    "options": {"type": "string", "description": "Extra nxc flags (e.g. --shares, --users, --groups)"},
                },
                "required": ["target_ip", "output_dir"],
            },
        ),
        Tool(
            name="wintools_rpc_enum",
            description=(
                "RPC enumeration via rpcclient. Common commands: enumdomusers, "
                "enumdomgroups, querydispinfo, querydominfo, enumprivs. "
                "Works with null session (no creds) or authenticated."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP address"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                    "rpc_command": {"type": "string", "description": "rpcclient command to execute", "default": "enumdomusers"},
                    **_CRED_PROPS,
                },
                "required": ["target_ip", "output_dir"],
            },
        ),
        Tool(
            name="wintools_ldap_query",
            description=(
                "LDAP query via ldapsearch. Works with anonymous bind (no creds) "
                "or authenticated. Returns truncated output — full results saved to file."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP / domain controller"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                    "base_dn": {"type": "string", "description": "Base DN (e.g. DC=htb,DC=local)"},
                    "filter": {"type": "string", "description": "LDAP filter", "default": "(objectClass=*)"},
                    "attributes": {"type": "string", "description": "Space-separated attributes to return"},
                    **_CRED_PROPS,
                },
                "required": ["target_ip", "output_dir", "base_dn"],
            },
        ),
        Tool(
            name="wintools_bloodhound",
            description=(
                "BloodHound data collection via bloodhound-python. Collects AD "
                "relationships and outputs a zip for analysis. Optionally auto-ingests "
                "into neo4j via bloodhound-import. Standard practice on every Windows box."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Domain controller IP (used as nameserver)"},
                    "output_dir": {"type": "string", "description": "Directory to save collection zip"},
                    "domain": {"type": "string", "description": "AD domain (e.g. htb.local)"},
                    "username": {"type": "string", "description": "Domain username"},
                    "password": {"type": "string", "description": "Domain password"},
                    "collection": {"type": "string", "description": "Collection method", "default": "all"},
                    "neo4j_ingest": {"type": "boolean", "description": "Auto-ingest into neo4j", "default": True},
                    "neo4j_uri": {"type": "string", "description": "Neo4j bolt URI", "default": "bolt://localhost:7687"},
                    "neo4j_user": {"type": "string", "description": "Neo4j username", "default": "neo4j"},
                    "neo4j_password": {"type": "string", "description": "Neo4j password", "default": "neo4j"},
                },
                "required": ["target_ip", "output_dir", "domain", "username", "password"],
            },
        ),
        Tool(
            name="wintools_kerberoast",
            description=(
                "Kerberoasting via impacket GetUserSPNs. Requests TGS tickets for "
                "service accounts — output is hashcat-ready (mode 13100)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Domain controller IP"},
                    "output_dir": {"type": "string", "description": "Directory to save hashes"},
                    "domain": {"type": "string", "description": "AD domain"},
                    "username": {"type": "string", "description": "Domain username"},
                    "password": {"type": "string", "description": "Domain password"},
                    "hashes": {"type": "string", "description": "NTLM hash for PtH (LM:NT)"},
                    "dc_ip": {"type": "string", "description": "Explicit DC IP (defaults to target_ip)"},
                },
                "required": ["target_ip", "output_dir", "domain", "username"],
            },
        ),
        Tool(
            name="wintools_asreproast",
            description=(
                "AS-REP Roasting via impacket GetNPUsers. Finds accounts with "
                "Kerberos pre-auth disabled — output is hashcat-ready (mode 18200). "
                "Can run without creds if a usersfile is provided."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Domain controller IP"},
                    "output_dir": {"type": "string", "description": "Directory to save hashes"},
                    "domain": {"type": "string", "description": "AD domain"},
                    "username": {"type": "string", "description": "Domain username (optional if usersfile provided)"},
                    "password": {"type": "string", "description": "Domain password"},
                    "usersfile": {"type": "string", "description": "Path to file with usernames (one per line)"},
                    "dc_ip": {"type": "string", "description": "Explicit DC IP (defaults to target_ip)"},
                },
                "required": ["target_ip", "output_dir", "domain"],
            },
        ),
        Tool(
            name="wintools_kerbrute",
            description=(
                "Kerberos user enumeration and password spraying via kerbrute. "
                "Modes: userenum (find valid users), passwordspray (one password vs many users), "
                "bruteuser (many passwords vs one user)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Domain controller IP"},
                    "output_dir": {"type": "string", "description": "Directory to save results"},
                    "domain": {"type": "string", "description": "AD domain"},
                    "mode": {
                        "type": "string",
                        "description": "Attack mode",
                        "enum": ["userenum", "passwordspray", "bruteuser"],
                    },
                    "userlist": {"type": "string", "description": "Path to username list (userenum/passwordspray)"},
                    "password": {"type": "string", "description": "Password to spray (passwordspray mode)"},
                    "username": {"type": "string", "description": "Target username (bruteuser mode)"},
                    "passwords_file": {"type": "string", "description": "Path to password list (bruteuser mode)"},
                },
                "required": ["target_ip", "output_dir", "domain", "mode"],
            },
        ),
        Tool(
            name="wintools_sam_dump",
            description=(
                "Dump SAM hashes, LSA secrets, and cached credentials via impacket "
                "secretsdump. Requires admin-level credentials. Supports pass-the-hash. "
                "Output can be large — truncated in response, full results saved to file."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP address"},
                    "output_dir": {"type": "string", "description": "Directory to save output"},
                    "username": {"type": "string", "description": "Admin username"},
                    "password": {"type": "string", "description": "Password"},
                    "hashes": {"type": "string", "description": "NTLM hash for PtH (LM:NT)"},
                    "domain": {"type": "string", "description": "Domain (empty for local)", "default": ""},
                    "dc_ip": {"type": "string", "description": "Explicit DC IP"},
                },
                "required": ["target_ip", "output_dir", "username"],
            },
        ),
        Tool(
            name="wintools_nxc",
            description=(
                "General-purpose NetExec wrapper. Use for any nxc module or protocol "
                "not covered by specialized tools. Pass extra flags via 'options' "
                "(e.g. '--shares', '--sam', '-M spider_plus'). "
                "Protocols: smb, ldap, winrm, rdp, mssql, ssh."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP address"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                    "protocol": {
                        "type": "string",
                        "description": "Protocol to use",
                        "enum": ["smb", "ldap", "winrm", "rdp", "mssql", "ssh"],
                    },
                    **_CRED_PROPS,
                    "options": {"type": "string", "description": "Extra nxc flags and modules"},
                },
                "required": ["target_ip", "output_dir", "protocol"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    output_dir = arguments.get("output_dir", ".")
    timestamp = _ts()

    if name == "wintools_smb_enum":
        return _handle_smb_enum(arguments, output_dir, timestamp)
    elif name == "wintools_rpc_enum":
        return _handle_rpc_enum(arguments, output_dir, timestamp)
    elif name == "wintools_ldap_query":
        return _handle_ldap_query(arguments, output_dir, timestamp)
    elif name == "wintools_bloodhound":
        return _handle_bloodhound(arguments, output_dir, timestamp)
    elif name == "wintools_kerberoast":
        return _handle_kerberoast(arguments, output_dir, timestamp)
    elif name == "wintools_asreproast":
        return _handle_asreproast(arguments, output_dir, timestamp)
    elif name == "wintools_kerbrute":
        return _handle_kerbrute(arguments, output_dir, timestamp)
    elif name == "wintools_sam_dump":
        return _handle_sam_dump(arguments, output_dir, timestamp)
    elif name == "wintools_nxc":
        return _handle_nxc(arguments, output_dir, timestamp)
    else:
        return _ok({"error": f"Unknown tool: {name}"})


# -- wintools_smb_enum -------------------------------------------------------

def _handle_smb_enum(args: dict, output_dir: str, ts: str) -> list[TextContent]:
    target_ip = args["target_ip"]
    cmd = ["nxc", "smb", target_ip]

    username = args.get("username")
    password = args.get("password")
    domain = args.get("domain")
    hashes = args.get("hashes")

    if username:
        cmd += ["-u", username]
        if password:
            cmd += ["-p", password]
        elif hashes:
            cmd += ["-H", hashes]
        else:
            cmd += ["-p", ""]
    if domain:
        cmd += ["-d", domain]

    options = args.get("options", "")
    if options:
        cmd += options.split()

    rc, stdout, stderr = _run(cmd, timeout=120)
    raw_file = _save(output_dir, f"wintools_smb_enum_{ts}.txt", stdout + "\n" + stderr)
    return _result("wintools_smb_enum", target_ip, cmd, rc, raw_file, stdout, stderr)


# -- wintools_rpc_enum -------------------------------------------------------

def _handle_rpc_enum(args: dict, output_dir: str, ts: str) -> list[TextContent]:
    target_ip = args["target_ip"]
    rpc_command = args.get("rpc_command", "enumdomusers")
    username = args.get("username")
    password = args.get("password")
    domain = args.get("domain")

    if username and password:
        auth = f"{domain + '/' if domain else ''}{username}%{password}"
        cmd = ["rpcclient", "-U", auth, target_ip, "-c", rpc_command]
    else:
        cmd = ["rpcclient", "-U", "", "-N", target_ip, "-c", rpc_command]

    rc, stdout, stderr = _run(cmd, timeout=60)
    raw_file = _save(output_dir, f"wintools_rpc_enum_{ts}.txt", stdout + "\n" + stderr)
    return _result("wintools_rpc_enum", target_ip, cmd, rc, raw_file, stdout, stderr)


# -- wintools_ldap_query -----------------------------------------------------

def _handle_ldap_query(args: dict, output_dir: str, ts: str) -> list[TextContent]:
    target_ip = args["target_ip"]
    base_dn = args["base_dn"]
    ldap_filter = args.get("filter", "(objectClass=*)")
    attributes = args.get("attributes", "")
    username = args.get("username")
    password = args.get("password")
    domain = args.get("domain")

    cmd = ["ldapsearch", "-x", "-H", f"ldap://{target_ip}", "-b", base_dn]

    if username and password:
        bind_dn = f"{domain}\\{username}" if domain else username
        cmd += ["-D", bind_dn, "-w", password]

    cmd.append(ldap_filter)
    if attributes:
        cmd += attributes.split()

    rc, stdout, stderr = _run(cmd, timeout=120)
    raw_file = _save(output_dir, f"wintools_ldap_query_{ts}.txt", stdout + "\n" + stderr)
    return _result("wintools_ldap_query", target_ip, cmd, rc, raw_file, stdout, stderr)


# -- wintools_bloodhound -----------------------------------------------------

def _handle_bloodhound(args: dict, output_dir: str, ts: str) -> list[TextContent]:
    target_ip = args["target_ip"]
    domain = args["domain"]
    username = args["username"]
    password = args["password"]
    collection = args.get("collection", "all")
    neo4j_ingest = args.get("neo4j_ingest", True)

    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "bloodhound-python",
        "-d", domain,
        "-u", username,
        "-p", password,
        "-ns", target_ip,
        "-c", collection,
        "--zip",
        "--output-prefix", f"bh_{ts}",
    ]

    rc, stdout, stderr = _run(cmd, timeout=300)
    raw_file = _save(output_dir, f"wintools_bloodhound_{ts}.txt", stdout + "\n" + stderr)

    # Find the generated zip file
    zip_files = _glob.glob(os.path.join(os.getcwd(), f"bh_{ts}*.zip"))
    zip_path = None
    if zip_files:
        zip_path = zip_files[0]
        # Move zip to output_dir
        dest = os.path.join(output_dir, os.path.basename(zip_path))
        os.rename(zip_path, dest)
        zip_path = dest

    # Best-effort neo4j ingest
    ingest_status = "skipped"
    ingest_error = None
    if neo4j_ingest and zip_path:
        neo4j_uri = args.get("neo4j_uri", "bolt://localhost:7687")
        neo4j_user = args.get("neo4j_user", "neo4j")
        neo4j_password = args.get("neo4j_password", "neo4j")
        try:
            ingest_cmd = [
                "bloodhound-import",
                "-du", neo4j_uri,
                "-un", neo4j_user,
                "-up", neo4j_password,
                zip_path,
            ]
            ingest_rc, ingest_out, ingest_err = _run(ingest_cmd, timeout=120)
            ingest_status = "success" if ingest_rc == 0 else "failed"
            if ingest_rc != 0:
                ingest_error = ingest_err or ingest_out
        except Exception as e:
            ingest_status = "failed"
            ingest_error = str(e)

    return _ok({
        "tool": "wintools_bloodhound",
        "target": target_ip,
        "domain": domain,
        "collection": collection,
        "return_code": rc,
        "raw_output_file": raw_file,
        "zip_file": zip_path,
        "neo4j_ingest": ingest_status,
        "neo4j_ingest_error": ingest_error,
        "output": _trunc(stdout),
        "errors": stderr if stderr else None,
    })


# -- wintools_kerberoast -----------------------------------------------------

def _handle_kerberoast(args: dict, output_dir: str, ts: str) -> list[TextContent]:
    target_ip = args["target_ip"]
    domain = args["domain"]
    username = args["username"]
    password = args.get("password")
    hashes = args.get("hashes")
    dc_ip = args.get("dc_ip", target_ip)

    os.makedirs(output_dir, exist_ok=True)
    hash_file = os.path.join(output_dir, f"kerberoast_{ts}.txt")

    identity = f"{domain}/{username}"
    if password:
        identity += f":{password}"

    cmd = ["impacket-GetUserSPNs", identity, "-dc-ip", dc_ip, "-request", "-outputfile", hash_file]

    if hashes and not password:
        cmd += ["-hashes", hashes]
    if not password and not hashes:
        cmd.append("-no-pass")

    rc, stdout, stderr = _run(cmd, timeout=120)
    raw_file = _save(output_dir, f"wintools_kerberoast_{ts}.txt", stdout + "\n" + stderr)

    # Count recovered hashes
    hash_count = 0
    if os.path.exists(hash_file):
        with open(hash_file) as f:
            hash_count = sum(1 for line in f if line.strip().startswith("$krb5tgs$"))

    return _ok({
        "tool": "wintools_kerberoast",
        "target": target_ip,
        "domain": domain,
        "command": " ".join(cmd),
        "return_code": rc,
        "raw_output_file": raw_file,
        "hash_file": hash_file if hash_count > 0 else None,
        "hash_count": hash_count,
        "hashcat_mode": 13100,
        "output": _trunc(stdout),
        "errors": stderr if stderr else None,
    })


# -- wintools_asreproast -----------------------------------------------------

def _handle_asreproast(args: dict, output_dir: str, ts: str) -> list[TextContent]:
    target_ip = args["target_ip"]
    domain = args["domain"]
    username = args.get("username")
    password = args.get("password")
    usersfile = args.get("usersfile")
    dc_ip = args.get("dc_ip", target_ip)

    os.makedirs(output_dir, exist_ok=True)
    hash_file = os.path.join(output_dir, f"asreproast_{ts}.txt")

    if username and password:
        identity = f"{domain}/{username}:{password}"
    elif username:
        identity = f"{domain}/{username}"
    else:
        identity = f"{domain}/"

    cmd = ["impacket-GetNPUsers", identity, "-dc-ip", dc_ip, "-request",
           "-format", "hashcat", "-outputfile", hash_file]

    if usersfile:
        cmd += ["-usersfile", usersfile]
    if not password:
        cmd.append("-no-pass")

    rc, stdout, stderr = _run(cmd, timeout=120)
    raw_file = _save(output_dir, f"wintools_asreproast_{ts}.txt", stdout + "\n" + stderr)

    hash_count = 0
    if os.path.exists(hash_file):
        with open(hash_file) as f:
            hash_count = sum(1 for line in f if line.strip().startswith("$krb5asrep$"))

    return _ok({
        "tool": "wintools_asreproast",
        "target": target_ip,
        "domain": domain,
        "command": " ".join(cmd),
        "return_code": rc,
        "raw_output_file": raw_file,
        "hash_file": hash_file if hash_count > 0 else None,
        "hash_count": hash_count,
        "hashcat_mode": 18200,
        "output": _trunc(stdout),
        "errors": stderr if stderr else None,
    })


# -- wintools_kerbrute -------------------------------------------------------

def _handle_kerbrute(args: dict, output_dir: str, ts: str) -> list[TextContent]:
    target_ip = args["target_ip"]
    domain = args["domain"]
    mode = args["mode"]

    cmd = ["kerbrute", mode, "--dc", target_ip, "-d", domain]

    if mode == "userenum":
        userlist = args.get("userlist")
        if not userlist:
            return _ok({"error": "userenum mode requires 'userlist' parameter"})
        cmd.append(userlist)

    elif mode == "passwordspray":
        userlist = args.get("userlist")
        password = args.get("password")
        if not userlist or not password:
            return _ok({"error": "passwordspray mode requires 'userlist' and 'password' parameters"})
        cmd += [userlist, "-p", password]

    elif mode == "bruteuser":
        username = args.get("username")
        passwords_file = args.get("passwords_file")
        if not username or not passwords_file:
            return _ok({"error": "bruteuser mode requires 'username' and 'passwords_file' parameters"})
        cmd += ["--username", username, passwords_file]

    rc, stdout, stderr = _run(cmd, timeout=300)
    raw_file = _save(output_dir, f"wintools_kerbrute_{mode}_{ts}.txt", stdout + "\n" + stderr)
    return _result("wintools_kerbrute", target_ip, cmd, rc, raw_file, stdout, stderr)


# -- wintools_sam_dump -------------------------------------------------------

def _handle_sam_dump(args: dict, output_dir: str, ts: str) -> list[TextContent]:
    target_ip = args["target_ip"]
    username = args["username"]
    password = args.get("password")
    hashes = args.get("hashes")
    domain = args.get("domain", "")
    dc_ip = args.get("dc_ip")

    prefix = f"{domain + '/' if domain else ''}{username}"
    if password:
        prefix += f":{password}"

    cmd = ["impacket-secretsdump", f"{prefix}@{target_ip}"]

    if hashes and not password:
        cmd += ["-hashes", hashes]
    if not password and not hashes:
        cmd.append("-no-pass")
    if dc_ip:
        cmd += ["-dc-ip", dc_ip]

    rc, stdout, stderr = _run(cmd, timeout=180)
    raw_file = _save(output_dir, f"wintools_sam_dump_{ts}.txt", stdout + "\n" + stderr)
    return _result("wintools_sam_dump", target_ip, cmd, rc, raw_file, stdout, stderr)


# -- wintools_nxc ------------------------------------------------------------

def _handle_nxc(args: dict, output_dir: str, ts: str) -> list[TextContent]:
    target_ip = args["target_ip"]
    protocol = args["protocol"]

    cmd = ["nxc", protocol, target_ip]

    username = args.get("username")
    password = args.get("password")
    hashes = args.get("hashes")
    domain = args.get("domain")

    if username:
        cmd += ["-u", username]
        if password:
            cmd += ["-p", password]
        elif hashes:
            cmd += ["-H", hashes]
        else:
            cmd += ["-p", ""]
    if domain:
        cmd += ["-d", domain]

    options = args.get("options", "")
    if options:
        cmd += options.split()

    rc, stdout, stderr = _run(cmd, timeout=120)
    raw_file = _save(output_dir, f"wintools_nxc_{protocol}_{ts}.txt", stdout + "\n" + stderr)
    return _result("wintools_nxc", target_ip, cmd, rc, raw_file, stdout, stderr)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
