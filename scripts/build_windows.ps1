$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$buildTemp = Join-Path $projectRoot '.qa/temp'
New-Item -ItemType Directory -Path $buildTemp -Force | Out-Null
$env:TEMP = $buildTemp
$env:TMP = $buildTemp
$env:PYINSTALLER_CONFIG_DIR = Join-Path $projectRoot '.qa/pyinstaller-cache'
$pythonExecutable = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Create .venv and install .[editor,build] first. See README.md.'
}
# Prevent DLLs from unrelated tools on PATH from entering the distributable.
$pythonBase = & $pythonExecutable -c 'import sys; print(sys.base_prefix)'
$env:PATH = @((Join-Path $env:SystemRoot 'System32'), $env:SystemRoot, $pythonBase, (Join-Path $pythonBase 'DLLs')) -join ';'
& $pythonExecutable -m PyInstaller --clean --noconfirm --distpath dist --workpath build/pyinstaller packaging/TkinterPlusPlus.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
$executablePath = Join-Path $projectRoot 'dist/TkinterPlusPlus-0.2.0-windows-x64.exe'
$hash = (Get-FileHash -LiteralPath $executablePath -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum = "$hash  $([IO.Path]::GetFileName($executablePath))"
[IO.File]::WriteAllText((Join-Path $projectRoot 'dist/SHA256SUMS.txt'), $checksum + "`n", [Text.UTF8Encoding]::new($false))
Write-Output $executablePath
