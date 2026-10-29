from settlement.reader import Payment, read_payments
from settlement.report import summarize


def test_simple_payment_and_pending():
    rows = [Payment("t1", "alice", "10.00", "settled"), Payment("t2", "bob", "99.00", "pending")]
    assert summarize(rows) == {"customers": {"alice": "10.00"}, "total": "10.00"}


def test_distinct_transactions_for_same_customer():
    rows = [Payment("t1", "alice", "10.00", "settled"), Payment("t2", "alice", "2.00", "settled")]
    assert summarize(rows) == {"customers": {"alice": "12.00"}, "total": "12.00"}


def test_example_export():
    from pathlib import Path
    rows = read_payments(Path(__file__).with_name("example.csv"))
    assert summarize(rows) == {"customers": {"alice": "12.69", "bob": "3.34"}, "total": "16.03"}
