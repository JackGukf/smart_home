param(
    [string]$PiHost = "192.168.0.234",
    [string]$PiUser = "orangepi",
    [string]$RemotePath = "/home/orangepi/smart_home_AI",
    [switch]$Check,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Command
)

$WslProjectRoot = "/home/jackgu/workspace/smart_home_AI"
$CheckArg = if ($Check) { "--check" } else { "" }
$RemoteCommand = if ($Command.Count -gt 0) { "-- " + ($Command -join " ") } else { "" }

wsl -e bash -lc "cd '$WslProjectRoot' && ./scripts/connect-pi.sh --host '$PiHost' --user '$PiUser' --remote-path '$RemotePath' $CheckArg $RemoteCommand"
