# FilaFlow

FilaFlow is een self-hosted filamentadministratie voor meerdere FFF-printers. Een Prusa INDX met T1–T8 is het belangrijkste acceptatieprofiel, maar printers hebben een dynamisch aantal tools. FilaFlow bestuurt, pauzeert of blokkeert **nooit** een print. De PrusaSlicer-hook kopieert de G-code naar een lokale outbox en retourneert altijd succes; reserveren en boeken gebeurt uitsluitend administratief tijdens of na de print.

De app bewaart lengte in millimeters en gewicht in milligrammen. De interface toont beide als meter en gram/kg. Conversies gebruiken de diameter en dichtheid die als momentopname bij de rol/job zijn opgeslagen.

## Wat is geïmplementeerd

- responsive, lichter antraciet dark dashboard met remaining, reserved en available;
- fysieke rollen met UUIDv7, onveranderlijke `SPL`-code, ledger, wegen met tarra, QR-label en archivering;
- voortijdig lege rollen met een ledgercorrectie naar nul, automatisch ontladen en archiveren zonder historie te verwijderen;
- meerdere printers met UUIDv7, `PRN`-code, single/dual/INDX T1–T8-presets, dynamische loadouts en atomair verplaatsen van rollen;
- printinbox `NEW`, `MAPPED`, `NEEDS_REVIEW`, `BOOKED` en `DISMISSED`, met zachte reserveringen en expliciet toegestaan negatief boeken;
- gewone G-code per tool en `.bgcode` via de officiële `bgcode`-CLI uit libbgcode;
- dagelijkse atomair gewisselde OpenPrintTag-snapshot en handmatige rollen;
- sessieauthenticatie, CSRF-bescherming, Argon2-wachtwoorden, admin/operator-gebruikersbeheer en printergebonden API-tokens;
- auditlog, CSV/JSON-export en PostgreSQL custom-format back-ups;
- multi-architecture GHCR-workflow voor `linux/amd64` en `linux/arm64`.

## Installatie in Synology Container Manager

Voor een volledige klik-voor-klik installatie, inclusief het publiceren van de multi-architecture image en de actuele randvoorwaarde rond de voorbeeldtag, zie [`docs/SYNOLOGY.md`](docs/SYNOLOGY.md).

Voor de korte beginnersroute van GitHub naar Synology en PrusaSlicer, zie [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

### 1. Mappen maken

Maak in File Station onder `/volume1/docker` de map `filaflow` en daarin `postgres`, `backups` en `config`. De containers gebruiken vaste niet-root UID's. Via DSM Taakplanner → Door gebruiker gedefinieerd script (als `root`) kun je eenmalig uitvoeren:

```sh
chown -R 70:70 /volume1/docker/filaflow/postgres /volume1/docker/filaflow/backups
chown -R 10001:10001 /volume1/docker/filaflow/config
chmod 750 /volume1/docker/filaflow/postgres /volume1/docker/filaflow/backups /volume1/docker/filaflow/config
```

Gebruik een andere volumenaam door `FILAFLOW_DATA_ROOT` in `.env` te wijzigen. Geef geen brede `777`-rechten.

### 2. Projectbestanden voorbereiden

Download deze repository/release naar een pc. Kopieer `.env.example` naar `.env` en vul minimaal in:

- `FILAFLOW_IMAGE`: gepubliceerde GHCR-image en bij voorkeur een vaste versie, bijvoorbeeld `ghcr.io/<owner>/filaflow:v1.0.0`;
- `POSTGRES_PASSWORD`: lang uniek databasewachtwoord;
- `FILAFLOW_SECRET_KEY`: minstens 64 willekeurige tekens;
- `FILAFLOW_ADMIN_EMAIL` en `FILAFLOW_ADMIN_PASSWORD`;
- `FILAFLOW_PUBLIC_URL`: het LAN- of HTTPS-adres zonder afsluitende slash.

Upload `docker-compose.yml`, `.env` en de map `deploy` samen. In Container Manager open je **Project → Create**, kies je een projectnaam en de geüploade projectmap en laat je DSM het Compose-bestand uitvoeren. Alleen `${FILAFLOW_PORT:-9000}` wordt gepubliceerd; PostgreSQL zit uitsluitend op het interne netwerk.

Open daarna `http://NAS-IP:9000` en meld aan met de initiële beheerder. De bootstrapgegevens maken alleen de eerste gebruiker aan; later wijzigen van `.env` verandert diens wachtwoord niet.

> De repository bevat de multi-arch GitHub Actions-build. Er kan vanuit deze lokale werkmap geen publieke image worden gepubliceerd zonder een eigen GitHub/GHCR-repository. Publiceer eerst de workflow of zet `FILAFLOW_IMAGE` op jouw bestaande registrytag.

### 3. Eerste inrichting

Voeg een printer toe met de single-, dual- of INDX T1–T8-preset. Voeg rollen handmatig of via OpenPrintTag toe en koppel ze in de printerloadout. Maak onder **Settings → PrusaSlicer API token** een token dat aan die printer is gebonden. FilaFlow toont direct de configuratieopdracht; het ruwe token wordt maar één keer getoond.

Configureer op de PrusaSlicer-pc:

```powershell
python client\prusa-hook\filaflow_hook.py --configure http://NAS-IP:9000 PRINTER_UUID ff_API_TOKEN
```

Voeg vervolgens de absolute Python-/scriptopdracht toe bij **Print Settings → Output options → Post-processing scripts**. Details staan in `client/prusa-hook/README.md`. Een server-, database- of netwerkstoring laat de printerupload ongemoeid; het bestand blijft lokaal in `%USERPROFILE%\.filaflow\outbox` en kan met `--retry` opnieuw worden aangeboden.

## Dagelijks gebruik

- **Weigh** corrigeert de administratie vanuit het gemeten totaalgewicht en de opgeslagen spoeltarra.
- **Empty** zet een voortijdig lege rol via een ledgercorrectie op nul, verwijdert hem uit een printerloadout en archiveert hem. De rol wordt nooit verwijderd en blijft onder **Spools → Archived** zichtbaar.
- Een rol met een zachte reservering door een open inboxjob moet eerst in die job worden omgekoppeld of de job moet worden afgewezen. Dit beïnvloedt de printer of lopende print niet.
- **Settings → OpenPrintTag → Synchronize** vervangt de actieve catalogus alleen na een volledig geldige import. Bij download-, DNS- of firewallproblemen blijft de vorige snapshot actief.

De volledige clientinstructies en probleemoplossing staan in [`client/prusa-hook/README.md`](client/prusa-hook/README.md). De volledige Synology-handleiding staat in [`docs/SYNOLOGY.md`](docs/SYNOLOGY.md).

## HTTPS via Synology Reverse Proxy

Maak in DSM **Control Panel → Login Portal → Advanced → Reverse Proxy** een regel van `https://filament.example.nl:443` naar `http://127.0.0.1:9000`. Koppel een certificaat, zet `FILAFLOW_PUBLIC_URL=https://filament.example.nl`, `FILAFLOW_COOKIE_SECURE=true` en zet `FILAFLOW_FORWARDED_ALLOW_IPS` alleen op het vertrouwde proxyadres/subnet. Herbouw daarna het project. Publiceer FilaFlow niet rechtstreeks zonder HTTPS en toegangsbeperking op internet.

## Back-up en herstel

De `backup`-service maakt dagelijks rond `BACKUP_HOUR` een gecomprimeerde custom-format dump. Op zondag wordt ook een wekelijkse kopie gemaakt. `BACKUP_DAILY_KEEP` en `BACKUP_WEEKLY_KEEP` zijn aantallen, niet leeftijden.

Handmatig back-uppen:

```sh
docker compose exec backup pg_dump --format=custom --compress=9 --file=/backups/daily/filaflow-manual.dump
```

Neem `/volume1/docker/filaflow/backups` op in Hyper Backup. Neem de live map `postgres` niet rechtstreeks op: een bestandssnapshot daarvan is geen vervanging voor een consistente `pg_dump`.

Herstellen naar een lege database:

```sh
docker compose stop app backup
docker compose exec -T db dropdb -U filaflow --if-exists filaflow
docker compose exec -T db createdb -U filaflow filaflow
docker compose exec -T db pg_restore -U filaflow -d filaflow --clean --if-exists < /volume1/docker/filaflow/backups/daily/filaflow-YYYYMMDD-HHMMSS.dump
docker compose start app backup
```

Gebruik de waarden uit `.env` als database/usernamen zijn aangepast. Test herstel periodiek op een apart project en controleer `/api/health` en dashboardtotalen.

## Updates en terugrollen

1. Maak een handmatige dump en noteer de huidige image-tag.
2. Wijzig `FILAFLOW_IMAGE` naar een vaste nieuwe tag en kies in Container Manager **Project → Action → Build/Start**. De app voert vóór starten `alembic upgrade head` uit.
3. Controleer health, login, rollen, loadouts en een testjob.

Voor terugrollen stop je het project, herstel je de dump die vóór de migratie is gemaakt, zet je de oude image-tag terug en start je opnieuw. Alleen de image terugzetten na een niet-achterwaarts-compatibele migratie is niet veilig.

## Ontwikkelen en testen

```sh
npm ci
npm run build
npm run build:spa
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/Scripts/python -m pytest backend/tests client/prusa-hook/test_hook.py
docker compose --env-file .env.example config --quiet
```

De frontend-productiebundel staat in `dist/spa`. De image bouwt libbgcode volgens de officiële CMake-preset en serveert frontend en API als één `app`-service. De workflow publiceert voor amd64 en arm64.

## Grenzen van v1

Geen printerbesturing, automatische printstatus, printgoedkeuring, harde voorraadblokkades, NFC, productbarcodes, Cura/Orca-hook, vocht-/droogbeheer, projectmanagement of uitgebreide businessanalytics. `NEEDS_REVIEW` is uitsluitend een administratieve waarschuwing.
