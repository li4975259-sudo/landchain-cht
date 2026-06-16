#!/usr/bin/env python3

"""Daily UV/PV statistics (counts page_view events in PostgreSQL if present)."""



from __future__ import annotations



import sys

from datetime import datetime

from pathlib import Path



ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



from dotenv import load_dotenv



load_dotenv(ROOT / ".env")



from app.config import get_settings

from app.services.postgres_business_store import PostgresBusinessStore

from scripts.tasks._contract import emit_json, fail, parse_args, resolve_date





def main() -> int:

    args = parse_args()

    task = "daily_uv"

    try:

        day = resolve_date(args.date)

        settings = get_settings()

        store = PostgresBusinessStore(settings)

        if not store.is_available:

            fail(task, "PostgreSQL unavailable")



        collection = "page_views"

        uv = pv = 0

        top_pages: list[dict] = []



        if store.conn is not None:

            collections = {item["name"] for item in store.list_collections()}

            if collection in collections:

                start = datetime.combine(day, datetime.min.time())

                end = datetime.combine(day, datetime.max.time())

                pv_row = store.conn.execute(

                    """

                    SELECT COUNT(*) AS cnt

                    FROM business_records

                    WHERE collection = %s

                      AND COALESCE(created_at, (data->>'created_at')::timestamptz) >= %s

                      AND COALESCE(created_at, (data->>'created_at')::timestamptz) <= %s

                    """,

                    (collection, start, end),

                ).fetchone()

                pv = int(pv_row["cnt"]) if pv_row else 0

                if pv:

                    uv_row = store.conn.execute(

                        """

                        SELECT COUNT(DISTINCT data->>'visitor_id') AS cnt

                        FROM business_records

                        WHERE collection = %s

                          AND COALESCE(created_at, (data->>'created_at')::timestamptz) >= %s

                          AND COALESCE(created_at, (data->>'created_at')::timestamptz) <= %s

                        """,

                        (collection, start, end),

                    ).fetchone()

                    uv = int(uv_row["cnt"]) if uv_row else 0

                    rows = store.conn.execute(

                        """

                        SELECT data->>'path' AS path,

                               COUNT(DISTINCT data->>'visitor_id') AS uv

                        FROM business_records

                        WHERE collection = %s

                          AND COALESCE(created_at, (data->>'created_at')::timestamptz) >= %s

                          AND COALESCE(created_at, (data->>'created_at')::timestamptz) <= %s

                        GROUP BY data->>'path'

                        ORDER BY uv DESC

                        LIMIT 10

                        """,

                        (collection, start, end),

                    ).fetchall()

                    top_pages = [{"path": r["path"], "uv": int(r["uv"])} for r in rows]



        payload = {

            "success": True,

            "task": task,

            "params": {"date": day.isoformat()},

            "data": {

                "date": day.isoformat(),

                "uv": uv,

                "pv": pv,

                "source_collection": collection if pv else "none",

                "top_pages": top_pages,

                "note": "Connect page_views collection or customize script data source",

            },

            "report_path": None,

        }

        emit_json(payload)

        return 0

    except Exception as exc:

        fail(task, str(exc))

        return 1





if __name__ == "__main__":

    raise SystemExit(main())

