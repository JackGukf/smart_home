param(
    [string]$PiHost = "192.168.0.234",
    [string]$PiUser = "orangepi",
    [string]$RemotePath = "/home/orangepi/smart_home_AI"
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WslProjectRoot = "/home/jackgu/workspace/smart_home_AI"

Write-Host "Deploying through WSL..."
Write-Host "Target: ${PiUser}@${PiHost}:${RemotePath}"

wsl -e bash -lc "cd '$WslProjectRoot' && ./scripts/deploy-to-pi.sh --host '$PiHost' --user '$PiUser' --remote-path '$RemotePath'"
