# Runs the project checks on Windows/PowerShell.
# Usage:  ./scripts/run-checks.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> Evaluation harness (regression gate)" -ForegroundColor Cyan
python evals/run_eval.py --gate

Write-Host "`n==> Agent-runtime tests (pytest, if installed)" -ForegroundColor Cyan
Push-Location services/agent-runtime
try { python -m pytest } catch { Write-Host "skip: pytest not installed (pip install -e .[dev])" -ForegroundColor Yellow }
Pop-Location

Write-Host "`n==> Gateway tests (jest, if installed)" -ForegroundColor Cyan
Push-Location services/gateway
if (Test-Path node_modules) { npm test } else { Write-Host "skip: run 'npm install' first" -ForegroundColor Yellow }
Pop-Location

Write-Host "`nAll checks complete." -ForegroundColor Green
