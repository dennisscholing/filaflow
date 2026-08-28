# FilaFlow

FilaFlow is a self-hosted filament inventory for multiple FFF printers. Prusa INDX with tools T1–T8 is the primary acceptance profile, but every printer can have a dynamic number of tools.

FilaFlow never controls, pauses, approves, or blocks a print. The PrusaSlicer hook stores a copy in a local outbox and always exits successfully. Mapping, soft reservations, and final consumption are administrative actions performed during or after printing.

## Features

- Dark, responsive English interface.
- Physical spools with UUIDv7, immutable `SPL` codes, weight and length, ledger history, weighing, QR labels, and archiving.
- Multiple printers with `PRN` codes, single/dual/INDX T1–T8 presets, dynamic tools, and loadouts.
- Automatic multi-printer routing from one PrusaSlicer installation, including physical-printer profile aliases and a safe default.
- Print inbox with `NEW`, `MAPPED`, `NEEDS_REVIEW`, `BOOKED`, and `DISMISSED` states.
- Regular G-code and binary `.bgcode` through the official libbgcode CLI.
- OpenPrintTag catalog synchronization plus fully manual materials.
- Editable spool and printer metadata, offline color-name suggestions, and real 30-day usage in grams and metres.
- Admin/operator users, printer-bound API tokens, audit log, CSV/JSON export, daily backups, and verified pre-upgrade backups.
- Prebuilt `linux/amd64` and `linux/arm64` images for Synology Container Manager.

## Install

Use the short beginner guide: [Quick start](docs/QUICKSTART.md).

For folder permissions, backups, HTTPS, updates, and restore instructions, see the full [Synology guide](docs/SYNOLOGY.md).

The Compose project automatically uses:

```text
ghcr.io/dennisscholing/filaflow:latest
```

You do not need to enter an image version or NAS IP in `.env`. Open FilaFlow at `http://YOUR-NAS-IP:9000`; QR links use the address from your browser request.

## PrusaSlicer

1. Add a printer in FilaFlow.
2. Open **Settings → PrusaSlicer API token** and create a printer-bound token.
3. Copy `client/prusa-hook/filaflow_hook.py` to the PrusaSlicer computer.
4. Run the generated command once for every printer used on that computer.
5. Add the hook under **Print Settings → Output options → Post-processing scripts**.

The hook line stays the same for every printer. It selects the FilaFlow printer from the active PrusaSlicer physical-printer or printer profile.

See [PrusaSlicer hook setup](client/prusa-hook/README.md) for exact Windows examples and troubleshooting.

## Updates

The Compose file follows `latest`, so no version needs to be edited. Synology Container Manager shows when an image update is available. Apply it under **Image → filaflow → Action → Update**, then rebuild and start the project. A running container cannot safely replace itself; fully unattended updates would require Docker-socket access, which FilaFlow deliberately does not use.

Before a schema update, FilaFlow takes a PostgreSQL custom-format dump, validates it with `pg_restore`, writes a SHA-256 checksum, and only then runs the migration. Startup stops safely if the backup mount is missing, the revision is unknown, or migration verification fails. A manual backup before maintenance remains recommended.

## Backups

The `backup` service creates daily PostgreSQL custom-format dumps and weekly copies. Add `/volume1/docker/filaflow/backups` to Hyper Backup. Do not use the live `postgres` directory as a replacement for a database dump.

## Development

```sh
npm ci
npm run lint
npm run build:spa
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/Scripts/python -m pytest backend/tests client/prusa-hook/test_hook.py
docker compose --env-file .env.example config --quiet
```

## V1 boundaries

No printer control, automatic print-state tracking, print approval, hard stock blocking, NFC, product barcodes, Cura/Orca hook, humidity/drying management, project management, or advanced business analytics. `NEEDS_REVIEW` is an administrative warning only.
