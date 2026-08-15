$ErrorActionPreference = "Stop"

$repository = "anlaki-py/codex-proxy"
$wheelUrl = $env:CODEX_PROXY_WHEEL_URL
$pythonCommand = $env:CODEX_PROXY_PYTHON
$pythonArguments = @()

if (-not $pythonCommand) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonCommand = "py"
        $pythonArguments = @("-3")
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCommand = "python"
    } else {
        throw "Python 3.11 or newer is required."
    }
}

& $pythonCommand @pythonArguments -c `
    "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'Python 3.11 or newer is required.')"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.11 or newer is required."
}

if (-not $wheelUrl) {
    $headers = @{
        Accept = "application/vnd.github+json"
        "User-Agent" = "codex-proxy-installer"
    }
    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/$repository/releases/latest" `
        -Headers $headers
    $wheels = @(
        $release.assets | Where-Object {
            $_.name -like "codex_proxy-*-py3-none-any.whl"
        }
    )
    if ($wheels.Count -ne 1) {
        throw "Expected one codex-proxy wheel in the latest release, found $($wheels.Count)"
    }
    $wheelUrl = $wheels[0].browser_download_url
}

Write-Host "Installing the latest codex-proxy wheel..."
& $pythonCommand @pythonArguments -m pip install --upgrade $wheelUrl
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install codex-proxy."
}
Write-Host "Installed codex-proxy with $pythonCommand. Run 'codex-proxy login' to get started."
