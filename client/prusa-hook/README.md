# Connect PrusaSlicer to FilaFlow

One hook installation supports all printers in the same PrusaSlicer installation. It selects the FilaFlow printer from PrusaSlicer's environment in this order:

1. physical-printer profile;
2. general printer profile;
3. configured default printer.

The hook first copies every `.gcode` or `.bgcode` file to a local outbox and then starts a separate uploader. It does not modify G-code and always exits successfully when called by PrusaSlicer. An unavailable NAS or invalid FilaFlow configuration can therefore never cancel the normal printer upload.

## Requirements

- Python 3 on the PrusaSlicer computer.
- Every physical printer added in FilaFlow.
- One printer-bound API token per FilaFlow printer.
- `filaflow_hook.py` in a permanent location such as `C:\FilaFlow\filaflow_hook.py`.

## 1. Add the first printer

1. In FilaFlow, open **Settings → PrusaSlicer API token**.
2. Enter a recognizable token name and select the printer.
3. Click **Generate token**. The raw token is shown only once.
4. Copy the generated command and run it in PowerShell. It looks like this:

   ```powershell
   python C:\FilaFlow\filaflow_hook.py --add-printer "http://YOUR-NAS-IP:9000" "PRINTER_UUID" "ff_API_TOKEN" "Original Prusa MK4S 0.4 nozzle"
   ```

The first printer automatically becomes the default. Configuration is stored in `%USERPROFILE%\.filaflow\config.json`. Protect this file because it contains API tokens.

## 2. Add the other printers

Generate a printer-bound token and run the generated `--add-printer` command once for every additional printer. A PrusaSlicer profile name can belong to only one FilaFlow printer on that computer.

If one printer is used through an additional PrusaSlicer profile, add an alias:

```powershell
python C:\FilaFlow\filaflow_hook.py --add-profile "PRINTER_UUID" "My second profile name"
```

For two identical models, create and select separate **Physical printer** profiles in PrusaSlicer. Their physical profile names take priority and can therefore route to different FilaFlow printers.

Show the current mappings:

```powershell
python C:\FilaFlow\filaflow_hook.py --list-printers
```

Change the fallback printer:

```powershell
python C:\FilaFlow\filaflow_hook.py --set-default "PRINTER_UUID"
```

Remove a local printer mapping without deleting the printer in FilaFlow:

```powershell
python C:\FilaFlow\filaflow_hook.py --remove-printer "PRINTER_UUID"
```

An existing version-1 single-printer configuration is converted automatically. The old JSON is retained next to it as a timestamped `config-v1-....bak` file, and that printer remains the default.

## 3. Add the post-processing script once

Open **Print Settings → Output options → Post-processing scripts** in PrusaSlicer. On Windows, absolute paths are the most reliable:

```text
"C:\Users\YOUR_NAME\AppData\Local\Programs\Python\Python312\python.exe" "C:\FilaFlow\filaflow_hook.py"
```

If `python` works from PowerShell, this shorter line is sufficient:

```text
python "C:\FilaFlow\filaflow_hook.py"
```

Do not add a G-code path. PrusaSlicer appends its temporary file path automatically. Save the Print Settings profile, and use this same hook line for all printers. Prusa documents the available [post-processing environment variables](https://help.prusa3d.com/article/post-processing-scripts_283913?product=prusaslicer).

## 4. Test and retry

1. Select one configured physical printer or printer profile.
2. Slice a small model and export or send it as usual.
3. Check **Print inbox** in FilaFlow. The detected profile is shown on the job.
4. Repeat for the other printers.

An unknown profile uses the default FilaFlow printer and marks the inbox job **Needs review**. This affects inventory only; it does not change where PrusaSlicer sends the print. Use **Change printer** in the inbox before mapping, booking, or dismissing the job if necessary.

If nothing appears, inspect `%USERPROFILE%\.filaflow\filaflow-hook.log`. Failed uploads remain in `%USERPROFILE%\.filaflow\outbox`. Retry them without slicing again:

```powershell
python C:\FilaFlow\filaflow_hook.py --retry
```

Each outbox manifest permanently records the selected printer and routing method. A later profile-mapping change cannot redirect an already queued job.
