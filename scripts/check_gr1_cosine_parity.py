"""Check that this repo ranks skills exactly like GR1 when both are given the same embeddings.

What it does
  Feeds the OpenAI vectors stored in artifacts/explorer/skill_index.json into GR1's own pipeline
  (CASSContextManager(fixed_ram_mb) -> ConstraintFilterStrategy -> SemanticFilterStrategy, i.e. Tier 1 + Tier 2 of
  "GR1 cosine top-3") through a lookup embedder, and compares GR1's order with the order in
  artifacts/explorer/selection_cache.json for the same encoder. No API call is made.

Input
  artifacts/explorer/skill_index.json and selection_cache.json (run `index gr1 --encoder openai:...` then `select gr1`).
  Must be run with GR1's interpreter on the same OS as --os of the selection (GR1 reads the OS from the host):
    <gr1>/../../venv/Scripts/python.exe scripts/check_gr1_cosine_parity.py

Output
  One line per task (identical / first difference) and exit code 0 only if every task matches.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GR1 = REPO_ROOT.parent / "gr1-prj" / "ai-software-engineering-agent" / "backend" / "services" / "skill_testing"


class LookupEmbedder:
    """GR1 calls embed(texts); answer from the precomputed vectors, fail on any unknown text."""

    def __init__(self, table):
        self.table = table

    def embed(self, texts):
        missing = [t for t in texts if t not in self.table]
        if missing:
            raise KeyError(f"no precomputed vector for {missing[:2]}")
        return np.stack([self.table[t] for t in texts])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gr1", type=Path, default=DEFAULT_GR1)
    parser.add_argument("--artifacts", type=Path, default=REPO_ROOT / "artifacts")
    parser.add_argument("--encoder", default="openai:text-embedding-3-small@api")
    args = parser.parse_args()
    index = json.loads((args.artifacts / "explorer" / "skill_index.json").read_text(encoding="utf-8"))
    selection = json.loads((args.artifacts / "explorer" / "selection_cache.json").read_text(encoding="utf-8"))
    run = next(r for r in selection["runs"] if r["params"]["encoder"] == args.encoder)
    ram_mb = int(run["params"]["ram_mode"].split(":")[1])

    gr1 = args.gr1.resolve()
    sys.path.insert(0, str(gr1 / "swe_agent"))
    sys.path.insert(0, str(gr1))
    os.chdir(gr1)
    from experiment_setup import build_skills
    from swe_agent.cass_bridge import CASSBridge
    from cass.context.context_manager import CASSContextManager
    from cass.filter.constraint import ConstraintFilterStrategy
    from cass.filter.semantic import SemanticFilterStrategy

    enc = index["encoders"][args.encoder]
    table = {f"{s['name']}: {s['description']}": np.asarray(enc["skill_vectors"][s["id"]], dtype=np.float32)
             for s in index["skills"]}
    table.update({t["text"]: np.asarray(enc["task_vectors"][t["id"]], dtype=np.float32) for t in index["tasks"]})

    context_mgr = CASSContextManager(fixed_ram_mb=ram_mb)
    if context_mgr._static_info["os_name"] != run["params"]["os"]:
        raise SystemExit(f"host OS {context_mgr._static_info['os_name']} != selection OS {run['params']['os']}")
    profiles = CASSBridge._to_profiles(build_skills(brain=None))
    ok = True
    for task in index["tasks"]:
        context = context_mgr.get_full_context("parity", task["text"])
        candidates = ConstraintFilterStrategy().filter(profiles, context)
        gr1_order = [c["name"] for c in SemanticFilterStrategy(top_n=len(candidates), embedder=LookupEmbedder(table))
                     .filter(candidates, context)]
        ours = [r["skill_id"] for r in run["tasks"][task["id"]]["ranking"] if not r["excluded"]]
        if gr1_order == ours:
            print(f"{task['id']:24s} identical ({len(ours)} ranked; top-3 {', '.join(ours[:3])})")
        else:
            ok = False
            i = next(i for i, (a, b) in enumerate(zip(gr1_order, ours)) if a != b) if len(gr1_order) == len(ours) else -1
            print(f"{task['id']:24s} DIFFERENT at rank {i + 1}: GR1 {gr1_order[i:i + 3]} vs ours {ours[i:i + 3]}")
    print("PARITY OK" if ok else "PARITY FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
