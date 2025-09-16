param(
    [string]$remoteUrl = 'git@github.com:yin1895/LANGCHAIN-RAG.git'
)

Write-Host "Preparing to push repository to remote: $remoteUrl"

function run([string]$cmd) {
    Write-Host "> $cmd"
    $r = & cmd /c $cmd
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Command failed: $cmd"
        exit $LASTEXITCODE
    }
    return $r
}

# Ensure we are in repo root
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# Ensure there's at least one commit
try {
    git rev-parse --verify HEAD > $null 2>&1
    $hasHead = $true
} catch {
    $hasHead = $false
}
if (-not $hasHead) {
    Write-Host "No commits found. Creating initial commit..."
    git add --all
    git commit -m "Initial import: RAG improvements, caching, celery, metrics, migration tools"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create initial commit"
        exit 1
    }
} else {
    Write-Host "Repository already has commits."
}

# Add or set origin
try {
    $existing = git remote get-url origin 2>$null
    if ($existing) {
        Write-Host "Existing origin: $existing"
        if ($existing -ne $remoteUrl) {
            Write-Host "Updating origin to $remoteUrl"
            git remote set-url origin $remoteUrl
        }
    }
} catch {
    Write-Host "Adding origin $remoteUrl"
    git remote add origin $remoteUrl
}

# Ensure local main branch exists
try {
    git rev-parse --verify main > $null 2>&1
    $mainExists = $true
} catch {
    $mainExists = $false
}
if (-not $mainExists) {
    # create main from current HEAD
    $cur = (git rev-parse --abbrev-ref HEAD).Trim()
    if ($cur -ne 'main') {
        Write-Host "Creating branch 'main' from $cur"
        git branch -M main
    }
}

Write-Host "Pushing main..."
git push -u origin main

Write-Host "Creating and pushing develop branch..."
git checkout -b develop
if ($LASTEXITCODE -ne 0) {
    git checkout develop
}
git push -u origin develop

Write-Host "Creating and pushing release/0.1.0 branch..."
git checkout main
git checkout -b release/0.1.0
if ($LASTEXITCODE -ne 0) {
    git checkout release/0.1.0
}
git push -u origin release/0.1.0

git checkout main

Write-Host "Done. Remote branches pushed. If the push failed due to SSH auth, ensure your SSH key is added to your GitHub account."
