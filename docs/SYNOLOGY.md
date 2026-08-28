# FilaFlow installeren op Synology

Deze installatie gebruikt Synology DSM 7.2 met **Container Manager**. De NAS bouwt FilaFlow niet zelf; `FILAFLOW_IMAGE` moet verwijzen naar een vooraf gepubliceerde `linux/amd64`/`linux/arm64` image.

## 0. Eerst de containerimage publiceren

De meegeleverde workflow `.github/workflows/container.yml` bouwt beide architecturen en publiceert naar GitHub Container Registry. De standaardwaarde `ghcr.io/filaflow-app/filaflow:latest` is een voorbeeld en werkt pas als daar daadwerkelijk een publieke image staat.

1. Plaats de broncode in een GitHub-repository.
2. Push naar de standaardbranch of maak een tag, bijvoorbeeld `v0.1.4`.
3. Controleer in GitHub onder **Actions** of `Multi-arch container` geslaagd is.
4. Maak het GHCR-package publiek, zodat Synology zonder registry-wachtwoord kan downloaden.
5. Gebruik bij voorkeur een vaste versie in `.env`:

   ```dotenv
   FILAFLOW_IMAGE=ghcr.io/JOUW-GITHUB-NAAM/filaflow:v0.1.4
   ```

Gebruik `latest` alleen voor testen; een vaste tag maakt terugrollen voorspelbaar.

## 1. Mappen maken

Maak met File Station deze structuur:

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

Kopieer `docker-compose.yml`, `deploy/backup.sh` en een ingevulde kopie van `.env.example` naar de aangegeven projectmap. Bestanden die met een punt beginnen zijn mogelijk verborgen in File Station; upload `.env` rechtstreeks naar de map.

## 2. Maprechten instellen

Open **Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script**. Kies gebruiker `root`, voer het onderstaande script één keer uit en verwijder of deactiveer de taak daarna:

```sh
chown -R 70:70 /volume1/docker/filaflow/postgres /volume1/docker/filaflow/backups
chown -R 10001:10001 /volume1/docker/filaflow/config
chmod 750 /volume1/docker/filaflow/postgres /volume1/docker/filaflow/backups /volume1/docker/filaflow/config
chmod 755 /volume1/docker/filaflow/project/deploy/backup.sh
```

Gebruik geen `chmod 777`. Als je opslagvolume niet `volume1` heet, pas zowel deze paden als `FILAFLOW_DATA_ROOT` aan.

## 3. `.env` invullen

Minimale configuratie:

```dotenv
FILAFLOW_IMAGE=ghcr.io/JOUW-GITHUB-NAAM/filaflow:v0.1.4
FILAFLOW_DATA_ROOT=/volume1/docker/filaflow
FILAFLOW_PORT=9000
FILAFLOW_PUBLIC_URL=http://192.168.1.10:9000
FILAFLOW_COOKIE_SECURE=false
FILAFLOW_FORWARDED_ALLOW_IPS=127.0.0.1

POSTGRES_DB=filaflow
POSTGRES_USER=filaflow
POSTGRES_PASSWORD=EEN-LANG-UNIEK-DATABASEWACHTWOORD
FILAFLOW_SECRET_KEY=MINSTENS-64-WILLEKEURIGE-TEKENS
FILAFLOW_ADMIN_EMAIL=jouw-adres@example.nl
FILAFLOW_ADMIN_PASSWORD=EEN-LANG-UNIEK-BEHEERDERSWACHTWOORD

BACKUP_DAILY_KEEP=7
BACKUP_WEEKLY_KEEP=4
BACKUP_HOUR=2
```

`FILAFLOW_ADMIN_EMAIL` en `FILAFLOW_ADMIN_PASSWORD` worden alleen gebruikt wanneer de database nog geen gebruiker bevat. Latere wijzigingen in `.env` wijzigen het bestaande account niet.

## 4. Project aanmaken in Container Manager

1. Installeer en open **Container Manager** vanuit Package Center.
2. Ga naar **Project → Create**.
3. Gebruik projectnaam `filaflow`.
4. Selecteer `/volume1/docker/filaflow/project` als pad.
5. Kies het aanwezige `docker-compose.yml` als bron.
6. Controleer de YAML-validatie en laat het project direct starten.
7. Wacht totdat `filaflow-db` healthy is en `filaflow-app` draait.

Open vervolgens `http://IP-VAN-DE-NAS:9000` en meld aan met de beheerder uit `.env`. Ga naar **Settings → Users → Add user** om gewone operators of extra administrators aan te maken.

## 5. Controleren na installatie

- **Overview** opent zonder foutmelding.
- **Settings → OpenPrintTag → Synchronize** haalt de catalogus op.
- In Container Manager is de databasepoort niet gepubliceerd; alleen poort `9000` is vanaf het netwerk bereikbaar.
- In `/volume1/docker/filaflow/backups/daily` verschijnt na de ingestelde tijd een dump.
- `http://IP-VAN-DE-NAS:9000/api/health` retourneert `{"status":"ok"}`.

## 6. HTTPS via Synology Reverse Proxy (optioneel)

Ga naar **Control Panel → Login Portal → Advanced → Reverse Proxy → Create**:

- Source: `HTTPS`, jouw hostnaam, poort `443`;
- Destination: `HTTP`, `127.0.0.1`, poort `9000`;
- koppel bij **Security → Certificate** een certificaat aan de hostnaam.

Wijzig daarna `.env`:

```dotenv
FILAFLOW_PUBLIC_URL=https://filament.example.nl
FILAFLOW_COOKIE_SECURE=true
```

Bouw/start het project opnieuw vanuit Container Manager. Publiceer de applicatie niet onbeperkt op internet; beperk toegang bij voorkeur via VPN, firewall of een Synology access-control profile.

## 7. PrusaSlicer verbinden

1. Voeg eerst de printer toe in FilaFlow.
2. Ga naar **Settings → PrusaSlicer API token**, geef het token een naam en selecteer de printer.
3. Genereer het token en voer de getoonde `--configure`-opdracht uit op de PrusaSlicer-computer.
4. Plaats `client/prusa-hook/filaflow_hook.py` op een vaste lokale locatie.
5. Voeg in PrusaSlicer onder **Print Settings → Output options → Post-processing scripts** de Python- en scriptopdracht toe.
6. Slice en verstuur een klein testmodel; controleer daarna **Print inbox**.

PrusaSlicer geeft het tijdelijke G-codepad zelf als laatste argument door. De hook kopieert dit bestand naar een lokale outbox en retourneert altijd succes, ook als FilaFlow of de NAS niet bereikbaar is. Zie [`client/prusa-hook/README.md`](../client/prusa-hook/README.md) voor Windows-voorbeelden, logging en opnieuw verzenden.

## 8. Back-up, update en terugrollen

Neem alleen `/volume1/docker/filaflow/backups` op in Hyper Backup. Kopieer de live PostgreSQL-datamap niet als vervanging voor `pg_dump`.

Voor een update:

1. maak een handmatige databaseback-up;
2. noteer de huidige `FILAFLOW_IMAGE`;
3. zet een nieuwe vaste image-tag in `.env`;
4. kies in Container Manager bij het project **Action → Build** en daarna **Start**;
5. controleer login, catalogus, rollen, printers en `/api/health`.

Voor terugrollen herstel je de dump van vóór de update en zet je de oude image-tag terug. Alleen de oude image terugzetten is niet voldoende wanneer de nieuwe versie een database-migratie heeft uitgevoerd.
