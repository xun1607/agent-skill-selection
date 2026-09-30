from __future__ import annotations

from typing import Dict, Mapping, Optional

from ..evaluation.metrics import METRICS, EvalReport


def metrics_table(mean: Mapping[str, float], ks, reference: Optional[Mapping[str, float]] = None) -> str:
    """Metrics in %, one row per metric, one column per k; with a reference, each cell also shows the difference."""
    lines = ["| Metric | " + " | ".join(f"@{k}" for k in ks) + " |",
             "|---|" + "---:|" * len(ks)]
    for m in METRICS:
        cells = []
        for k in ks:
            name = f"{m}@{k}"
            cell = f"{100 * mean[name]:.2f}"
            if reference and name in reference:
                cell += f" (ref {reference[name]:.2f}, {100 * mean[name] - reference[name]:+.2f})"
            cells.append(cell)
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run_report(manifest: Dict, report: EvalReport, reference: Optional[Mapping[str, float]] = None) -> str:
    ds = manifest["dataset"]
    out = [
        f"# Run `{manifest['run_id']}`",
        "",
        f"- Selector: `{manifest['selector']}`",
        f"- Dataset: {ds['name']} / {ds['split']} (revision `{ds.get('revision', '-')}`), "
        f"{manifest['catalog_size']} skills, {manifest['n_queries']} queries, k = {manifest['k']}",
        f"- Evaluated queries: {report.n_evaluated} (skipped, no relevant skill: {report.n_skipped_no_relevant}; "
        f"missing from run: {report.n_missing_from_run})",
        f"- Mean skills returned: {report.mean['n_selected']:.2f}",
        f"- Fit: {manifest['fit_seconds']} s, selection: {manifest['select_seconds']} s "
        f"({manifest['mean_latency_ms']} ms/query)",
        f"- Created: {manifest['created_utc']}",
        "",
        "## Metrics (%)",
        "",
        metrics_table(report.mean, report.ks, reference),
        "",
    ]
    if reference:
        out += ["`ref` = reference numbers reported by the dataset paper for the same method.", ""]
    return "\n".join(out)
