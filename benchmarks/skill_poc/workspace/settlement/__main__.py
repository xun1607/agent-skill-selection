"""Usage: python -m settlement <payments.csv>."""
import json
import sys

from .reader import read_payments
from .report import summarize


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m settlement <payments.csv>", file=sys.stderr)
        return 2
    try:
        result = summarize(read_payments(sys.argv[1]))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
