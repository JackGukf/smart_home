param(
    [string]$PiHost,
    [string]$PiUser,
    [string]$RemotePath,
    [switch]$Check,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Command
)

# Addresses come from configs/hosts.env - the only place they are written down.
# A value passed on the command line still wins; this only fills the blanks.
function Get-SmartHomeHosts {
    $file = Join-Path $PSScriptRoot "..\configs\hosts.env"
    $map = @{}
    if (Test-Path $file) {
        foreach ($line in Get-Content $file) {
            $trimmed = $line.Trim()
            if ($trimmed -eq "" -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
            $key, $value = $trimmed.Split("=", 2)
            $map[$key.Trim()] = $value.Trim()
        }
    }
    return $map
}
$SmartHomeHosts = Get-SmartHomeHosts
if (-not $PSBoundParameters.ContainsKey("PiHost")     -and $SmartHomeHosts["PI_HOST"])     { $PiHost     = $SmartHomeHosts["PI_HOST"] }
if (-not $PSBoundParameters.ContainsKey("PiUser")     -and $SmartHomeHosts["PI_USER"])     { $PiUser     = $SmartHomeHosts["PI_USER"] }
if (-not $PSBoundParameters.ContainsKey("RemotePath") -and $SmartHomeHosts["REMOTE_PATH"]) { $RemotePath = $SmartHomeHosts["REMOTE_PATH"] }

$WslProjectRoot = "/home/jackgu/workspace/smart_home_AI"
$CheckArg = if ($Check) { "--check" } else { "" }
$RemoteCommand = if ($Command.Count -gt 0) { "-- " + ($Command -join " ") } else { "" }

wsl -e bash -lc "cd '$WslProjectRoot' && ./scripts/connect-pi.sh --host '$PiHost' --user '$PiUser' --remote-path '$RemotePath' $CheckArg $RemoteCommand"
