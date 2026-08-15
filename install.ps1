$ErrorActionPreference = "Stop"

$repository = "anlaki-py/codex-proxy"
$wheelUrl = $env:CODEX_PROXY_WHEEL_URL

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

$installRoot = $env:CODEX_PROXY_INSTALL_DIR
if (-not $installRoot) {
    $installRoot = "$env:LOCALAPPDATA\codex-proxy"
}
$venvDir = Join-Path $installRoot "venv"

Write-Host "Installing the latest codex-proxy wheel..."
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m venv $venvDir
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv $venvDir
} else {
    throw "Python 3.11 or newer is required."
}
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create the codex-proxy virtual environment."
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvExecutable = Join-Path $venvDir "Scripts\codex-proxy.exe"
$binDir = $env:CODEX_PROXY_BIN_DIR
if (-not $binDir) {
    $binDir = Join-Path $installRoot "bin"
}
$launcher = Join-Path $binDir "codex-proxy.cmd"

New-Item -ItemType Directory -Path $binDir -Force | Out-Null
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to update pip in the codex-proxy virtual environment."
}
& $venvPython -m pip install --upgrade --force-reinstall $wheelUrl
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install codex-proxy."
}
Set-Content -Path $launcher -Encoding ASCII -Value @(
    "@echo off"
    "`"$venvExecutable`" %*"
)

if ($env:CODEX_PROXY_SKIP_PATH_UPDATE -ne "1") {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $pathEntries = @($userPath -split ";" | Where-Object { $_ })
    if ($binDir -notin $pathEntries) {
        $newUserPath = (@($pathEntries) + $binDir) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    }
    if ($binDir -notin ($env:Path -split ";")) {
        $env:Path = "$env:Path;$binDir"
    }
}

Write-Host "Installed codex-proxy in $installRoot. Run 'codex-proxy login' to get started."
