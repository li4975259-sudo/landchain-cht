from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

import psycopg

from app.config import Settings, get_settings
from app.services.order_report import OrderReportGenerator
from app.services.postgres_business_store import PostgresBusinessStore, _serialize_record
from app.services.table_schema import TableSchemaService


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: _serialize_value(v) for k, v in doc.items()}


def _truncate_result(payload: dict[str, Any], max_chars: int) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False)
    if len(text) <= max_chars:
        return payload
    return {**payload, "truncated": True, "preview": text[:max_chars]}


class PostgresQueryService:
    def __init__(
        self,
        store: PostgresBusinessStore | None,
        schema_service: TableSchemaService,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._store = store
        self.schema = schema_service

    def _conn(self) -> psycopg.Connection:
        if self._store is None or not self._store.is_available or self._store.conn is None:
            raise RuntimeError("PostgreSQL is not available")
        return self._store.conn

    def _ensure_collection(self, collection: str) -> None:
        if not self.schema.is_collection_allowed(collection):
            raise ValueError(f"Collection '{collection}' is not accessible")

    def _json_field(self, field: str) -> str:
        return f"data->>'{field}'"

    def _time_filter_sql(
        self,
        collection: str,
        from_date: str | None,
        to_date: str | None,
        time_field: str | None,
    ) -> tuple[list[str], list[Any], str | None]:
        if not from_date and not to_date:
            return [], [], time_field

        schema = self.schema.describe_collection(collection)
        field = time_field or schema.get("time_field")
        if not field:
            raise ValueError(f"No time field available for collection '{collection}'")
        self.schema.validate_field(collection, field)

        clauses: list[str] = []
        params: list[Any] = []
        expr = f"COALESCE(created_at, (data->>%s)::timestamptz)"
        params.append(field)
        if from_date:
            clauses.append(f"{expr} >= %s")
            params.append(_parse_datetime(from_date))
        if to_date:
            clauses.append(f"{expr} <= %s")
            params.append(_parse_datetime(to_date))
        return clauses, params, field

    def _filter_sql(
        self,
        collection: str,
        filters: dict[str, Any] | None,
    ) -> tuple[list[str], list[Any]]:
        if not filters:
            return [], []
        clauses: list[str] = []
        params: list[Any] = []
        for key, value in filters.items():
            self.schema.validate_field(collection, key)
            clauses.append(f"data->>%s = %s")
            params.extend([key, str(value)])
        return clauses, params

    def _base_where(
        self,
        collection: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        time_field: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> tuple[str, list[Any]]:
        clauses = ["collection = %s"]
        params: list[Any] = [collection]
        time_clauses, time_params, _ = self._time_filter_sql(
            collection, from_date, to_date, time_field
        )
        filter_clauses, filter_params = self._filter_sql(collection, filters)
        clauses.extend(time_clauses)
        clauses.extend(filter_clauses)
        params.extend(time_params)
        params.extend(filter_params)
        return " AND ".join(clauses), params

    def query(
        self,
        collection: str,
        action: str,
        *,
        id_value: str | None = None,
        id_field: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        time_field: str | None = None,
        field: str | None = None,
        op: str = "sum",
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        skip: int = 0,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        max_chars = self.settings.agent_tool_result_max_chars
        limit = min(max(limit, 1), 200)
        skip = max(skip, 0)
        conn = self._conn()
        self._ensure_collection(collection)

        if action == "get_by_id":
            if not id_value:
                raise ValueError("id is required for get_by_id")
            schema = self.schema.describe_collection(collection)
            fid = id_field or schema.get("id_field") or "record_id"
            self.schema.validate_field(collection, fid)
            row = conn.execute(
                f"""
                SELECT collection, record_id, data, created_at
                FROM business_records
                WHERE collection = %s
                  AND (record_id = %s OR data->>%s = %s)
                LIMIT 1
                """,
                (collection, id_value, fid, id_value),
            ).fetchone()
            record = _serialize_record(row) if row else None
            return _truncate_result(
                {"collection": collection, "record": _serialize_doc(record) if record else None},
                max_chars,
            )

        if action == "count":
            where, params = self._base_where(
                collection,
                from_date=from_date,
                to_date=to_date,
                time_field=time_field,
                filters=filters,
            )
            row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM business_records WHERE {where}",
                params,
            ).fetchone()
            total = int(row["cnt"]) if row else 0
            return {"collection": collection, "count": total}

        if action == "list_by_date_range":
            if not from_date or not to_date:
                raise ValueError("from_date and to_date are required")
            where, params = self._base_where(
                collection,
                from_date=from_date,
                to_date=to_date,
                time_field=time_field,
                filters=filters,
            )
            _, _, tf = self._time_filter_sql(collection, from_date, to_date, time_field)
            total_row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM business_records WHERE {where}",
                params,
            ).fetchone()
            total = int(total_row["cnt"]) if total_row else 0
            rows = conn.execute(
                f"""
                SELECT collection, record_id, data, created_at
                FROM business_records
                WHERE {where}
                ORDER BY COALESCE(created_at, (data->>%s)::timestamptz)
                OFFSET %s LIMIT %s
                """,
                [*params, tf or self.settings.postgres_business_time_field, skip, limit],
            ).fetchall()
            return _truncate_result(
                {
                    "collection": collection,
                    "time_field": tf,
                    "total": total,
                    "skip": skip,
                    "limit": limit,
                    "records": [_serialize_doc(_serialize_record(r)) for r in rows],
                },
                max_chars,
            )

        if action == "filter_list":
            where, params = self._base_where(
                collection,
                from_date=from_date,
                to_date=to_date,
                time_field=time_field,
                filters=filters or {},
            )
            rows = conn.execute(
                f"""
                SELECT collection, record_id, data, created_at
                FROM business_records
                WHERE {where}
                LIMIT %s
                """,
                [*params, limit],
            ).fetchall()
            docs = [_serialize_doc(_serialize_record(r)) for r in rows]
            return _truncate_result(
                {"collection": collection, "count": len(docs), "records": docs},
                max_chars,
            )

        if action == "distinct_values":
            if not field:
                raise ValueError("field is required")
            self.schema.validate_field(collection, field)
            where, params = self._base_where(collection)
            rows = conn.execute(
                f"""
                SELECT DISTINCT data->>%s AS value
                FROM business_records
                WHERE {where}
                LIMIT %s
                """,
                [field, *params, limit],
            ).fetchall()
            values = [_serialize_value(r["value"]) for r in rows if r.get("value") is not None]
            return {"collection": collection, "field": field, "values": values, "count": len(values)}

        if action == "aggregate_by_field":
            if not field:
                raise ValueError("field is required")
            self.schema.validate_field(collection, field)
            where, params = self._base_where(
                collection,
                from_date=from_date,
                to_date=to_date,
                time_field=time_field,
                filters=filters,
            )
            total_row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM business_records WHERE {where}",
                params,
            ).fetchone()
            total = int(total_row["cnt"]) if total_row else 0
            rows = conn.execute(
                f"""
                SELECT data->>%s AS value, COUNT(*) AS count
                FROM business_records
                WHERE {where}
                GROUP BY data->>%s
                ORDER BY count DESC
                LIMIT %s
                """,
                [field, *params, field, limit],
            ).fetchall()
            distribution = [
                {
                    "value": _serialize_value(r["value"]) if r["value"] is not None else "null",
                    "count": int(r["count"]),
                    "percentage": round(int(r["count"]) / total * 100, 2) if total else 0,
                }
                for r in rows
            ]
            return {
                "collection": collection,
                "field": field,
                "total_documents": total,
                "value_distribution": distribution,
            }

        if action == "aggregate_array_field":
            if not field:
                raise ValueError("field is required")
            self.schema.validate_field(collection, field)
            where, params = self._base_where(
                collection,
                from_date=from_date,
                to_date=to_date,
                time_field=time_field,
                filters=filters,
            )
            total_row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM business_records WHERE {where}",
                params,
            ).fetchone()
            total = int(total_row["cnt"]) if total_row else 0
            rows = conn.execute(
                f"""
                SELECT elem.value AS value, COUNT(*) AS count
                FROM business_records,
                     LATERAL jsonb_array_elements_text(
                         CASE
                             WHEN jsonb_typeof(data->%s) = 'array' THEN data->%s
                             ELSE '[]'::jsonb
                         END
                     ) AS elem(value)
                WHERE {where}
                GROUP BY elem.value
                ORDER BY count DESC
                LIMIT %s
                """,
                [field, field, *params, limit],
            ).fetchall()
            without_row = conn.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM business_records
                WHERE {where}
                  AND (
                    data->%s IS NULL
                    OR data->%s = 'null'::jsonb
                    OR data->%s = '[]'::jsonb
                    OR data->>%s = ''
                  )
                """,
                [*params, field, field, field, field],
            ).fetchone()
            distribution = [
                {
                    "value": _serialize_value(r["value"]),
                    "count": int(r["count"]),
                    "percentage": round(int(r["count"]) / total * 100, 2) if total else 0,
                }
                for r in rows
            ]
            return {
                "collection": collection,
                "field": field,
                "total_documents": total,
                "value_distribution": distribution,
                "documents_without_values": int(without_row["cnt"]) if without_row else 0,
            }

        if action == "aggregate_numeric":
            if not field:
                raise ValueError("field is required")
            self.schema.validate_field(collection, field)
            op_map = {"sum": "SUM", "avg": "AVG", "min": "MIN", "max": "MAX"}
            if op not in op_map:
                raise ValueError(f"Unsupported op: {op}")
            where, params = self._base_where(
                collection,
                from_date=from_date,
                to_date=to_date,
                time_field=time_field,
                filters=filters,
            )
            row = conn.execute(
                f"""
                SELECT {op_map[op]}((data->>%s)::double precision) AS result
                FROM business_records
                WHERE {where}
                """,
                [field, *params],
            ).fetchone()
            result = float(row["result"]) if row and row["result"] is not None else None
            return {"collection": collection, "field": field, "op": op, "result": result}

        if action == "aggregate_summary":
            if not from_date or not to_date:
                raise ValueError("from_date and to_date are required for aggregate_summary")
            store = PostgresBusinessStore(self.settings)
            gen = OrderReportGenerator(store, self.settings)
            start = _parse_datetime(from_date)
            end = _parse_datetime(to_date)
            orders = gen.fetch_orders(start, end, collection=collection)
            total_amount = sum(float(o.get("amount") or 0) for o in orders)
            dim_field = group_by or "brand"
            stats: dict[str, dict[str, float | int]] = defaultdict(lambda: {"count": 0, "amount": 0.0})
            for order in orders:
                key = str(order.get(dim_field) or "未知")
                stats[key]["count"] += 1
                stats[key]["amount"] += float(order.get("amount") or 0)
            return {
                "collection": collection or self.settings.postgres_business_collection,
                "period": {"from": from_date, "to": to_date},
                "total_orders": len(orders),
                "total_amount": round(total_amount, 2),
                "group_by": dim_field,
                "breakdown": [
                    {"value": k, "count": v["count"], "amount": round(v["amount"], 2)}
                    for k, v in sorted(stats.items(), key=lambda x: x[1]["amount"], reverse=True)
                ],
            }

        raise ValueError(f"Unknown action: {action}")
