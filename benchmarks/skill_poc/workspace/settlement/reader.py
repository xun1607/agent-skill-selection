"""CSV boundary: normalize and validate records before aggregation."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class Payment:
    txn_id: str
    customer_id: str
    amount: str
    status: str


def read_payments(path: str | Path) -> list[Payment]:
    payments = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"txn_id", "customer_id", "amount", "status"}.issubset(reader.fieldnames or []):
            raise ValueError("missing required CSV columns")
        for line, row in enumerate(reader, 2):
            fields = {key: (row.get(key) or "").strip() for key in ("txn_id", "customer_id", "amount", "status")}
            fields["status"] = fields["status"].lower()
            if not fields["txn_id"] or not fields["customer_id"]:
                raise ValueError(f"missing identifier at line {line}")
            if fields["status"] not in {"settled", "pending", "failed"}:
                raise ValueError(f"unsupported status at line {line}")
            try:
                amount = Decimal(fields["amount"])
            except InvalidOperation as error:
                raise ValueError(f"invalid amount at line {line}") from error
            if not amount.is_finite() or amount < 0:
                raise ValueError(f"invalid amount at line {line}")
            payments.append(Payment(**fields))
    return payments
