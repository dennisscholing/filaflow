# Install FilaFlow on Synology

This guide targets DSM 7.2 with **Container Manager**. The NAS downloads a prebuilt image for `linux/amd64` or `linux/arm64`; it does not compile FilaFlow.

## 0. Confirm the GitHub package is public

The GitHub Action named **Multi-arch container** must be green. Then open your GitHub profile → **Packages** → **filaflow** → **Package settings** and confirm that package visibility is **Public**. Synology cannot download a private GHCR image without registry credentials.

The Compose file already uses:

```text
ghcr.io/dennisscholing/filaflow:latest
```

There is no image version to maintain in `.env` or the Synology project.

## 1. Create the folders

Create this structure in File Station:

```text
/volume1/docker/filaflow/
├── backups/
├── config/
├── postgres/
└── project/
    ├── .env
    ├── docker-compose.yml
    └── deploy/
        └── backup.sh
```

Upload `docker-compose.yml`, `deploy/backup.sh`, and `.env.example` from the repository. Rename `.env.example` to `.env`. Files beginning with a dot may be hidden in File Station.

If your storage volume is not `volume1`, change `FILAFLOW_DATA_ROOT` in `.env` and use the same volume name in the permission commands below.

## 2. Set folder permissions

Open **Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script**. Select user `root`, run this script once, and disable or remove the task afterward:

```sh
chown -R 70:70 /volume1/docker/filaflow/postgres /volume1/docker/filaflow/backups
chown -R 10001:10001 /volume1/docker/filaflow/config
chmod 750 /volume1/docker/filaflow/postgres /volume1/docker/filaflow/config
chmod 770 /volume1/docker/filaflow/backups
chmod 755 /volume1/docker/filaflow/project/deploy/backup.sh
```

The application joins group `70` only to create verified pre-upgrade dumps. Do not use `chmod 777`.

## 3. Edit `.env`

The required configuration is intentionally small:

```dotenv
FILAFLOW_DATA_ROOT=/volume1/docker/filaflow
FILAFLOW_PORT=9000
FILAFLOW_COOKIE_SECURE=false
FILAFLOW_FORWARDED_ALLOW_IPS=127.0.0.1

POSTGRES_DB=filaflow
POSTGRES_USER=filaflow
POSTGRES_PASSWORD='CHANGE_TO_A_LONG_UNIQUE_DATABASE_PASSWORD'
FILAFLOW_SECRET_KEY='CHANGE_TO_AT_LEAST_64_RANDOM_CHARACTERS'
FILAFLOW_ADMIN_EMAIL=admin@example.local
FILAFLOW_ADMIN_PASSWORD='CHANGE_TO_A_LONG_UNIQUE_ADMIN_PASSWORD'

BACKUP_DAILY_KEEP=7
BACKUP_WEEKLY_KEEP=4
BACKUP_PREUPGRADE_KEEP=5
BACKUP_HOUR=2
```

Replace the three password/secret placeholders. Keep the single quotes so characters such as `$`, `%`, `#`, and `@` remain literal. The bootstrap email and password are only used when no user exists yet; later `.env` changes do not reset an existing account.

No NAS IP is required. Open the app using the same IP address or hostname you already use for DSM, followed by port `9000`. FilaFlow also uses the incoming browser address for QR-label links.

## 4. Create the Container Manager project

1. Install and open **Container Manager** from Package Center.
2. Open **Project → Create**.
3. Enter project name `filaflow`.
4. Select `/volume1/docker/filaflow/project` as the path.
5. Use the existing `docker-compose.yml`.
6. Confirm validation and start the project.
7. Wait until `filaflow-db` is healthy and `filaflow-app` is running.

Open `http://YOUR-NAS-IP:9000` and sign in with the bootstrap administrator from `.env`. Additional users can be created under **Settings → Users**.

## 5. Verify the installation

- **Overview** opens successfully.
- `http://YOUR-NAS-IP:9000/api/health` returns `{"status":"ok"}`.
- Only port `9000` is published; PostgreSQL is internal to the Compose project.
- **Settings → OpenPrintTag → Synchronize** downloads the catalog.
- A dump appears in `/volume1/docker/filaflow/backups/daily` after the configured backup time.

## 6. Optional HTTPS reverse proxy

Open **Control Panel → Login Portal → Advanced → Reverse Proxy → Create**:

- Source: `HTTPS`, your hostname, port `443`.
- Destination: `HTTP`, `127.0.0.1`, port `9000`.
- Assign the matching certificate under **Security → Certificate**.

Then add or change these values in `.env`:

```dotenv
FILAFLOW_PUBLIC_URL=https://filament.example.com
FILAFLOW_COOKIE_SECURE=true
```

The public URL is optional for normal LAN use. It is useful behind a reverse proxy so printed QR labels always contain the external HTTPS address.

Rebuild and start the project after changing `.env`. Do not expose FilaFlow unrestricted to the internet; prefer a VPN, firewall rules, or a Synology access-control profile.

## 7. Connect PrusaSlicer

1. Add every physical printer in FilaFlow and enter its primary PrusaSlicer profile name exactly.
2. Open **Settings → PrusaSlicer API token**, name the token, and select a printer.
3. Generate the token and run the displayed `--add-printer` command on the PrusaSlicer computer.
4. Repeat steps 2–3 once for every printer used by that PrusaSlicer installation.
5. Store `filaflow_hook.py` in a permanent local folder.
6. Add its Python command once under **Print Settings → Output options → Post-processing scripts**.
7. Slice and export a small test model for each printer, then check **Print inbox**.

PrusaSlicer appends the temporary G-code path automatically. The hook first checks the physical-printer profile, then the general printer profile, and finally the configured default. It copies the job to a local outbox and always returns success to PrusaSlicer, even when the NAS is offline. See the [PrusaSlicer hook guide](../client/prusa-hook/README.md) for aliases, Windows examples, and retry instructions.

## 8. Backups and restore

Add `/volume1/docker/filaflow/backups` to Hyper Backup. Do not copy the live `postgres` directory as a replacement for a consistent `pg_dump`.

Daily and weekly dumps are stored in `backups/daily` and `backups/weekly`. Before every database migration, the app creates a second custom-format dump in `backups/pre-upgrade`, verifies that `pg_restore` can read it, and records its SHA-256 checksum in the adjacent JSON file.

Create a manual backup from the project directory:

```sh
docker compose exec backup pg_dump --format=custom --compress=9 --file=/backups/daily/filaflow-manual.dump
```

Restore a dump into an empty database:

```sh
docker compose stop app backup
docker compose exec -T db dropdb -U filaflow --if-exists filaflow
docker compose exec -T db createdb -U filaflow filaflow
docker compose exec -T db pg_restore -U filaflow -d filaflow --clean --if-exists < /volume1/docker/filaflow/backups/daily/YOUR-DUMP.dump
docker compose start app backup
```

Use the database/user values from `.env` if you changed them. Test restores periodically in a separate project.

## 9. Updates and rollback

FilaFlow follows the `latest` image. Container Manager can detect a newer image, but it does not silently replace a running container. That safeguard prevents an unattended database migration from surprising you.

To update:

1. For the first v0.2 update, download the current `docker-compose.yml`, `.env.example`, and `deploy/backup.sh` from GitHub. Replace the Compose file and backup script in the project folder. Add any new non-secret options from `.env.example` to `.env`; do not overwrite your secrets.
2. Re-run the permission commands from section 2. An old project without the writable backup mount is intentionally not allowed to migrate the database.
3. Make a manual database backup.
4. Open **Container Manager → Image**.
5. Select the FilaFlow image and choose **Action → Update** or click **Update available**.
6. Open **Project**, select `filaflow`, choose **Action → Build**, then **Start**.
7. Wait a few minutes, then check login, spools, printers, OpenPrintTag, and `/api/health`.

Normal later updates do not require an image-tag or IP change. The Compose `pull_policy` requests the current image whenever the project is recreated. FilaFlow locks migration execution, rejects unknown database revisions, and starts the web server only after the database reaches the exact expected revision.

Fully unattended updating would require a privileged host task or a container with Docker-socket access. FilaFlow deliberately avoids that security risk.

For a controlled image pin or rollback, add this line to `.env` and rebuild the project:

```dotenv
FILAFLOW_IMAGE=ghcr.io/dennisscholing/filaflow:v0.1.6
```

Remove the line later to follow `latest` again. If the failed update changed the schema, restore its verified `backups/pre-upgrade` dump before starting the older image. Reverting only the image may be unsafe after a database migration.

### If a migration stops startup

Read the `filaflow-app` log first. FilaFlow writes `/volume1/docker/filaflow/config/migration-failed.json` and blocks automatic retries so the same failing operation cannot loop. Keep this file while investigating. Restore the most recent verified pre-upgrade dump, confirm that the matching JSON checksum is present, and then either deploy the compatible previous image or remove the failure marker once before retrying the corrected update. Never delete the marker merely to force repeated attempts against the production database.
