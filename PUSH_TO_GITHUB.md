# Push NoUS-mINd-SENTinel to GitHub (nousloop)

This repo is initialized locally with one commit on `main`. Create the remote repo, then push.

## 1. Create the repo on GitHub

- **Org:** [nousloopsolutions](https://github.com/nousloopsolutions)
- **Repo name:** `NoUS-mINd-SENTinel` (match exactly for consistency with other NOUS repos)
- **URL:** https://github.com/new?name=NoUS-mINd-SENTinel (create under the nousloopsolutions org if you have admin access)
- **Important:** Do **not** check "Add a README", "Add .gitignore", or "Choose a license". Create an **empty** repo.

## 2. Push (PowerShell)

Remote is already set. From project root:

```powershell
cd "G:\My Drive\NOUS LOOP SOLUTIONS LLC\CLone Repos\NoUS-mINd-SENTinel"
git push -u origin main
```

If the repo was created under your user instead of nousloopsolutions:

```powershell
git remote set-url origin https://github.com/YOUR_USERNAME/NoUS-mINd-SENTinel.git
git push -u origin main
```

## 3. After first push

- Add this repo to `CLone Repos\REPOSITORY_LINKS.md` (already done in workspace).
- Use `CLone Repos\sync-and-push-all.ps1` for future syncs (script updated to include this repo).
