from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.services.postgres_business_store import PostgresBusinessStore

INTERNAL_FIELDS = frozenset(
    {
        "_id",
        "updated_at",
        "rag_source",
        "rag_status",
        "rag_synced_at",
        "rag_error",
    }
)


def _parse_created_at(value: Any) -> datetime | None:
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


def _fmt_date(value: Any) -> str:
    dt = _parse_created_at(value)
    if dt is None:
        return str(value) if value is not None else "-"
    return dt.strftime("%Y-%m-%d")


def _fmt_month(value: Any) -> str:
    dt = _parse_created_at(value)
    if dt is None:
        return "unknown"
    return dt.strftime("%Y-%m")


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in INTERNAL_FIELDS}


class OrderReportGenerator:
    def __init__(
        self,
        business_store: PostgresBusinessStore,
        settings: Settings | None = None,
    ) -> None:
        self.business_store = business_store
        self.settings = settings or get_settings()

    def fetch_orders(
        self,
        start: datetime,
        end: datetime,
        *,
        collection: str | None = None,
    ) -> list[dict[str, Any]]:
        raw = self.business_store.find_by_time_range(start, end, collection=collection)
        return [_clean_record(record) for record in raw]

    @staticmethod
    def build_output_path(
        start: datetime,
        end: datetime,
        output_dir: Path | None = None,
    ) -> Path:
        directory = output_dir or Path("./data/orders")
        start_label = start.strftime("%Y-%m-%d")
        end_label = end.strftime("%Y-%m-%d")
        return directory / f"order-report_{start_label}_{end_label}.md"

    def render_markdown(
        self,
        orders: list[dict[str, Any]],
        *,
        start: datetime,
        end: datetime,
    ) -> str:
        generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        start_label = start.strftime("%Y-%m-%d")
        end_label = end.strftime("%Y-%m-%d")

        total_orders = len(orders)
        total_amount = sum(_safe_float(o.get("amount")) for o in orders)
        total_quantity = sum(_safe_int(o.get("quantity")) for o in orders)
        avg_amount = total_amount / total_orders if total_orders else 0.0

        lines: list[str] = [
            "# 订单经营数据报告",
            "",
            f"> **数据说明**：本报告由 PostgreSQL 订单集合按 `created_at` 区间 `{start_label}` 至 `{end_label}` 自动生成。",
            f"> **生成时间**：{generated_at}  ",
            f"> **订单总数**：{total_orders}  ",
            "> **用途**：供 LandChain RAG 检索，支持销售额、渠道、品牌、区域及订单明细等业务问答。",
            "",
            "---",
            "",
            "## 汇总 KPI",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 订单总数 | {total_orders} |",
            f"| 总销售额（元） | {_fmt_money(total_amount)} |",
            f"| 总销量 | {total_quantity:,} |",
            f"| 客单价（元） | {_fmt_money(avg_amount)} |",
            "",
        ]

        lines.extend(self._render_monthly_section(orders))
        lines.extend(self._render_dimension_section(orders, "brand", "品牌"))
        lines.extend(self._render_dimension_section(orders, "channel", "渠道"))
        lines.extend(self._render_dimension_section(orders, "region", "区域"))
        lines.extend(self._render_dimension_section(orders, "wine_type", "酒类"))
        lines.extend(self._render_ledger_section(orders))
        return "\n".join(lines)

    def _render_monthly_section(self, orders: list[dict[str, Any]]) -> list[str]:
        monthly: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"count": 0, "amount": 0.0, "quantity": 0}
        )
        for order in orders:
            month = _fmt_month(order.get("created_at"))
            monthly[month]["count"] += 1
            monthly[month]["amount"] += _safe_float(order.get("amount"))
            monthly[month]["quantity"] += _safe_int(order.get("quantity"))

        lines = [
            "## 月度明细",
            "",
            "| 月份 | 订单数 | 销售额（元） | 销量 |",
            "|------|--------|--------------|------|",
        ]
        for month in sorted(monthly):
            stats = monthly[month]
            lines.append(
                f"| {month} | {stats['count']} | {_fmt_money(stats['amount'])} | {stats['quantity']:,} |"
            )
        lines.append("")
        return lines

    def _render_dimension_section(
        self,
        orders: list[dict[str, Any]],
        field: str,
        label: str,
    ) -> list[str]:
        stats: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"count": 0, "amount": 0.0}
        )
        for order in orders:
            key = str(order.get(field) or "未知")
            stats[key]["count"] += 1
            stats[key]["amount"] += _safe_float(order.get("amount"))

        lines = [
            f"## 分{label}统计",
            "",
            f"| {label} | 订单数 | 销售额（元） |",
            "|------|--------|--------------|",
        ]
        sorted_keys = sorted(stats, key=lambda k: stats[k]["amount"], reverse=True)
        for key in sorted_keys:
            row = stats[key]
            lines.append(f"| {key} | {row['count']} | {_fmt_money(row['amount'])} |")
        lines.append("")
        return lines

    def _render_ledger_section(self, orders: list[dict[str, Any]]) -> list[str]:
        id_field = self.settings.postgres_business_id_field
        sorted_orders = sorted(
            orders,
            key=lambda o: _parse_created_at(o.get("created_at")) or datetime.min.replace(tzinfo=UTC),
        )

        lines = [
            "## 订单明细台账",
            "",
            "| 订单号 | 日期 | 客户 | 品牌 | SKU | 数量 | 单价 | 金额（元） | 渠道 | 区域 | 状态 |",
            "|--------|------|------|------|-----|------|------|------------|------|------|------|",
        ]
        for order in sorted_orders:
            order_id = str(order.get(id_field, "-"))
            product = str(order.get("product_name") or order.get("spec") or "-")
            lines.append(
                "| "
                + " | ".join(
                    [
                        order_id,
                        _fmt_date(order.get("created_at")),
                        str(order.get("customer") or "-"),
                        str(order.get("brand") or "-"),
                        product,
                        str(_safe_int(order.get("quantity"))),
                        _fmt_money(_safe_float(order.get("unit_price"))),
                        _fmt_money(_safe_float(order.get("amount"))),
                        str(order.get("channel") or "-"),
                        str(order.get("region") or "-"),
                        str(order.get("status") or "-"),
                    ]
                )
                + " |"
            )
        lines.append("")
        return lines

    def generate_report_file(
        self,
        start: datetime,
        end: datetime,
        *,
        collection: str | None = None,
        output_dir: Path | None = None,
    ) -> tuple[Path, int]:
        orders = self.fetch_orders(start, end, collection=collection)
        markdown = self.render_markdown(orders, start=start, end=end)
        output_path = self.build_output_path(start, end, output_dir=output_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        return output_path, len(orders)
