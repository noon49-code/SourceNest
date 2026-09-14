<#
SourceNest one-command Windows setup.

Default behavior is a read-only plan. Add -Apply to write files. If the vault
already exists, the script selects the reversible upgrade path automatically.
#>
[CmdletBinding()]
param(
    [string]$Vault = $(if ($env:BEYIN_VAULT) { $env:BEYIN_VAULT } else { Join-Path $env:USERPROFILE 'Documents\Beyin' }),
    [string]$CodexHome = '',
    [string]$ClaudeHome = '',
    [switch]$NoCodex,
    [switch]$NoClaude,
    [switch]$Apply,
    [switch]$Verify
)

$ErrorActionPreference = 'Stop'
$Package = Split-Path -Parent $MyInvocation.MyCommand.Path
$Vault = [IO.Path]::GetFullPath($Vault)

function Select-Python {
    if ($env:BEYIN_PYTHON -and (Test-Path -LiteralPath $env:BEYIN_PYTHON -PathType Leaf)) {
        return @{ Exe = [IO.Path]::GetFullPath($env:BEYIN_PYTHON); Prefix = @() }
    }
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled -PathType Leaf) {
        return @{ Exe = $bundled; Prefix = @() }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike '*WindowsApps*') {
        return @{ Exe = $python.Source; Prefix = @() }
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return @{ Exe = $py.Source; Prefix = @('-3') }
    }
    throw 'Python 3.11+ bulunamadı. BEYIN_PYTHON ile Python.exe yolunu belirt.'
}

function Resolve-Home([string]$Explicit, [string]$EnvironmentName, [string]$DefaultPath, [string]$CommandName, [switch]$Disabled) {
    if ($Disabled) { return $null }
    if ($Explicit) { return [IO.Path]::GetFullPath($Explicit) }
    $environmentValue = [Environment]::GetEnvironmentVariable($EnvironmentName)
    if ($environmentValue) { return [IO.Path]::GetFullPath($environmentValue) }
    $tool = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($tool -or (Test-Path -LiteralPath $DefaultPath -PathType Container)) { return $DefaultPath }
    return $null
}

$runtime = Select-Python
$codexDefault = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$claudeDefault = Join-Path $env:USERPROFILE '.claude'
$codex = Resolve-Home $CodexHome 'CODEX_HOME' $codexDefault 'codex' -Disabled:$NoCodex
$claude = Resolve-Home $ClaudeHome 'CLAUDE_HOME' $claudeDefault 'claude' -Disabled:$NoClaude

if (-not $codex -and -not $claude -and -not $Verify) {
    throw 'Codex veya Claude Code bulunamadı. -CodexHome ya da -ClaudeHome ile ayar klasörünü belirt.'
}

$arguments = @((Join-Path $Package 'install.py'), '--target', $Vault)
if ($codex) { $arguments += @('--codex-home', $codex) }
if ($claude) { $arguments += @('--claude-home', $claude) }

$engine = Join-Path $Vault 'engine\beyin.py'
if ($Verify) {
    $arguments += '--verify'
} elseif (Test-Path -LiteralPath $engine -PathType Leaf) {
    $arguments += '--upgrade'
} else {
    $arguments += @('--registry', (Join-Path $Package 'projects.example.json'))
    if ($Apply) { $arguments += '--apply' }
}

Write-Host ('SourceNest: ' + ($(if ($Verify) { 'doğrulama' } elseif ($Apply) { 'uygula' } else { 'plan' }))) -ForegroundColor Cyan
Write-Host ('Kasa: ' + $Vault)
Write-Host ('Bağlantılar: ' + ((@($codex, $claude) | Where-Object { $_ }) -join ', '))
& $runtime.Exe @($runtime.Prefix + $arguments)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $Apply -and -not $Verify) {
    Write-Host 'Plan gösterildi. Yazmak için aynı komuta -Apply ekle.' -ForegroundColor Yellow
}
