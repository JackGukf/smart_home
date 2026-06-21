#!/usr/bin/env python3
"""
WSL MCP Server — exposes shell and file tools so Claude can run commands
and read/write files directly inside WSL Ubuntu.

Setup:
  pip install mcp --break-system-packages   (inside WSL)
  Register in .claude/settings.json mcpServers (see project README).
"""

import os
import subprocess
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("WSL Shell")

DEFAULT_WORKDIR = "/home/jackgu/workspace/smart-home-rpi4"


@mcp.tool()
def run_command(command: str, working_dir: str = DEFAULT_WORKDIR) -> str:
    """Run a bash command inside WSL and return combined stdout/stderr + exit code.

    Args:
        command:     Bash command to execute.
        working_dir: Absolute WSL path to run from (default: project root).
    """
    result = subprocess.run(
        ["bash", "-lc", f"cd {working_dir} && {command}"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    parts: list[str] = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr.rstrip()}")
    parts.append(f"[exit {result.returncode}]")
    return "\n".join(parts)


@mcp.tool()
def read_file(path: str) -> str:
    """Read a file from the WSL filesystem.

    Args:
        path: Absolute WSL path to the file.
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file on the WSL filesystem (creates parent dirs).

    Args:
        path:    Absolute WSL path to write.
        content: File content to write.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Written: {path}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
