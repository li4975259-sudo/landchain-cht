from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

INIT_SQL = """
CREATE TABLE IF NOT EXISTS business_records (
    id          BIGSERIAL PRIMARY KEY,
    collection  VARCHAR(64)  NOT NULL,
    record_id   VARCHAR(128) NOT NULL,
    data        JSONB        NOT NULL,
    created_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (collection, record_id)
);
CREATE INDEX IF NOT EXISTS idx_br_collection ON business_records(collection);
CREATE INDEX IF NOT EXISTS idx_br_created_at ON business_records(created_at);
CREATE INDEX IF NOT EXISTS idx_br_data_gin ON business_records USING GIN(data);
"""


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _serialize_record(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row.get("data") or {})
    data.setdefault("record_id", row.get("record_id"))
    if row.get("created_at") is not None and "created_at" not in data:
        created = row["created_at"]
        data["created_at"] = created.isoformat() if isinstance(created, datetime) else created
    return data


class PostgresBusinessStore:
    """Read/write business JSON documents (e.g. order collection)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._conn: psycopg.Connection | None = None

        try:
            self._conn = psycopg.connect(self.settings.postgres_dsn, row_factory=dict_row)
            self._conn.autocommit = True
            self._init_schema()
        except Exception:
            logger.exception("Failed to connect PostgresBusinessStore")
            self._conn = None

    @property
    def is_available(self) -> bool:
        return self._conn is not None and not self._conn.closed

    @property
    def conn(self) -> psycopg.Connection | None:
        return self._conn

    def _init_schema(self) -> None:
        if self._conn is None:
            return
        self._conn.execute(INIT_SQL)

    def ping(self) -> bool:
        if not self.is_available or self._conn is None:
            return False
        try:
            self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def upsert_json_array(
        self,
        items: list[dict[str, Any]],
        *,
        collection: str | None = None,
    ) -> list[str]:
        if not items or not self.is_available or self._conn is None:
            return []

        collection_name = collection or self.settings.postgres_business_collection
        id_field = self.settings.postgres_business_id_field
        time_field = self.settings.postgres_business_time_field
        now = datetime.now(UTC)
        imported_ids: list[str] = []

        with self._conn.cursor() as cur:
            for item in items:
                if id_field not in item:
                    raise ValueError(f"Each item must contain '{id_field}' field")

                record = dict(item)
                record_id = str(record[id_field])
                record[id_field] = record_id

                created_at = _parse_datetime(record.get(time_field)) or now
                record["updated_at"] = now.isoformat()

                cur.execute(
                    """
                    INSERT INTO business_records (collection, record_id, data, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (collection, record_id)
                    DO UPDATE SET data = EXCLUDED.data,
                                  created_at = EXCLUDED.created_at,
                                  updated_at = EXCLUDED.updated_at
                    """,
                    (collection_name, record_id, Jsonb(record), created_at, now),
                )
                imported_ids.append(record_id)

        return imported_ids

    def get_by_id(
        self,
        id_value: str,
        *,
        collection: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.is_available or self._conn is None:
            return None

        collection_name = collection or self.settings.postgres_business_collection
        row = self._conn.execute(
            """
            SELECT collection, record_id, data, created_at
            FROM business_records
            WHERE collection = %s AND record_id = %s
            """,
            (collection_name, id_value),
        ).fetchone()
        return _serialize_record(row) if row else None

    def find_by_time_range(
        self,
        start: datetime,
        end: datetime,
        *,
        collection: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.is_available or self._conn is None:
            return []

        collection_name = collection or self.settings.postgres_business_collection
        time_field = self.settings.postgres_business_time_field
        rows = self._conn.execute(
            f"""
            SELECT collection, record_id, data, created_at
            FROM business_records
            WHERE collection = %s
              AND COALESCE(
                    created_at,
                    (data->>%s)::timestamptz
                  ) >= %s
              AND COALESCE(
                    created_at,
                    (data->>%s)::timestamptz
                  ) <= %s
            ORDER BY COALESCE(created_at, (data->>%s)::timestamptz)
            """,
            (collection_name, time_field, start, time_field, end, time_field),
        ).fetchall()
        return [_serialize_record(row) for row in rows]

    def count_records(self, collection: str | None = None) -> int:
        if not self.is_available or self._conn is None:
            return 0
        collection_name = collection or self.settings.postgres_business_collection
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM business_records WHERE collection = %s",
            (collection_name,),
        ).fetchone()
        return int(row["cnt"]) if row else 0

    def list_collections(self) -> list[dict[str, Any]]:
        if not self.is_available or self._conn is None:
            return []
        rows = self._conn.execute(
            """
            SELECT collection AS name, COUNT(*) AS count
            FROM business_records
            GROUP BY collection
            ORDER BY collection
            """
        ).fetchall()
        return [{"name": row["name"], "count": int(row["count"])} for row in rows]

    def sample_records(self, collection: str, limit: int = 50) -> list[dict[str, Any]]:
        if not self.is_available or self._conn is None:
            return []
        rows = self._conn.execute(
            """
            SELECT collection, record_id, data, created_at
            FROM business_records
            WHERE collection = %s
            ORDER BY id
            LIMIT %s
            """,
            (collection, limit),
        ).fetchall()
        return [_serialize_record(row) for row in rows]

    def dump_record(self, row: dict[str, Any]) -> str:
        return json.dumps(_serialize_record(row), ensure_ascii=False, default=str)
