"""
sova-mcp — Reconnaissance tool server for IRONTHREAD.

Wraps standard recon CLI tools (nmap, whatweb, dig, smbclient, ftp)
as MCP tools that Oracle can invoke directly.
"""

import asyncio
import json
import os
import subprocess
from datetime import datetime, timezone

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("sova-mcp")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _save(output_dir: str, filename: str, content: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"


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

    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
