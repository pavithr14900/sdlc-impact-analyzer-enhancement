# Legacy intelligence sample: claims service

This small source-only fixture is safe to index without running its code or installing dependencies.

- `app.py`: Flask `POST /claims` and `GET /claims/<int:claim_id>` endpoints.
- `services.py`: `ClaimsService`, claim validation, and a senior loyalty discount condition.
- `repository.py`: SQLite inserts and reads from the `claims` table.
- `schema.sql`: definitions for the `claims` and `claim_audit` tables.
- `jobs.py`: an hourly scheduled reconciliation task and an external notification API call.

The create flow is `create_claim` → `ClaimsService.submit_claim` → `ClaimsService.calculate_discount` / `save_claim`.
Customers aged at least 60 with at least 10 membership years receive a 15% discount.
Use this directory as a Local Folder source in Legacy Code Intelligence. No credentials or production data are included.
