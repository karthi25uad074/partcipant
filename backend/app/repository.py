"""Data access layer.

Single interface, three tiers of fallback so the API is never down:

  1. Supabase (Postgres)  — used when SUPABASE_URL + key are present.
  2. SQLite mirror        — every Supabase read is mirrored locally; writes queue here.
  3. Deterministic demo   — generated in-process by `dataset.build_all()`.

That chain is what delivers the "offline capability / fault tolerance"
non-functional requirement: the edge node keeps serving advisories with the last
synced snapshot when the network is gone, then replays queued writes on reconnect.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import dataset
from .config import LOCAL_DB, OFFLINE_CACHE, SUPABASE_ENABLED, SUPABASE_KEY, SUPABASE_URL

READ_TABLES = ["farms", "plots", "sensor_readings", "satellite_scenes",
               "weather_forecast", "cultivation_history", "market_prices"]
WRITE_TABLES = ["advisories", "predictions", "sms_outbox"]
_LOCK = threading.Lock()


class Repository:
    def __init__(self) -> None:
        self.source = "demo"
        self.supabase = None
        self.last_sync: Optional[str] = None
        self.errors: List[str] = []
        self._store: Dict[str, List[Dict[str, Any]]] = {}
        self._init_sqlite()
        self._bootstrap()

    # ------------------------------------------------------------- lifecycle
    def _init_sqlite(self) -> None:
        self.db = sqlite3.connect(LOCAL_DB, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS snapshot (table_name TEXT PRIMARY KEY, payload TEXT, synced_at TEXT)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS write_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT, table_name TEXT, payload TEXT,
            created_at TEXT, pushed INTEGER DEFAULT 0)""")
        self.db.commit()

    def _bootstrap(self) -> None:
        if SUPABASE_ENABLED:
            try:
                from supabase import create_client
                self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                for t in READ_TABLES:
                    rows = self.supabase.table(t).select("*").limit(50000).execute().data or []
                    if rows:
                        self._store[t] = rows
                if self._store.get("plots"):
                    self.source = "supabase"
                    self.last_sync = datetime.now(timezone.utc).isoformat()
                    self._persist_snapshot()
                    self._flush_queue()
                    return
                self.errors.append("Supabase reachable but empty — run `python -m app.seed`.")
            except Exception as exc:                       # noqa: BLE001
                self.errors.append(f"Supabase unavailable ({type(exc).__name__}: {exc}); using local tier.")

        if self._load_snapshot():
            self.source = "sqlite-cache"
            return
        self._store = {k: v for k, v in dataset.build_all().items() if isinstance(v, list)}
        self.source = "demo"
        self._persist_snapshot()

    # ---------------------------------------------------------------- caches
    def _persist_snapshot(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with _LOCK:
            for t, rows in self._store.items():
                self.db.execute("INSERT OR REPLACE INTO snapshot VALUES (?,?,?)", (t, json.dumps(rows), now))
            self.db.commit()
        try:
            OFFLINE_CACHE.write_text(json.dumps({"synced_at": now, "tables": {
                t: len(r) for t, r in self._store.items()}}, indent=2))
        except OSError:
            pass

    def _load_snapshot(self) -> bool:
        rows = self.db.execute("SELECT table_name, payload, synced_at FROM snapshot").fetchall()
        if not rows:
            return False
        for name, payload, synced in rows:
            self._store[name] = json.loads(payload)
            self.last_sync = synced
        return bool(self._store.get("plots"))

    def _flush_queue(self) -> None:
        if not self.supabase:
            return
        pending = self.db.execute(
            "SELECT id, table_name, payload FROM write_queue WHERE pushed = 0").fetchall()
        for row_id, table, payload in pending:
            try:
                self.supabase.table(table).insert(json.loads(payload)).execute()
                self.db.execute("UPDATE write_queue SET pushed = 1 WHERE id = ?", (row_id,))
            except Exception:                              # noqa: BLE001
                break
        self.db.commit()

    # ------------------------------------------------------------------ read
    def table(self, name: str) -> List[Dict[str, Any]]:
        return self._store.get(name, [])

    def where(self, name: str, **eq: Any) -> List[Dict[str, Any]]:
        return [r for r in self.table(name) if all(r.get(k) == v for k, v in eq.items())]

    def one(self, name: str, **eq: Any) -> Optional[Dict[str, Any]]:
        rows = self.where(name, **eq)
        return rows[0] if rows else None

    # ----------------------------------------------------------------- write
    def insert(self, table: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**payload, "created_at": payload.get("created_at") or datetime.now(timezone.utc).isoformat()}
        self._store.setdefault(table, []).append(payload)
        with _LOCK:
            self.db.execute("INSERT INTO write_queue (table_name, payload, created_at, pushed) VALUES (?,?,?,0)",
                            (table, json.dumps(payload), payload["created_at"]))
            self.db.commit()
        if self.supabase:
            try:
                self.supabase.table(table).insert(payload).execute()
                with _LOCK:
                    self.db.execute("UPDATE write_queue SET pushed = 1 WHERE table_name = ? AND created_at = ?",
                                    (table, payload["created_at"]))
                    self.db.commit()
            except Exception as exc:                       # noqa: BLE001
                self.errors.append(f"Queued offline write for {table}: {exc}")
        return payload

    # ---------------------------------------------------------------- status
    def status(self) -> Dict[str, Any]:
        queued = self.db.execute("SELECT COUNT(*) FROM write_queue WHERE pushed = 0").fetchone()[0]
        return {
            "source": self.source,
            "supabase_configured": SUPABASE_ENABLED,
            "last_sync": self.last_sync,
            "queued_writes": int(queued),
            "row_counts": {t: len(self._store.get(t, [])) for t in READ_TABLES + WRITE_TABLES},
            "warnings": self.errors[-4:],
        }


REPO: Optional[Repository] = None


def get_repo() -> Repository:
    global REPO
    if REPO is None:
        REPO = Repository()
    return REPO
