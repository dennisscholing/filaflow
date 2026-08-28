# Connect PrusaSlicer to FilaFlow

The hook first copies each sliced `.gcode` or `.bgcode` file to a local outbox and then starts a separate uploader. It does not modify G-code and always exits with code `0`. An unavailable NAS or FilaFlow server therefore cannot stop the normal printer upload.

## Requirements

- Python 3 on the PrusaSlicer computer.
- A printer configured in FilaFlow.
- A printer-bound API token created by an administrator.
- `filaflow_hook.py` in a permanent location such as `C:\FilaFlow\filaflow_hook.py`.

## 1. Configure the token

1. In FilaFlow, open **Settings → PrusaSlicer API token**.
2. Enter a recognizable name and select the printer.
3. Click **Generate token**.
4. Copy the generated configuration command. The raw token is shown only once.
5. Run the command in PowerShell, for example:

   ```powershell
   python C:\FilaFlow\filaflow_hook.py --configure "http://YOUR-NAS-IP:9000" "PRINTER_UUID" "ff_API_TOKEN"
   ```

The configuration is stored in `%USERPROFILE%\.filaflow\config.json`. Protect this file because it contains the API token.

## 2. Add the post-processing script

Open **Print Settings → Output options → Post-processing scripts** in PrusaSlicer. On Windows, using absolute paths is the most reliable option:

```text
"C:\Users\YOUR_NAME\AppData\Local\Programs\Python\Python312\python.exe" "C:\FilaFlow\filaflow_hook.py"
```

If `python` works from PowerShell, this shorter command is sufficient:

```text
python "C:\FilaFlow\filaflow_hook.py"
```

Do not add a G-code path. PrusaSlicer automatically appends the temporary file path as the final argument. Save the Print Settings profile.

Prusa also documents [post-processing scripts](https://help.prusa3d.com/article/post-processing-scripts_283913?product=prusaslicer).

## 3. Test and retry

1. Slice a small model.
2. Export or send it as usual.
3. Check **Print inbox** in FilaFlow.
4. If nothing appears, inspect `%USERPROFILE%\.filaflow\filaflow-hook.log`.

Failed uploads remain in `%USERPROFILE%\.filaflow\outbox`. Retry them without slicing again:

```powershell
python C:\FilaFlow\filaflow_hook.py --retry
```

A successful retry removes only that upload and its manifest. Failed items remain in the outbox.

## Multiple computers or printers

Run `--configure` on every PrusaSlicer computer and use a separate token for each printer or workstation. The current client configuration points one operating-system user to one printer; use separate workstations or user/configuration environments when one computer must maintain independent mappings.
