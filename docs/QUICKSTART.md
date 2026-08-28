# FilaFlow quick start

GitHub is ready when the **Multi-arch container** Action is green. Before installing on Synology, open your GitHub profile → **Packages** → **filaflow** → **Package settings** and confirm that package visibility is **Public**.

## 1. Prepare Synology

1. In File Station, create `/volume1/docker/filaflow/project`.
2. Upload these items from the repository into that folder:
   - `docker-compose.yml`
   - `.env.example`
   - the complete `deploy` folder
3. Rename `.env.example` to `.env`.
4. Edit `.env` and replace only the three password/secret placeholders. Keep the single quotes around their values.

You do not need to enter an image version or NAS IP.

## 2. Start FilaFlow

1. Open **Container Manager → Project → Create**.
2. Name the project `filaflow`.
3. Select `/volume1/docker/filaflow/project`.
4. Use the uploaded `docker-compose.yml` and start the project.
5. Open `http://YOUR-NAS-IP:9000`.

If DSM reports a folder permission error, follow [Folder permissions](SYNOLOGY.md#2-set-folder-permissions).

## 3. Connect PrusaSlicer

1. Add your printer in FilaFlow.
2. Open **Settings → PrusaSlicer API token** and create a token for that printer.
3. Copy `client/prusa-hook/filaflow_hook.py` to `C:\FilaFlow\filaflow_hook.py` on the PrusaSlicer computer.
4. Run the configuration command shown by FilaFlow.
5. Add this under **Print Settings → Output options → Post-processing scripts**:

   ```text
   python "C:\FilaFlow\filaflow_hook.py"
   ```

6. Slice and export a small model, then check **Print inbox** in FilaFlow.

The hook never blocks the printer upload. Failed inventory uploads remain in the local outbox for retry.

## Updating later

1. Make a manual backup.
2. In Container Manager, open **Image**, select `filaflow`, and choose **Action → Update** when shown.
3. Open **Project**, select `filaflow`, choose **Action → Build**, then **Start**.

No image tag or YAML version needs to be changed.
