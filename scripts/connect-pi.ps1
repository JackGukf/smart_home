param(
    [string]$PiHost = "192.168.0.176",
    [string]$PiUser = "smarthome",
    [string]$RemotePath = "/home/smarthome/smart-home-rpi4",
    [switch]$Check,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Command
)

$WslProjectRoot = "/home/jackgu/workspace/smart-home-rpi4"
$CheckArg = if ($Check) { "--check" } else { "" }
$RemoteCommand = if ($Command.Count -gt 0) { "-- " + ($Command -join " ") } else { "" }

wsl -e bash -lc "cd '$WslProjectRoot' && ./scripts/connect-pi.sh --host '$PiHost' --user '$PiUser' --remote-path '$RemotePath' $CheckArg $RemoteCommand"
