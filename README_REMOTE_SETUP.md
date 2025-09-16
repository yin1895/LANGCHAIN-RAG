# Create remote GitHub repository (LANGCHAIN-RAG)

This project includes helper scripts to create and push a remote GitHub repository named `LANGCHAIN-RAG`.

Option A: Using GitHub CLI (recommended)
1. Install GitHub CLI: https://cli.github.com/
2. Authenticate: `gh auth login` (choose GitHub.com and your preferred auth)
3. From the repo root run (PowerShell):

   .\scripts\create_remote_repo.ps1

This will create a public repository named `LANGCHAIN-RAG`, add `origin`, and push the current branch.

Option B: Manual via GitHub website
1. Create a new repository on https://github.com/new named `LANGCHAIN-RAG`.
2. In your local repo run:

```powershell
# activate venv first if you want
& D:/langchain-RAG/.venv/Scripts/Activate.ps1
git remote add origin https://github.com/<your-org-or-username>/LANGCHAIN-RAG.git
git push -u origin main
# create and push develop branch
git checkout -b develop
git push -u origin develop
# create a release branch
git checkout -b release/0.1.0
git push -u origin release/0.1.0
```

After pushing, configure branch protections for `main` in the GitHub repository settings (require PR reviews, status checks, etc.).

If you want, I can attempt to run the helper script (requires `gh`) or perform the manual remote add and push for you if you provide the remote URL or authenticate `gh` locally.
