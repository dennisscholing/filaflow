# FilaFlow: korte installatie

## 1. Naar GitHub

Open PowerShell in de FilaFlow-map en voer uit:

```powershell
cd "C:\Users\denni\OneDrive\Documents\Codex"
git init
git branch -M main
git add .
git commit -m "Initial FilaFlow version"
gh repo create filaflow --public --source=. --remote=origin --push
git tag v0.1.2
git push origin v0.1.2
```

Open GitHub → **Actions** en wacht tot **Multi-arch container** groen is. Open daarna je GitHub-profiel → **Packages** → **filaflow** → **Package settings** en maak het package **Public**.

## 2. Op Synology

1. Maak in File Station `/volume1/docker/filaflow/project`.
2. Upload `docker-compose.yml`, de map `deploy` en `.env.example`.
3. Hernoem `.env.example` naar `.env` en vul je GitHub-naam, NAS-IP en wachtwoorden in. Gebruik:

   ```dotenv
   FILAFLOW_IMAGE=ghcr.io/JOUW-GITHUB-NAAM/filaflow:v0.1.2
   FILAFLOW_PORT=9000
   FILAFLOW_PUBLIC_URL=http://JOUW-NAS-IP:9000
   ```

4. Open **Container Manager → Project → Create**.
5. Kies `/volume1/docker/filaflow/project`, geef het project de naam `filaflow` en start het.
6. Open `http://JOUW-NAS-IP:9000`.

Zie [`SYNOLOGY.md`](SYNOLOGY.md) als DSM een melding over maprechten geeft.

## 3. PrusaSlicer

1. Voeg in FilaFlow je printer toe.
2. Open **Settings → PrusaSlicer API token**, kies de printer en maak een token.
3. Kopieer `client/prusa-hook/filaflow_hook.py` naar `C:\FilaFlow\filaflow_hook.py` op de PrusaSlicer-pc.
4. Voer de getoonde configuratieopdracht uit; het adres moet `http://JOUW-NAS-IP:9000` zijn.
5. Zet in PrusaSlicer bij **Print Settings → Output options → Post-processing scripts** één regel:

   ```text
   python "C:\FilaFlow\filaflow_hook.py"
   ```

6. Slice en exporteer een klein model. Controleer daarna **Print inbox** in FilaFlow.

De hook beïnvloedt de printerupload nooit; bij een storing blijft de job lokaal in de outbox staan.
