param(
    [string]$PiHost = "raspberrypi.local",
    [string]$PiUser = "pi",
    [string]$RemotePath = "/home/pi/smart-home-rpi4"
)

Write-Host "Deployment placeholder"
Write-Host "Target: ${PiUser}@${PiHost}:${RemotePath}"
Write-Host "Add rsync/scp/git deployment steps when the Pi is reachable."
