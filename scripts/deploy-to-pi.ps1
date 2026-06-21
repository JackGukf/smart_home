param(
    [string]$PiHost = "192.168.0.176",
    [string]$PiUser = "smarthome",
    [string]$RemotePath = "/home/smarthome/smart-home-rpi4"
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WslProjectRoot = "/home/jackgu/workspace/smart-home-rpi4"

Write-Host "Deploying through WSL..."
Write-Host "Target: ${PiUser}@${PiHost}:${RemotePath}"

wsl -e bash -lc "cd '$WslProjectRoot' && ./scripts/deploy-to-pi.sh --host '$PiHost' --user '$PiUser' --remote-path '$RemotePath'"
