# Atlassian MCP Setup

This workspace is configured to use Atlassian's official remote MCP server for Jira and Confluence through Codex.

Configuration file:

```text
.codex/config.toml
```

Server entry:

```toml
[mcp_servers.atlassian]
url = "https://mcp.atlassian.com/v1/mcp/authv2"
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"
```

## Authenticate

From this workspace, run:

```powershell
codex mcp login atlassian
```

If Windows blocks the `codex` shim, use the installed Codex binary directly:

```powershell
& 'C:\Users\jackg\AppData\Local\OpenAI\Codex\bin\fb2111b91430cb17\codex.exe' mcp login atlassian
```

Codex should open an Atlassian OAuth flow in your browser. Sign in with the Atlassian account that has access to your personal Jira and Confluence site, then approve the requested access.

After login, restart Codex or start a new thread in this workspace so the new MCP server is loaded.

## Notes

- This uses Atlassian Cloud's remote MCP endpoint: `https://mcp.atlassian.com/v1/mcp/authv2`.
- No Jira or Confluence password, API token, or site credential is stored in this repo.
- MCP tools can read and act with your Atlassian account permissions. The workspace config keeps tool calls in prompt approval mode so you can review actions before they run.
- If your Atlassian admin restricts MCP, OAuth apps, supported domains, or IP allowlists, you may need to approve the Codex client or update Atlassian admin settings.
