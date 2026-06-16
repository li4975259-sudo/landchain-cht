#!/usr/bin/env python3
"""Generate and insert test order records into PostgreSQL business collection."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.config import get_settings
from app.services.postgres_business_store import PostgresBusinessStore

CUSTOMERS = ("张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十")
WINE_PRODUCTS = (
    {"name": "怀仁老窖 52度", "type": "白酒", "brand": "怀仁老窖", "spec": "500ml", "unit_price": 168.0},
    {"name": "朔州特曲 45度", "type": "白酒", "brand": "朔州特曲", "spec": "500ml", "unit_price": 98.0},
    {"name": "晋北陈酿 53度", "type": "白酒", "brand": "晋北陈酿", "spec": "500ml", "unit_price": 258.0},
    {"name": "云中珍藏 干红", "type": "红酒", "brand": "云中珍藏", "spec": "750ml", "unit_price": 128.0},
    {"name": "黄土高原 干白", "type": "红酒", "brand": "黄土高原", "spec": "750ml", "unit_price": 88.0},
    {"name": "老陈醋配餐黄酒", "type": "黄酒", "brand": "晋韵", "spec": "500ml", "unit_price": 45.0},
    {"name": "精酿原浆啤酒", "type": "啤酒", "brand": "朔州鲜酿", "spec": "330ml", "unit_price": 6.5},
    {"name": "宴会定制礼盒装", "type": "白酒", "brand": "怀仁礼宴", "spec": "500ml×2", "unit_price": 398.0},
)
CHANNELS = ("门店零售", "电商小程序", "企业团购", "宴会定制", "经销商批发")
STATUSES = ("待付款", "已付款", "已发货", "已完成", "已取消")
REGIONS = ("怀仁", "朔州", "大同", "太原")


def build_orders(
    count: int,
    *,
    id_prefix: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    if count <= 0:
        return []

    span_seconds = max(int((end - start).total_seconds()), 1)
    step = span_seconds / count
    orders: list[dict] = []

    for index in range(count):
        order_id = f"{id_prefix}{index + 1:04d}"
        created_at = start + timedelta(seconds=int(step * index))
        product = WINE_PRODUCTS[index % len(WINE_PRODUCTS)]
        quantity = (index % 12) + 1
        unit_price = product["unit_price"]
        amount = round(unit_price * quantity, 2)
        orders.append(
            {
                "ID": order_id,
                "created_at": created_at.isoformat().replace("+00:00", "Z"),
                "customer": CUSTOMERS[index % len(CUSTOMERS)],
                "product_name": product["name"],
                "wine_type": product["type"],
                "brand": product["brand"],
                "spec": product["spec"],
                "unit_price": unit_price,
                "quantity": quantity,
                "amount": amount,
                "channel": CHANNELS[index % len(CHANNELS)],
                "status": STATUSES[index % len(STATUSES)],
                "region": REGIONS[index % len(REGIONS)],
                "remark": f"酒类订单 {order_id}，{product['name']} × {quantity}",
            }
        )

    return orders


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed PostgreSQL order collection with test data")
    parser.add_argument("--count", type=int, default=1000, help="Number of orders to create")
    parser.add_argument(
        "--collection",
        default=None,
        help="Target collection (default: MONGODB_BUSINESS_COLLECTION)",
    )
    parser.add_argument(
        "--id-prefix",
        default="O",
        help="Order ID prefix, e.g. O -> O0001",
    )
    parser.add_argument(
        "--from",
        dest="from_time",
        default="2025-01-01T00:00:00Z",
        help="Start created_at for generated orders",
    )
    parser.add_argument(
        "--to",
        dest="to_time",
        default="2026-06-30T23:59:59Z",
        help="End created_at for generated orders",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="PostgreSQL upsert batch size",
    )
    args = parser.parse_args()

    settings = get_settings()
    collection = args.collection or settings.postgres_business_collection
    start = datetime.fromisoformat(args.from_time.replace("Z", "+00:00"))
    end = datetime.fromisoformat(args.to_time.replace("Z", "+00:00"))

    business_store = PostgresBusinessStore(settings)
    if not business_store.is_available:
        print("PostgreSQL business store is unavailable", file=sys.stderr)
        return 1

    orders = build_orders(
        args.count,
        id_prefix=args.id_prefix,
        start=start,
        end=end,
    )
    imported_total = 0
    batch_size = max(args.batch_size, 1)

    for offset in range(0, len(orders), batch_size):
        batch = orders[offset : offset + batch_size]
        imported_ids = business_store.upsert_json_array(batch, collection=collection)
        imported_total += len(imported_ids)
        print(f"Upserted batch {offset // batch_size + 1}: {len(imported_ids)} records")

    total_in_collection = business_store.count_records(collection)

    print(f"Collection: {collection}")
    print(f"Generated: {len(orders)}")
    print(f"Upserted: {imported_total}")
    print(f"Total documents in collection: {total_in_collection}")
    print(f"Sample ID range: {orders[0]['ID']} .. {orders[-1]['ID']}")
    print("Next: python scripts/sync_orders_to_rag.py --from ... --to ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
