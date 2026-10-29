"""Runner-only acceptance suite; copied into a disposable verifier workspace.

This is outside the workspace supplied to an agent. It is not a security boundary
against an agent with read access to the enclosing research repository.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from settlement.reader import Payment, read_payments
from settlement.report import summarize


def test_idempotency_and_multiple_payments():
    a = Payment("tx1", "a", "1.00", "settled")
    b = Payment("tx2", "a", "2.00", "settled")
    assert summarize([a, a, b]) == {"customers": {"a": "3.00"}, "total": "3.00"}
    assert summarize([b, a, a]) == summarize([a, a, b])


def test_round_each_payment_half_up():
    rows = [Payment("tx1", "a", "0.005", "settled"), Payment("tx2", "a", "0.005", "settled")]
    assert summarize(rows) == {"customers": {"a": "0.02"}, "total": "0.02"}
    assert summarize([Payment("tx3", "z", "2.675", "settled")])["total"] == "2.68"


def test_duplicate_equivalent_decimal_spellings():
    rows = [Payment("tx1", "a", "1.0", "settled"), Payment("tx1", "a", "1.00", "settled")]
    assert summarize(rows) == {"customers": {"a": "1.00"}, "total": "1.00"}


@pytest.mark.parametrize("other", [Payment("tx", "b", "1.00", "settled"), Payment("tx", "a", "2.00", "settled"), Payment("tx", "a", "1.00", "pending")])
def test_conflicting_duplicate_is_rejected(other):
    with pytest.raises(ValueError):
        summarize([Payment("tx", "a", "1.00", "settled"), other])


def test_conflicting_pending_rows_are_rejected():
    with pytest.raises(ValueError):
        summarize([Payment("tx", "a", "1", "pending"), Payment("tx", "b", "1", "pending")])


def test_empty_and_status_filter():
    assert summarize([]) == {"customers": {}, "total": "0.00"}
    assert summarize([Payment("tx", "a", "5", "failed")]) == summarize([])


def test_normalization_and_cli(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("txn_id,customer_id,amount,status\n t1 , z , 1.005 , SETTLED \nt2,a,1.00,settled\n", encoding="utf-8")
    rows = read_payments(path)
    assert rows[0] == Payment("t1", "z", "1.005", "settled")
    result = subprocess.run([sys.executable, "-m", "settlement", str(path)], cwd=Path.cwd(), capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == {"customers": {"a": "1.00", "z": "1.01"}, "total": "2.01"}
    assert list(report["customers"]) == ["a", "z"]


@pytest.mark.parametrize("amount", ["-1", "NaN", "Infinity", "not-money"])
def test_invalid_amounts(tmp_path, amount):
    path = tmp_path / "invalid.csv"
    path.write_text(f"txn_id,customer_id,amount,status\nt1,a,{amount},settled\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_payments(path)
    result = subprocess.run([sys.executable, "-m", "settlement", str(path)], capture_output=True, text=True, timeout=15)
    assert result.returncode != 0


@pytest.mark.parametrize("content", ["txn_id,amount,status\nt1,1,settled\n", "txn_id,customer_id,amount,status\n,a,1,settled\n", "txn_id,customer_id,amount,status\nt1,a,1,unknown\n"])
def test_invalid_records(tmp_path, content):
    path = tmp_path / "invalid.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_payments(path)
