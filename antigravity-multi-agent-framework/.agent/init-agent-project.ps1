# init-agent-project.ps1
# Usage: .\init-agent-project.ps1 -ProjectName "my-new-poc"
# Executes in PowerShell. Initializes and links the multi-agent platform context.

param (
    [Parameter(Mandatory=$true)]
    [string]$ProjectName
)

$GlobalAgentDir = "e:\ands-agentic\EL-AI\.agent"
$TargetProjectDir = "e:\ands-agentic\EL-AI\$ProjectName"
$StateDir = "$TargetProjectDir\.agent_state"
$SymlinkPath = "$TargetProjectDir\.agent"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Initializing Platform Workspace: $ProjectName" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Create target project directory if missing
if (-not (Test-Path -Path $TargetProjectDir)) {
    Write-Host "Creating project directory: $TargetProjectDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $TargetProjectDir | Out-Null
} else {
    Write-Host "Project directory already exists: $TargetProjectDir" -ForegroundColor Green
}

# 2. Create local blackboard state folder
if (-not (Test-Path -Path $StateDir)) {
    Write-Host "Initializing blackboard memory: $StateDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $StateDir | Out-Null
} else {
    Write-Host "Blackboard memory already initialized." -ForegroundColor Green
}

# 3. Create the symbolic link to register global workflows (/intake, /plan, etc)
if (-not (Test-Path -Path $SymlinkPath)) {
    Write-Host "Creating directory junction to register slash commands..." -ForegroundColor Yellow
    # Create a Junction link (does NOT require Admin privileges on Windows)
    New-Item -ItemType Junction -Path $SymlinkPath -Target $GlobalAgentDir | Out-Null
    Write-Host "Workflow link created successfully." -ForegroundColor Green
} else {
    Write-Host "Workflow link already exists. Cleaning up and recreating..." -ForegroundColor Yellow
    Remove-Item -Path $SymlinkPath -Force -Recurse
    New-Item -ItemType Junction -Path $SymlinkPath -Target $GlobalAgentDir | Out-Null
    Write-Host "Workflow link refreshed successfully." -ForegroundColor Green
}

Write-Host "`nProject successfully initialized!" -ForegroundColor Green
Write-Host "State Folder: $StateDir" -ForegroundColor White
Write-Host "Workflows: Linked to global .agent engine" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Cyan
