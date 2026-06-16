#!/usr/bin/env python3

"""Daily order statistics from PostgreSQL order collection."""



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

from app.services.order_report import OrderReportGenerator

from app.services.postgres_business_store import PostgresBusinessStore

from scripts.tasks._contract import emit_json, fail, parse_args, resolve_date





def main() -> int:

    args = parse_args()

    task = "daily_orders"

    try:

        day = resolve_date(args.date)

        start = datetime.combine(day, datetime.min.time()).replace(tzinfo=datetime.now().astimezone().tzinfo)

        end = datetime.combine(day, datetime.max.time()).replace(tzinfo=start.tzinfo)

        settings = get_settings()

        store = PostgresBusinessStore(settings)

        if not store.is_available:

            fail(task, "PostgreSQL unavailable")

        gen = OrderReportGenerator(store, settings)

        orders = gen.fetch_orders(start, end)

        total_amount = sum(float(o.get("amount") or 0) for o in orders)

        payload = {

            "success": True,

            "task": task,

            "params": {"date": day.isoformat()},

            "data": {

                "date": day.isoformat(),

                "order_count": len(orders),

                "total_amount": round(total_amount, 2),

                "total_quantity": sum(int(o.get("quantity") or 0) for o in orders),

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

