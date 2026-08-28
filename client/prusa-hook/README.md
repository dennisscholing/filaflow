# PrusaSlicer verbinden met FilaFlow

De hook kopieert iedere geslicete `.gcode` of `.bgcode` eerst naar een lokale outbox en start daarna een losse uploader. De hook wijzigt de G-code niet en eindigt altijd met exitcode `0`. Een onbereikbare FilaFlow-server kan de gewone upload naar de printer daarom niet tegenhouden.

## Vereisten

- Python 3 op de computer waarop PrusaSlicer draait;
- een printer in FilaFlow;
- een administratoraccount om een printergebonden API-token te maken;
- het bestand `filaflow_hook.py` op een blijvende lokale locatie, bijvoorbeeld `C:\FilaFlow\filaflow_hook.py`.

## 1. Token en configuratie maken

1. Open FilaFlow en ga naar **Settings → PrusaSlicer API token**.
2. Vul een herkenbare naam in en selecteer de juiste printer.
3. Klik **Generate token**.
4. Kopieer de getoonde configuratieopdracht; het token wordt later niet opnieuw getoond.
5. Open PowerShell in de map van `filaflow_hook.py` en voer de opdracht uit, bijvoorbeeld:

   ```powershell
   python filaflow_hook.py --configure "http://NAS-IP:9000" "PRINTER_UUID" "ff_API_TOKEN"
   ```

De configuratie staat daarna in `%USERPROFILE%\.filaflow\config.json`. Bescherm dit bestand: het bevat het API-token.

## 2. Post-processing script instellen

Open in PrusaSlicer **Print Settings → Output options → Post-processing scripts**. Voeg één regel toe. Gebruik op Windows bij voorkeur zowel het absolute Pythonpad als het absolute scriptpad:

```text
"C:\Users\JOUW_NAAM\AppData\Local\Programs\Python\Python312\python.exe" "C:\FilaFlow\filaflow_hook.py"
```

Als `python` betrouwbaar op `PATH` staat, volstaat:

```text
python "C:\FilaFlow\filaflow_hook.py"
```

Voeg zelf geen G-codepad toe. PrusaSlicer plaatst het absolute tijdelijke G-codepad automatisch als laatste argument. Sla het Print Settings-profiel daarna op.

Zie ook Prusa's officiële uitleg over [post-processing scripts](https://help.prusa3d.com/article/post-processing-scripts_283913?product=prusaslicer).

## 3. Verbinding testen

1. Slice een klein testmodel.
2. Verstuur of exporteer de G-code zoals normaal.
3. Controleer in FilaFlow onder **Print inbox** of de job verschijnt.
4. Controleer bij problemen `%USERPROFILE%\.filaflow\filaflow-hook.log`.

Mislukte uploads blijven met hun manifest in `%USERPROFILE%\.filaflow\outbox`. Opnieuw verzenden kan zonder opnieuw te slicen:

```powershell
python C:\FilaFlow\filaflow_hook.py --retry
```

Een succesvolle retry verwijdert alleen het betreffende outboxbestand en manifest. Bij een blijvende fout blijven ze staan.

## Andere computer of printer

Voer `--configure` opnieuw uit op iedere PrusaSlicer-computer. Gebruik per printer of werkplek een afzonderlijk token. De huidige clientconfiguratie wijst per Windows-/Linux-gebruiker naar één printer; gebruik voor verschillende printers aparte werkplekken of een afzonderlijke gebruikers-/configuratieomgeving.
