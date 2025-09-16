<#
Create a GitHub repository named LANGCHAIN-RAG and push local branches.

This script requires GitHub CLI (`gh`) to be installed and authenticated.
If `gh` is not available, follow the steps in README_REMOTE_SETUP.md.

Usage (PowerShell):
  .\scripts\create_remote_repo.ps1
#>
try {
    gh --version > $null 2>&1
} catch {
    Write-Error "gh (GitHub CLI) not found. See README_REMOTE_SETUP.md for manual steps."
    exit 1
}

$repoName = 'LANGCHAIN-RAG'
Write-Host "Creating repo $repoName on GitHub..."
gh repo create $repoName --public --source=. --remote=origin --push --confirm
Write-Host "Repository created and pushed. Consider enabling branch protections in the GitHub UI."
