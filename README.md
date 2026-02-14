# WorkTimeTracker - Restored & Improved

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Setup credentials:
   ```bash
   python tools/wtt_setup.py init
   python tools/wtt_setup.py add-google /path/to/service_account.json
   python tools/wtt_setup.py add-telegram
   ```

3. Apply database migrations:
   ```bash
   python db_migrations_improved.py local_backup.db migrate
   ```

4. Run user app:
   ```bash
   python user_app/main.py
   ```

5. Run admin app:
   ```bash
   python admin_app/main_admin.py
   ```

## Environment Sync (new machine / cloud)

Run one command to align dependencies and local config:

```bash
python3 tools/sync_env.py
```

What it does:
- Installs runtime dependencies (`requirements.txt` + `supabase` + `keyrings.alt`)
- Creates `.env` from `.env.example` if needed
- Tries to auto-wire `GOOGLE_CREDENTIALS_FILE` if `service_account.json` is present
- Runs a smoke import check for `config.py`

For strict validation with diagnostics:

```bash
python3 tools/sync_env.py --strict --doctor
```

## What's Included

- ✅ Original project (85 files)
- ✅ Security improvements (encrypted credentials)
- ✅ Database encryption (SQLCipher)
- ✅ Audit logging
- ✅ Improved sync (conflict resolution, exponential backoff)
- ✅ Database migrations

## Documentation

- `INTEGRATION_GUIDE.md` - How improvements are integrated
- `CHANGES_MAP.md` - What was changed in code
- `docs/` - Additional documentation

## Need Help?

Run diagnostics:
```bash
python tools/doctor.py
```
