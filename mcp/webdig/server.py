"""
webdig-mcp — Web enumeration tool server for IRONTHREAD.

Wraps web enumeration CLI tools (gobuster, ffuf, whatweb, curl)
as MCP tools that Oracle can invoke directly.
"""

import asyncio
import json
import re

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import ts as _ts, save_output as _save, run_cmd as _run

server = Server("webdig-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="webdig_dir_bust",
            description="Directory/file brute-force enumeration. Wraps: gobuster dir",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_url": {"type": "string", "description": "Target URL (e.g. http://10.10.10.10:8080)"},
                    "wordlist": {"type": "string", "description": "Path to wordlist file"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                    "extensions": {"type": "string", "description": "Comma-separated file extensions (e.g. php,html,txt)"},
                },
                "required": ["target_url", "wordlist", "output_dir"],
            },
        ),
        Tool(
            name="webdig_vhost_fuzz",
            description="Virtual host discovery via Host header fuzzing. Wraps: ffuf -H 'Host: FUZZ.domain'",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_url": {"type": "string", "description": "Target URL (e.g. http://10.10.10.10)"},
                    "domain": {"type": "string", "description": "Base domain (e.g. target.htb)"},
                    "wordlist": {"type": "string", "description": "Path to wordlist file"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                },
                "required": ["target_url", "domain", "wordlist", "output_dir"],
            },
        ),
        Tool(
            name="webdig_curl",
            description="HTTP request with full control over method, headers, and data. Wraps: curl",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Request URL"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                    "method": {"type": "string", "description": "HTTP method (GET, POST, PUT, etc.)", "default": "GET"},
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Headers as 'Key: Value' strings",
                    },
                    "data": {"type": "string", "description": "Request body data"},
                },
                "required": ["url", "output_dir"],
            },
        ),
        Tool(
            name="webdig_js_review",
            description="Download JavaScript files from a URL and extract endpoints, API paths, secrets, and comments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_url": {"type": "string", "description": "URL to a JS file or page to scan for JS references"},
                    "output_dir": {"type": "string", "description": "Directory to save raw output"},
                },
                "required": ["target_url", "output_dir"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    output_dir = arguments.get("output_dir", ".")
    ts = _ts()

    if name == "webdig_dir_bust":
        target_url = arguments["target_url"]
        wordlist = arguments["wordlist"]
        extensions = arguments.get("extensions")
        cmd = ["gobuster", "dir", "-u", target_url, "-w", wordlist, "-q", "--no-color"]
        if extensions:
            cmd.extend(["-x", extensions])
        rc, stdout, stderr = _run(cmd, timeout=300)
        raw_file = _save(output_dir, f"webdig_dirbust_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "webdig_dir_bust",
                "target": target_url,
                "wordlist": wordlist,
                "extensions": extensions,
                "command": " ".join(cmd),
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "webdig_vhost_fuzz":
        target_url = arguments["target_url"]
        domain = arguments["domain"]
        wordlist = arguments["wordlist"]
        cmd = [
            "ffuf", "-u", target_url,
            "-H", f"Host: FUZZ.{domain}",
            "-w", wordlist,
            "-mc", "all",
            "-fc", "301,302",
            "-ac",  # auto-calibrate to filter wildcard responses
        ]
        rc, stdout, stderr = _run(cmd, timeout=300)
        raw_file = _save(output_dir, f"webdig_vhost_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "webdig_vhost_fuzz",
                "target": target_url,
                "domain": domain,
                "wordlist": wordlist,
                "command": " ".join(cmd),
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "webdig_curl":
        url = arguments["url"]
        method = arguments.get("method", "GET")
        headers = arguments.get("headers", [])
        data = arguments.get("data")
        cmd = ["curl", "-s", "-i", "-X", method]
        for h in headers:
            cmd.extend(["-H", h])
        if data:
            cmd.extend(["-d", data])
        cmd.append(url)
        rc, stdout, stderr = _run(cmd, timeout=30)
        raw_file = _save(output_dir, f"webdig_curl_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "webdig_curl",
                "url": url,
                "method": method,
                "command": " ".join(cmd),
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "webdig_js_review":
        target_url = arguments["target_url"]
        # Download the page/JS file
        cmd = ["curl", "-s", target_url]
        rc, stdout, stderr = _run(cmd, timeout=30)

        if rc != 0:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "tool": "webdig_js_review",
                    "target": target_url,
                    "error": f"Failed to download: {stderr}",
                }),
            )]

        js_content = stdout

        # Extract potentially interesting patterns
        endpoints = list(set(re.findall(r'["\'](/[a-zA-Z0-9_/\-\.]+)["\']', js_content)))
        api_paths = [e for e in endpoints if any(k in e.lower() for k in ["api", "v1", "v2", "graphql", "rest"])]
        secrets_patterns = re.findall(
            r'(?:api[_-]?key|token|secret|password|auth|bearer)\s*[:=]\s*["\']([^"\']+)["\']',
            js_content,
            re.IGNORECASE,
        )
        comments = re.findall(r'//.*?$|/\*.*?\*/', js_content, re.MULTILINE | re.DOTALL)

        raw_file = _save(output_dir, f"webdig_js_raw_{ts}.txt", js_content)
        analysis_content = json.dumps({
            "endpoints": sorted(endpoints),
            "api_paths": sorted(api_paths),
            "potential_secrets": secrets_patterns,
            "comments_found": len(comments),
        }, indent=2)
        analysis_file = _save(output_dir, f"webdig_js_analysis_{ts}.json", analysis_content)

        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "webdig_js_review",
                "target": target_url,
                "raw_output_file": raw_file,
                "analysis_file": analysis_file,
                "endpoints_found": len(endpoints),
                "api_paths": api_paths,
                "potential_secrets_found": len(secrets_patterns),
                "comments_found": len(comments),
                "endpoints": sorted(endpoints)[:50],  # cap at 50 for response size
            }),
        )]

    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
