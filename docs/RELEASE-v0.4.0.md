# FilaFlow v0.4.0

FilaFlow v0.4.0 aligns eight-tool printers with G-code indexes and adds manual filament usage corrections.

- New and existing eight-tool layouts use G-code indexes 0–7 while remaining visibly labelled T1–T8, retaining their tool UUIDs and loadouts.
- Historical print-job snapshots and ledger entries are not rewritten.
- The spool inventory dialog can either accept a total measured weight including the spool or subtract a known consumed weight.
- Manual usage is recorded as a separate `MANUAL_CONSUMPTION` ledger correction and is not counted as a booked print.
- Subtraction that would produce negative inventory requires explicit confirmation and marks the spool as an inventory discrepancy.

The database migration is guarded by FilaFlow's existing verified pre-upgrade backup process.
