# FilaFlow v0.3.1

FilaFlow v0.3.1 is a database-neutral bugfix release for label printing and editing.

## Fixes

- Production deep links such as `/labels/print` and `/spools/{uuid}` now correctly load the single-page application instead of returning `{"detail":"Not Found"}`.
- Missing static assets still return a real 404 response.
- The label editor uses real CSS millimetres at 100% and offers independent 75%, 150%, and 200% screen zoom.
- Pointer dragging keeps the original grab position and snaps to 0.5 mm.
- Selected elements have a visible resize handle, keyboard movement and resizing, alignment controls, and a command to keep every element inside the label.
- QR elements remain square and at least 16 mm while editing.

No schema migration is included. Existing templates and all inventory data remain unchanged.
