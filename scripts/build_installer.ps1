param([string]$InnoCompiler = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$version = [regex]::Match((Get-Content -LiteralPath 'pyproject.toml' -Raw), '(?m)^version = "([^"]+)"').Groups[1].Value
if (-not $version) { throw 'Cannot read project version.' }
$portable = Join-Path $projectRoot "dist/TkinterPlusPlus-$version-windows-x64.exe"
if (-not (Test-Path -LiteralPath $portable)) { throw 'Build the portable executable with scripts/build_windows.ps1 first.' }
if (-not $InnoCompiler) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $InnoCompiler = $command.Source }
    else {
        foreach ($candidate in @(
            (Join-Path $projectRoot '.qa/tools/inno/ISCC.exe'),
            (Join-Path $env:ProgramFiles 'Inno Setup 7/ISCC.exe'),
            (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7/ISCC.exe')
        )) {
            if (Test-Path -LiteralPath $candidate) { $InnoCompiler = $candidate; break }
        }
    }
}
if (-not $InnoCompiler) { throw 'Install Inno Setup 7, or pass -InnoCompiler with the full path to ISCC.exe.' }
$buildTemp = Join-Path $projectRoot '.qa/temp'
New-Item -ItemType Directory -Force -Path $buildTemp | Out-Null
$env:TEMP = $buildTemp
$env:TMP = $buildTemp
& $InnoCompiler "/DAppVersion=$version" 'packaging/windows-installer.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
Write-Output (Join-Path $projectRoot "dist/TkinterPlusPlus-$version-setup-windows-x64.exe")
