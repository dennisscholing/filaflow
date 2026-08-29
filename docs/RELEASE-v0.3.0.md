# FilaFlow v0.3.0

FilaFlow v0.3.0 focuses on day-to-day stock management. It adds silent five-second refresh, an attention and reorder dashboard, improved INDX loadouts, richer spool browsing, quick inbox booking, personal display units, and a guided label-template editor.

## Data safety

- The schema update is additive and creates only label-template and reorder-setting tables.
- Existing users, printers, tools, spools, loadouts, jobs, ledger entries, UUIDs, and codes are not rewritten.
- FilaFlow keeps the existing migration lock and creates and validates a pre-upgrade PostgreSQL dump before applying the migration.
- The app starts only after the database reaches the exact expected migration revision.
- Synology never replaces the running image automatically. Updating remains a deliberate Container Manager action.

## Release process

1. Push the release commit to `main` and wait until its `candidate` and immutable `sha-…` multi-architecture image is complete.
2. Tag that same commit as `v0.3.0-rc.1`. The workflow promotes the existing SHA image to this RC tag without rebuilding it.
3. Verify a fresh install, a representative v0.2.0 upgrade, backup validation, restore, frontend build, backend tests, hook tests, and Compose validation.
4. Tag the same commit as `v0.3.0`. The workflow promotes the exact same SHA image digest to `v0.3.0` and `latest`; it never rebuilds it.
5. Update the Synology project manually by stopping the project, downloading the selected image, and building the project again.

The normal upgrade and rollback instructions are in [SYNOLOGY.md](SYNOLOGY.md).
