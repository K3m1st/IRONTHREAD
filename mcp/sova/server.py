"""
sova-mcp — Reconnaissance tool server for IRONTHREAD.

Wraps standard recon CLI tools (nmap, whatweb, dig, smbclient, ftp)
as MCP tools that Oracle can invoke directly.
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

import subprocess
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import ts as _ts, save_output as _save, run_cmd as _run

server = Server("sova-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="sova_full_scan",
            description="Full TCP port scan with service version detection and default scripts. Wraps: nmap -p- -sC -sV -T4",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP address"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                },
                "required": ["target_ip", "output_dir"],
            },
        ),
        Tool(
            name="sova_whatweb",
            description="Web technology fingerprinting. Wraps: whatweb -a 3",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_url": {"type": "string", "description": "Target URL (e.g. http://10.10.10.10)"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                },
                "required": ["target_url", "output_dir"],
            },
        ),
        Tool(
            name="sova_banner_grab",
            description="Targeted service version detection on a specific port. Wraps: nmap -sV -p{port}",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP address"},
                    "port": {"type": "integer", "description": "Port number to probe"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                },
                "required": ["target_ip", "port", "output_dir"],
            },
        ),
        Tool(
            name="sova_zone_transfer",
            description="Attempt DNS zone transfer. Wraps: dig axfr @target domain",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "DNS server IP"},
                    "domain": {"type": "string", "description": "Domain to query"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                },
                "required": ["target_ip", "domain", "output_dir"],
            },
        ),
        Tool(
            name="sova_null_session",
            description="Test SMB null session / anonymous listing. Wraps: smbclient -N -L //target",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP address"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                },
                "required": ["target_ip", "output_dir"],
            },
        ),
        Tool(
            name="sova_anon_ftp",
            description="Test FTP anonymous login and list files if successful.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP address"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                },
                "required": ["target_ip", "output_dir"],
            },
        ),
        Tool(
            name="sova_udp_scan",
            description="Top UDP port scan with version detection. Wraps: nmap -sU --top-ports N -sV -T4. Requires sudo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP address"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                    "top_ports": {"type": "integer", "description": "Number of top UDP ports to scan", "default": 100},
                },
                "required": ["target_ip", "output_dir"],
            },
        ),
        Tool(
            name="sova_add_hosts",
            description="Add IP-to-hostname mappings to /etc/hosts. Skips duplicates. Requires sudo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IP address to map"},
                    "hostnames": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Hostnames to map to the IP (e.g. ['target.htb', 'portal.target.htb'])",
                    },
                },
                "required": ["ip", "hostnames"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    output_dir = arguments.get("output_dir", ".")
    ts = _ts()

    if name == "sova_full_scan":
        target_ip = arguments["target_ip"]
        cmd = ["nmap", "-p-", "-sC", "-sV", "-T4", target_ip]
        rc, stdout, stderr = _run(cmd, timeout=600)
        raw_file = _save(output_dir, f"sova_full_scan_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "sova_full_scan",
                "target": target_ip,
                "command": " ".join(cmd),
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "sova_whatweb":
        target_url = arguments["target_url"]
        cmd = ["whatweb", "-a", "3", target_url]
        rc, stdout, stderr = _run(cmd, timeout=60)
        raw_file = _save(output_dir, f"sova_whatweb_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "sova_whatweb",
                "target": target_url,
                "command": " ".join(cmd),
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "sova_banner_grab":
        target_ip = arguments["target_ip"]
        port = arguments["port"]
        cmd = ["nmap", "-sV", f"-p{port}", target_ip]
        rc, stdout, stderr = _run(cmd, timeout=60)
        raw_file = _save(output_dir, f"sova_banner_{port}_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "sova_banner_grab",
                "target": target_ip,
                "port": port,
                "command": " ".join(cmd),
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "sova_zone_transfer":
        target_ip = arguments["target_ip"]
        domain = arguments["domain"]
        cmd = ["dig", "axfr", f"@{target_ip}", domain]
        rc, stdout, stderr = _run(cmd, timeout=30)
        raw_file = _save(output_dir, f"sova_zone_transfer_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "sova_zone_transfer",
                "target": target_ip,
                "domain": domain,
                "command": " ".join(cmd),
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "sova_null_session":
        target_ip = arguments["target_ip"]
        cmd = ["smbclient", "-N", "-L", f"//{target_ip}"]
        rc, stdout, stderr = _run(cmd, timeout=30)
        raw_file = _save(output_dir, f"sova_null_session_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "sova_null_session",
                "target": target_ip,
                "command": " ".join(cmd),
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "sova_anon_ftp":
        target_ip = arguments["target_ip"]
        # Use curl for anonymous FTP listing — cleaner than spawning ftp client
        cmd = ["curl", "-s", "--connect-timeout", "10", f"ftp://anonymous:anonymous@{target_ip}/"]
        rc, stdout, stderr = _run(cmd, timeout=30)
        raw_file = _save(output_dir, f"sova_anon_ftp_{ts}.txt", stdout + "\n" + stderr)
        anon_success = rc == 0 and len(stdout.strip()) > 0
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "sova_anon_ftp",
                "target": target_ip,
                "command": " ".join(cmd),
                "return_code": rc,
                "anonymous_login": anon_success,
                "raw_output_file": raw_file,
                "output": stdout if anon_success else "Anonymous login failed or empty listing",
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "sova_udp_scan":
        target_ip = arguments["target_ip"]
        top_ports = arguments.get("top_ports", 100)
        cmd = ["sudo", "nmap", "-sU", "--top-ports", str(top_ports), "-sV", "-T4", target_ip]
        rc, stdout, stderr = _run(cmd, timeout=600)
        raw_file = _save(output_dir, f"sova_udp_scan_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "sova_udp_scan",
                "target": target_ip,
                "command": " ".join(cmd),
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "sova_add_hosts":
        import re
        ip = arguments["ip"]
        hostnames = arguments.get("hostnames", [])

        # Validate IP format
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
            return [TextContent(type="text", text=json.dumps({"error": f"Invalid IP: {ip}"}))]

        # Validate hostnames — alphanumeric, dots, hyphens only
        for h in hostnames:
            if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.\-]+$', h):
                return [TextContent(type="text", text=json.dumps({"error": f"Invalid hostname: {h}"}))]

        if not hostnames:
            return [TextContent(type="text", text=json.dumps({"error": "No hostnames provided"}))]

        # Read current /etc/hosts and check for existing entries
        try:
            with open("/etc/hosts", "r") as f:
                current_hosts = f.read()
        except PermissionError:
            current_hosts = ""

        added = []
        skipped = []
        for h in hostnames:
            if h in current_hosts:
                skipped.append(h)
            else:
                added.append(h)

        if not added:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "tool": "sova_add_hosts",
                    "ip": ip,
                    "added": [],
                    "skipped": skipped,
                    "message": "All hostnames already present in /etc/hosts",
                }),
            )]

        # Build the line and append via sudo tee (stdin, no shell interpolation)
        hosts_line = f"{ip}\t{' '.join(added)}"
        try:
            result = subprocess.run(
                ["sudo", "tee", "-a", "/etc/hosts"],
                input=hosts_line + "\n",
                capture_output=True,
                text=True,
                timeout=10,
            )
            rc, stderr = result.returncode, result.stderr
        except subprocess.TimeoutExpired:
            rc, stderr = -1, "tee timed out after 10s"
        except FileNotFoundError:
            rc, stderr = -1, "sudo or tee not found"

        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "sova_add_hosts",
                "ip": ip,
                "added": added,
                "skipped": skipped,
                "return_code": rc,
                "line_added": hosts_line if rc == 0 else None,
                "errors": stderr if stderr else None,
            }),
        )]

    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
