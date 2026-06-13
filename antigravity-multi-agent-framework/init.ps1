# init.ps1
# Usage: .\init.ps1 -ProjectName "my-new-poc"
# Root wrapper script for initializing platform projects.

param (
    [Parameter(Mandatory=$true)]
    [string]$ProjectName
)

$InternalScript = ".\.agent\init-agent-project.ps1"

if (Test-Path -Path $InternalScript) {
    # Call the internal agent initialization script
    & $InternalScript -ProjectName $ProjectName
} else {
    Write-Error "Orchestration Engine Script not found at $InternalScript"
}
