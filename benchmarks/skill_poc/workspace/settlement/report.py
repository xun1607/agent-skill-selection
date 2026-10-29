"""Aggregate the normalized gateway records."""
from __future__ import annotations

from .reader import Payment


def summarize(payments: list[Payment]) -> dict:
    seen = set()
    customers = {}
    for payment in payments:
        if payment.status != "settled":
            continue
        if payment.customer_id in seen:
            continue
        seen.add(payment.customer_id)
        customers[payment.customer_id] = customers.get(payment.customer_id, 0.0) + float(payment.amount)
    return {
        "customers": {key: f"{round(value, 2):.2f}" for key, value in sorted(customers.items())},
        "total": f"{round(sum(customers.values()), 2):.2f}",
    }
