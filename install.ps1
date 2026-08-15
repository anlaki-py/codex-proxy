$ErrorActionPreference = "Stop"

$repository = "anlaki-py/codex-proxy"
$wheelUrl = $env:CODEX_PROXY_WHEEL_URL
$pythonCommand = $env:CODEX_PROXY_PYTHON
$pythonArguments = @()

function Stop-Install {
    param([string]$Message)
    throw "codex-proxy installer: $Message"
}

function ConvertTo-NormalizedPath {
    param([string]$Path)
    if (-not $Path) {
        return ""
    }
    try {
        $expanded = [Environment]::ExpandEnvironmentVariables($Path)
        return [IO.Path]::GetFullPath($expanded).TrimEnd("\")
    } catch {
        return $Path.TrimEnd("\")
    }
}

function Test-PathEntry {
    param(
        [string[]]$Entries,
        [string]$Target
    )
    $normalizedTarget = ConvertTo-NormalizedPath $Target
    foreach ($entry in $Entries) {
        $normalizedEntry = ConvertTo-NormalizedPath $entry
        if ([string]::Equals($normalizedEntry, $normalizedTarget, "OrdinalIgnoreCase")) {
            return $true
        }
    }
    return $false
}

if (-not $pythonCommand) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonCommand = "py"
        $pythonArguments = @("-3")
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCommand = "python"
    } else {
        Stop-Install "Python 3.11 or newer was not found (checked py -3 and python)."
    }
}

try {
    $pythonVersion = [string](& $pythonCommand @pythonArguments -c `
        "import platform; print(platform.python_version())")
} catch {
    Stop-Install "Could not run the selected Python interpreter '$pythonCommand': $($_.Exception.Message)"
}
if ($LASTEXITCODE -ne 0 -or -not $pythonVersion) {
    Stop-Install "Could not determine the version of '$pythonCommand'."
}
& $pythonCommand @pythonArguments -c `
    "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    Stop-Install "Python 3.11 or newer is required; '$pythonCommand' reports $($pythonVersion.Trim())."
}
$pipVersion = [string](& $pythonCommand @pythonArguments -m pip --version)
if ($LASTEXITCODE -ne 0 -or -not $pipVersion) {
    Stop-Install "pip is unavailable for '$pythonCommand'. Install pip and try again."
}

if (-not $wheelUrl) {
    $headers = @{
        Accept = "application/vnd.github+json"
        "User-Agent" = "codex-proxy-installer"
    }
    try {
        $release = Invoke-RestMethod `
            -Uri "https://api.github.com/repos/$repository/releases/latest" `
            -Headers $headers `
            -TimeoutSec 30
    } catch {
        Stop-Install "GitHub release lookup failed: $($_.Exception.Message)"
    }
    if (-not $release -or -not $release.assets) {
        Stop-Install "GitHub returned a release with no downloadable assets."
    }
    $wheels = @(
        $release.assets | Where-Object {
            $_.name -like "codex_proxy-*-py3-none-any.whl" -and
            $_.browser_download_url -is [string]
        }
    )
    if ($wheels.Count -ne 1) {
        Stop-Install "Expected one codex-proxy wheel in the latest release; found $($wheels.Count)."
    }
    $wheelUrl = $wheels[0].browser_download_url
    $parsedWheelUrl = $null
    if (-not [Uri]::TryCreate($wheelUrl, [UriKind]::Absolute, [ref]$parsedWheelUrl) -or
        $parsedWheelUrl.Scheme -ne "https") {
        Stop-Install "GitHub returned an invalid wheel download URL."
    }
}

Write-Host "Installing the latest codex-proxy wheel..."
& $pythonCommand @pythonArguments -m pip install --upgrade $wheelUrl
if ($LASTEXITCODE -ne 0) {
    Stop-Install "pip could not install codex-proxy. Check network access and Python permissions."
}

$installedVersion = [string](& $pythonCommand @pythonArguments -c `
    "from importlib.metadata import version; print(version('codex-proxy'))")
if ($LASTEXITCODE -ne 0 -or -not $installedVersion) {
    Stop-Install "pip completed, but codex-proxy is not importable from '$pythonCommand'."
}

$scriptsDir = [string](& $pythonCommand @pythonArguments -c @'
from pathlib import Path
import sysconfig

schemes = (sysconfig.get_default_scheme(), sysconfig.get_preferred_scheme('user'))
paths = [sysconfig.get_path('scripts', scheme=scheme) for scheme in schemes]
print(next((path for path in paths if (Path(path) / 'codex-proxy.exe').is_file()), ''))
'@)
if ($LASTEXITCODE -ne 0) {
    Stop-Install "Installed codex-proxy, but failed to inspect its executable location."
}
$scriptsDir = $scriptsDir.Trim()
if (-not $scriptsDir) {
    Stop-Install "Installed codex-proxy, but could not locate its executable."
}
$executablePath = Join-Path $scriptsDir "codex-proxy.exe"
if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
    Stop-Install "Expected executable was not created at '$executablePath'."
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$userPathEntries = @($userPath -split ";" | Where-Object { $_ })
if (-not (Test-PathEntry $userPathEntries $scriptsDir)) {
    try {
        [Environment]::SetEnvironmentVariable(
            "Path",
            (@($userPathEntries) + $scriptsDir) -join ";",
            "User"
        )
    } catch {
        Stop-Install "Could not add '$scriptsDir' to your user PATH: $($_.Exception.Message)"
    }
    Write-Host "Added $scriptsDir to your user PATH."
}
if (-not (Test-PathEntry ($env:Path -split ";") $scriptsDir)) {
    $env:Path = "$scriptsDir;$env:Path"
}

Write-Host "Installed codex-proxy $($installedVersion.Trim()) with $pythonCommand."
Write-Host "Executable: $executablePath"
Write-Host "Run 'codex-proxy login' to get started."
