"""
noire-mcp — Post-access investigation tool server for IRONTHREAD.

Wraps local enumeration commands as MCP tools that Oracle can invoke
on a remote target via SSH or a command prefix wrapper.
"""

import asyncio
import json
import shlex
import subprocess

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import ts as _ts, save_output as _save

server = Server("noire-mcp")

EXECUTION_CONTEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "method": {
            "type": "string",
            "enum": ["ssh", "shell_command"],
            "description": "Execution method: 'ssh' for SSH connection, 'shell_command' for arbitrary wrapper",
        },
        "ssh_target": {
            "type": "string",
            "description": "SSH target in user@host format (required if method=ssh)",
        },
        "ssh_key": {
            "type": "string",
            "description": "Path to SSH private key (optional, for method=ssh)",
        },
        "command_prefix": {
            "type": "string",
            "description": "Arbitrary command prefix that wraps the tool command (for method=shell_command)",
        },
    },
    "required": ["method"],
}


def _build_remote_cmd(ctx: dict, command: str) -> list[str]:
    """Build the full command list based on execution_context."""
    method = ctx.get("method", "ssh")

    if method == "ssh":
        ssh_target = ctx.get("ssh_target")
        if not ssh_target:
            raise ValueError("ssh_target is required when method=ssh")
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
        ssh_key = ctx.get("ssh_key")
        if ssh_key:
            cmd.extend(["-i", ssh_key])
        cmd.extend([ssh_target, command])
        return cmd

    elif method == "shell_command":
        prefix = ctx.get("command_prefix", "")
        if prefix:
            return ["bash", "-c", f"{prefix} {shlex.quote(command)}"]
        return ["bash", "-c", command]

    else:
        raise ValueError(f"Unknown execution method: {method}")


def _run_remote(ctx: dict, command: str, timeout: int = 60) -> tuple[int, str, str]:
    try:
        cmd = _build_remote_cmd(ctx, command)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except FileNotFoundError as e:
        return -1, "", f"Command not found: {e}"
    except ValueError as e:
        return -1, "", str(e)


def _make_tool(name: str, description: str, extra_props: dict | None = None) -> Tool:
    """Helper to build a Tool with execution_context + output_dir + optional extras."""
    props = {
        "execution_context": EXECUTION_CONTEXT_SCHEMA,
        "output_dir": {"type": "string", "description": "Directory to save raw output"},
    }
    required = ["execution_context", "output_dir"]
    if extra_props:
        for k, v in extra_props.items():
            props[k] = v
            if v.get("required_field"):
                required.append(k)
    return Tool(
        name=name,
        description=description,
        inputSchema={"type": "object", "properties": props, "required": required},
    )


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        _make_tool(
            "noire_system_profile",
            "Collect basic system information: OS, kernel, architecture, current user, groups.",
        ),
        _make_tool(
            "noire_sudo_check",
            "Check sudo privileges for the current user. Wraps: sudo -l",
        ),
        _make_tool(
            "noire_suid_scan",
            "Find all SUID and SGID binaries on the system.",
        ),
        _make_tool(
            "noire_cron_inspect",
            "Inspect cron jobs, cron directories, and systemd timers.",
        ),
        _make_tool(
            "noire_service_enum",
            "Enumerate running processes and active services.",
        ),
        _make_tool(
            "noire_config_harvest",
            "Read specified configuration files from the target.",
            extra_props={
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of absolute file paths to read on the target",
                },
            },
        ),
        _make_tool(
            "noire_writable_paths",
            "Find world-writable and group-writable paths, filtered for noise.",
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    ctx = arguments.get("execution_context", {})
    output_dir = arguments.get("output_dir", ".")
    ts = _ts()

    if name == "noire_system_profile":
        command = "echo '=== uname ===' && uname -a && echo '=== id ===' && id && echo '=== os-release ===' && cat /etc/os-release 2>/dev/null || cat /etc/issue 2>/dev/null && echo '=== hostname ===' && hostname"
        rc, stdout, stderr = _run_remote(ctx, command)
        raw_file = _save(output_dir, f"noire_system_profile_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "noire_system_profile",
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "noire_sudo_check":
        command = "sudo -l 2>&1"
        rc, stdout, stderr = _run_remote(ctx, command)
        raw_file = _save(output_dir, f"noire_sudo_check_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "noire_sudo_check",
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "noire_suid_scan":
        command = "find / -perm -4000 -o -perm -2000 2>/dev/null -type f | head -100"
        rc, stdout, stderr = _run_remote(ctx, command, timeout=120)
        raw_file = _save(output_dir, f"noire_suid_scan_{ts}.txt", stdout + "\n" + stderr)
        binaries = [line.strip() for line in stdout.strip().split("\n") if line.strip()]
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "noire_suid_scan",
                "return_code": rc,
                "raw_output_file": raw_file,
                "suid_sgid_binaries": binaries,
                "count": len(binaries),
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "noire_cron_inspect":
        command = (
            "echo '=== crontab -l ===' && crontab -l 2>&1; "
            "echo '=== /etc/crontab ===' && cat /etc/crontab 2>/dev/null; "
            "echo '=== /etc/cron.d/ ===' && ls -la /etc/cron.d/ 2>/dev/null; "
            "echo '=== /etc/cron.daily/ ===' && ls -la /etc/cron.daily/ 2>/dev/null; "
            "echo '=== /etc/cron.hourly/ ===' && ls -la /etc/cron.hourly/ 2>/dev/null; "
            "echo '=== systemctl timers ===' && systemctl list-timers --no-pager 2>/dev/null"
        )
        rc, stdout, stderr = _run_remote(ctx, command)
        raw_file = _save(output_dir, f"noire_cron_inspect_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "noire_cron_inspect",
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "noire_service_enum":
        command = (
            "echo '=== ps aux ===' && ps aux 2>/dev/null; "
            "echo '=== systemctl units ===' && systemctl list-units --type=service --state=running --no-pager 2>/dev/null; "
            "echo '=== listening ports ===' && ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null"
        )
        rc, stdout, stderr = _run_remote(ctx, command, timeout=30)
        raw_file = _save(output_dir, f"noire_service_enum_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "noire_service_enum",
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "noire_config_harvest":
        paths = arguments.get("paths", [])
        if not paths:
            return [TextContent(
                type="text",
                text=json.dumps({"tool": "noire_config_harvest", "error": "No paths specified"}),
            )]
        # Build a command that cats each file with a header
        parts = []
        for p in paths:
            safe_path = shlex.quote(p)
            parts.append(f"echo '=== {p} ===' && cat {safe_path} 2>&1")
        command = "; ".join(parts)
        rc, stdout, stderr = _run_remote(ctx, command)
        raw_file = _save(output_dir, f"noire_config_harvest_{ts}.txt", stdout + "\n" + stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "noire_config_harvest",
                "paths_requested": paths,
                "return_code": rc,
                "raw_output_file": raw_file,
                "output": stdout,
                "errors": stderr if stderr else None,
            }),
        )]

    elif name == "noire_writable_paths":
        command = (
            "find / -writable -type f 2>/dev/null "
            "| grep -v -E '^/(proc|sys|dev|run|tmp)' "
            "| head -100"
        )
        rc, stdout, stderr = _run_remote(ctx, command, timeout=120)
        raw_file = _save(output_dir, f"noire_writable_paths_{ts}.txt", stdout + "\n" + stderr)
        paths = [line.strip() for line in stdout.strip().split("\n") if line.strip()]
        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": "noire_writable_paths",
                "return_code": rc,
                "raw_output_file": raw_file,
                "writable_paths": paths,
                "count": len(paths),
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
