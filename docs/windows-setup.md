# Windows Setup

Use the PowerShell scripts in [`scripts/`](C:/Users/felze/source/repos/PharmacyStudyApp/scripts) for local database tasks.

## Database commands

From the repo root in PowerShell:

```powershell
.\scripts\db-up.ps1
.\scripts\db-migrate.ps1
.\scripts\db-seed.ps1
```

Or run the full bootstrap:

```powershell
.\scripts\db-bootstrap.ps1
```

To remove the local Postgres container and named volume for a clean database:

```powershell
.\scripts\db-reset.ps1
```

## Notes

- These scripts mirror the existing `Makefile` targets.
- `db-reset.ps1` deletes the Docker volume, so it removes all local database data.
- Run PowerShell from the repository root so the relative paths resolve correctly.
- For Supabase-backed auth, set `SUPABASE_URL` in the repo-root `.env` to your
  project base URL (for example, `https://your-project.supabase.co`). The
  backend verifies modern RSA/ECC access tokens against
  `/.well-known/jwks.json`.
- `SUPABASE_JWT_SECRET` is only needed for legacy HS256 JWT setups.
- If script execution is blocked on your machine, run them with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\db-bootstrap.ps1
```
