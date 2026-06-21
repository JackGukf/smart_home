# WSL MCP Server Setup
# Run this with "Run with PowerShell" to complete the setup.

$ErrorActionPreference = "Stop"

Write-Host "=== WSL MCP Server Setup ===" -ForegroundColor Cyan

# Step 1: Install mcp package in WSL
Write-Host "`nStep 1: Installing 'mcp' package in WSL Ubuntu-22.04..." -ForegroundColor Yellow
wsl.exe -d Ubuntu-22.04 pip install mcp --break-system-packages
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed. Trying pip3..." -ForegroundColor Yellow
    wsl.exe -d Ubuntu-22.04 pip3 install mcp --break-system-packages
}
Write-Host "  mcp package installed." -ForegroundColor Green

# Step 2: Update Claude Desktop config
Write-Host "`nStep 2: Updating Claude Desktop config..." -ForegroundColor Yellow
$configPath = "$env:APPDATA\Claude\claude_desktop_config.json"
$configDir  = Split-Path $configPath

if (-not (Test-Path $configDir)) { New-Item -ItemType Directory -Path $configDir | Out-Null }

if (Test-Path $configPath) {
    $raw    = Get-Content $configPath -Raw -Encoding UTF8
    $config = $raw | ConvertFrom-Json
} else {
    $config = [PSCustomObject]@{ mcpServers = [PSCustomObject]@{} }
}

if (-not $config.PSObject.Properties['mcpServers']) {
    $config | Add-Member -MemberType NoteProperty -Name 'mcpServers' -Value ([PSCustomObject]@{})
}

$wslServer = [PSCustomObject]@{
    command = "wsl.exe"
    args    = @("-d", "Ubuntu-22.04", "python3",
                "/home/jackgu/workspace/smart-home-rpi4/scripts/wsl_mcp_server.py")
}
$config.mcpServers | Add-Member -MemberType NoteProperty -Name 'wsl-shell' -Value $wslServer -Force

$config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
Write-Host "  Config saved to: $configPath" -ForegroundColor Green

Write-Host "`n=== Setup complete! ===" -ForegroundColor Cyan
Write-Host "Restart Claude Desktop to activate the WSL MCP server." -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to close"
