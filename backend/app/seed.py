"""Seed the Supabase project with the demonstration dataset.

    cd backend
    cp .env.example .env         # fill SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
    python -m app.seed           # run supabase/schema.sql in the SQL editor first

Idempotent: existing rows are replaced by primary key (upsert).
"""
from __future__ import annotations

import sys

from .config import SUPABASE_ENABLED, SUPABASE_KEY, SUPABASE_URL
from .dataset import build_all

CHUNK = 500
ORDER = ["farms", "plots", "sensor_readings", "satellite_scenes",
         "weather_forecast", "cultivation_history", "market_prices"]


def main() -> int:
    if not SUPABASE_ENABLED:
        print("SUPABASE_URL / key missing in backend/.env — nothing to seed.")
        print("The API still runs perfectly on the built-in demo tier.")
        return 1

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    data = build_all()

    for table in ORDER:
        rows = data[table]
        try:
            sb.table(table).delete().neq("id" if table in ("farms", "plots") else "plot_id", "__none__").execute()
        except Exception as exc:                             # noqa: BLE001
            print(f"  ! could not clear {table}: {exc}")
        inserted = 0
        for i in range(0, len(rows), CHUNK):
            batch = rows[i:i + CHUNK]
            sb.table(table).upsert(batch).execute()
            inserted += len(batch)
            print(f"  {table}: {inserted}/{len(rows)}", end="\r")
        print(f"  {table}: {inserted} rows inserted".ljust(48))

    print("\nSeed complete. Restart the API — it will now read from Supabase.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
