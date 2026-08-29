# FilaFlow v0.3.2

FilaFlow v0.3.2 is a database-neutral bugfix release for browser label printing.

## Fixes

- Print output now removes all screen padding and margins, so the label fits the custom-size page instead of overflowing onto a blank page.
- Each printed label uses the selected template's exact width and height in millimetres.
- The print button remains disabled until every SVG label image has loaded.
- Print output preserves backgrounds and colour swatches.
- Multiple selected labels continue on separate custom-size pages without adding a trailing blank page.

No schema migration is included. Existing templates and all inventory data remain unchanged.
