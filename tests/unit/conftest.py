import hashlib

import numpy as np
import pytest

from skill_selection.encoders.base import Encoder


class FakeEncoder(Encoder):
    """Deterministic pseudo-embeddings from a hash of the text; no model, no network."""
    backend, model, revision, dim = "fake", "hash", "v1", 8

    def __init__(self):
        self.calls = []

    def _encode(self, texts, kind):
        self.calls.append((kind, list(texts)))
        rows = [np.frombuffer(hashlib.sha256(f"{kind}|{t}".encode()).digest()[:self.dim * 4], dtype=np.uint32)
                for t in texts]
        return np.asarray(rows, dtype=np.float32) / 2**32 - 0.5


@pytest.fixture(scope="session")
def explorer_dir(tmp_path_factory):
    """skill_index.json + selection_cache.json built from the real GR1 snapshot with the fake encoder."""
    from skill_selection.datasets.gr1 import load_gr1
    from skill_selection.explorer import build_index, select_all, write_json_stable
    from skill_selection.filters.constraint import Environment
    out = tmp_path_factory.mktemp("explorer")
    index = build_index(load_gr1(), [FakeEncoder()])
    write_json_stable(index, out / "skill_index.json")
    write_json_stable(select_all(index, Environment("windows", 8192), ram_mode="fixed:8192", k=3, seed=0),
                      out / "selection_cache.json", pretty=True)
    return out
