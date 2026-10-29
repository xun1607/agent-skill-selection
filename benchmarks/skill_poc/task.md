# Repair a payment reconciliation CLI

Operations imports CSV exports from a payment gateway and uses this project to produce a per-customer settlement
report. Retried exports contain repeated transaction IDs, and some customers have multiple real transactions.
Reports currently lose payments and occasionally differ from the gateway by one cent.

Investigate and fix the implementation. Preserve the `python -m settlement <csv-path>` CLI and JSON output shape.
You may add regression tests; do not edit or remove the supplied tests, sample CSV, or this task specification.

## Acceptance criteria

- CSV columns are `txn_id,customer_id,amount,status`; whitespace is stripped and status is case insensitive.
- Only `settled` records contribute money. `pending` and `failed` records contribute nothing.
- Distinct transaction IDs count independently, including multiple payments for one customer.
- Repeating an identical normalized record with the same transaction ID has no additional effect.
- Equivalent decimal spellings such as `1.0` and `1.00` mean the same amount when detecting repeated records.
- Reusing a transaction ID for a different customer, amount, or status raises `ValueError`, even for non-settled rows.
- Amounts are non-negative finite decimal USD values. Round EACH settled payment to cents using ROUND_HALF_UP
  before summing. Output amounts as strings with exactly two decimal places; input row order must not matter.
- Reject missing identifiers, missing columns, unsupported status, negative amounts and non-finite amounts.
- Keep customer IDs in sorted order in the JSON output. Empty/no-settled input produces `{"customers": {}, "total": "0.00"}`.
- The CLI writes valid JSON to stdout on success and exits non-zero with an error on invalid input.

The example export and supplied tests are starting points, not a complete acceptance suite. Add tests for gaps you find.
Before claiming completion, run the full public suite and CLI on the example export. Explain the root causes and cite
the verification commands/results in your final response. No dependencies beyond Python's standard library and pytest
are needed. Do not install plugins, access credentials, contact external services, or commit changes.
