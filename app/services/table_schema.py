from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any

import psycopg
import yaml

from app.config import Settings, get_settings
from app.services.postgres_business_store import PostgresBusinessStore

TIME_FIELD_PATTERN = re.compile(
    r"^(created_at|updated_at|registered_at|.*_at|.*_date|date)$",
    re.I,
)
ID_FIELD_PATTERN = re.compile(r"^(_id|.*_id|ID|record_id)$", re.I)
FIELD_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _infer_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "number"
    if isinstance(value, datetime):
        return "date"
    if isinstance(value, str):
        if re.match(r"^\d{4}-\d{2}-\d{2}", value):
            return "date"
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


class TableSchemaService:
    def __init__(
        self,
        store: PostgresBusinessStore | None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._store = store
        self._cache_loaded_at = 0.0
        self._cache: dict[str, dict[str, Any]] = {}
        self._overrides = self._load_overrides()

    def _load_overrides(self) -> dict[str, dict[str, Any]]:
        path = self.settings.postgres_collection_overrides_path
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}
        except (OSError, yaml.YAMLError):
            return {}

    def _load_disk_cache(self) -> None:
        path = self.settings.postgres_schema_cache_path
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            self._cache = payload.get("schemas", {})
            self._cache_loaded_at = payload.get("loaded_at", 0.0)
        except (OSError, json.JSONDecodeError):
            self._cache = {}

    def _save_disk_cache(self) -> None:
        path = self.settings.postgres_schema_cache_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                {"loaded_at": self._cache_loaded_at, "schemas": self._cache},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def is_collection_allowed(self, name: str) -> bool:
        if name.startswith("system."):
            return False
        if name in self.settings.postgres_agent_denylist:
            return False
        allow = self.settings.postgres_agent_allowlist
        if allow and name not in allow:
            return False
        return True

    def list_collections(self) -> list[dict[str, Any]]:
        if self._store is None or not self._store.is_available:
            return []
        return [
            item
            for item in self._store.list_collections()
            if self.is_collection_allowed(item["name"])
        ]

    def describe_collection(self, collection: str, *, force_refresh: bool = False) -> dict[str, Any]:
        if self._store is None or not self._store.is_available:
            raise RuntimeError("PostgreSQL is not available")
        if not self.is_collection_allowed(collection):
            raise ValueError(f"Collection '{collection}' is not accessible")

        now = time.time()
        if not force_refresh:
            if not self._cache:
                self._load_disk_cache()
            if (
                collection in self._cache
                and now - self._cache_loaded_at < self.settings.postgres_schema_cache_ttl
            ):
                return self._cache[collection]

        sample_size = self.settings.postgres_schema_sample_size
        samples = self._store.sample_records(collection, limit=sample_size)
        schema = self._infer_schema(collection, samples)
        self._cache[collection] = schema
        self._cache_loaded_at = now
        self._save_disk_cache()
        return schema

    def _infer_schema(self, collection: str, samples: list[dict[str, Any]]) -> dict[str, Any]:
        override = self._overrides.get(collection, {})
        fields: dict[str, dict[str, Any]] = {}

        for doc in samples:
            for key, value in doc.items():
                if key not in fields:
                    fields[key] = {"type": _infer_type(value), "nullable": False, "examples": []}
                entry = fields[key]
                if value is None:
                    entry["nullable"] = True
                if len(entry["examples"]) < 5 and value is not None:
                    ex = value.isoformat() if isinstance(value, datetime) else value
                    if ex not in entry["examples"]:
                        entry["examples"].append(ex)

        candidate_time_fields: list[str] = []
        candidate_id_fields: list[str] = []
        array_fields: list[str] = []
        aggregatable_fields: list[str] = []

        for name, meta in fields.items():
            if TIME_FIELD_PATTERN.match(name) or meta["type"] == "date":
                candidate_time_fields.append(name)
            if ID_FIELD_PATTERN.match(name):
                candidate_id_fields.append(name)
            if meta["type"] == "array":
                array_fields.append(name)
            if meta["type"] in {"string", "bool"}:
                distinct = {str(doc.get(name)) for doc in samples if doc.get(name) is not None}
                if len(distinct) <= 100:
                    aggregatable_fields.append(name)
            if meta["type"] in {"int", "number"}:
                aggregatable_fields.append(name)

        return {
            "collection": collection,
            "document_count": len(samples),
            "sample_size": len(samples),
            "fields": fields,
            "candidate_time_fields": candidate_time_fields,
            "candidate_id_fields": candidate_id_fields,
            "time_field": override.get("time_field")
            or (candidate_time_fields[0] if candidate_time_fields else None),
            "id_field": override.get("id_field")
            or (candidate_id_fields[0] if candidate_id_fields else "record_id"),
            "array_fields": override.get("array_fields") or array_fields,
            "aggregatable_fields": aggregatable_fields,
        }

    def validate_field(self, collection: str, field: str) -> None:
        if not FIELD_NAME_PATTERN.match(field):
            raise ValueError(f"Invalid field name: {field}")
        schema = self.describe_collection(collection)
        if field not in schema["fields"]:
            raise ValueError(f"Unknown field '{field}' in collection '{collection}'")

    def sample_records(self, collection: str, limit: int = 5) -> list[dict[str, Any]]:
        if self._store is None or not self._store.is_available:
            raise RuntimeError("PostgreSQL is not available")
        if not self.is_collection_allowed(collection):
            raise ValueError(f"Collection '{collection}' is not accessible")
        return self._store.sample_records(collection, limit=min(limit, 50))
