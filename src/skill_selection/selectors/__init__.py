from .base import Selector
from .bm25 import BM25Selector
from .random_selector import RandomSelector

REGISTRY = {
    "random": RandomSelector,
    "bm25": BM25Selector,
}


def build_selector(name: str, **params) -> Selector:
    if name not in REGISTRY:
        raise ValueError(f"unknown selector {name!r}; available: {sorted(REGISTRY)}")
    return REGISTRY[name](**params)
