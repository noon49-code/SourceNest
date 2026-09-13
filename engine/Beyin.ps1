# Portable launcher; compatible with Windows PowerShell 5.1 and PowerShell 7.
# All arguments are forwarded as arguments, never evaluated as shell source.
$ErrorActionPreference = 'Stop'
$BeyinScript = Join-Path $PSScriptRoot 'beyin.py'
$BeyinCandidates = @()
if ($env:BEYIN_PYTHON) { $BeyinCandidates += $env:BEYIN_PYTHON }
$BeyinCandidates += (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
$BeyinCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($BeyinCommand -and $BeyinCommand.Source -notlike '*WindowsApps*') { $BeyinCandidates += $BeyinCommand.Source }
$BeyinPython = $BeyinCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $BeyinPython) { throw 'Python 3.11+ is required. Set BEYIN_PYTHON to the executable path.' }
& $BeyinPython $BeyinScript @args
exit $LASTEXITCODE
