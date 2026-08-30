# FilaFlow v0.5.0

FilaFlow v0.5.0 makes dashboard reservations representative of the complete print inbox and adds secure password management.

- Dashboard Reserved includes every `NEW`, `MAPPED`, and `NEEDS_REVIEW` job exactly once.
- Reserved is split into mapped and unassigned estimates; Available subtracts every open job estimate.
- The redundant Remaining dashboard card is removed while remaining inventory stays available on spool details and through the API.
- Users can change their own password after confirming the current password.
- Administrators can assign temporary passwords to other users and require a change at the next sign-in.
- Password changes invalidate existing browser sessions without revoking printer-bound API tokens.

The additive database migration is protected by FilaFlow's verified pre-upgrade backup gate.
