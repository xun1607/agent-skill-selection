"""Cross-encoder rerankers built on a causal LM that answers "yes"/"no" (Qwen3-Reranker style).

SkillRouter-Reranker-0.6B is reproduced verbatim from its model card: document "name | desc[:500] | body[:2000]",
the <Instruct>/<Query>/<Document> prompt, the system prefix and the empty-think suffix, max 4096 tokens,
score = logit("yes") - logit("no") at the last position.

Input: one query and candidate skills. Output: one float score per candidate (higher = more relevant).
Scores are cached on disk by sha256(model, revision, prompt), so re-runs are offline and identical.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

SKILLROUTER_RERANKER = "pipizhao/SkillRouter-Reranker-0.6B"
SKILLROUTER_RERANKER_REVISION = "78986e1142d12857cfd85b8005e62902cd42d858"
SKILLROUTER_INSTRUCTION = ("Given a task description, judge whether the skill document "
                           "is relevant and useful for completing the task")
QWEN_RERANK_PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements '
                      'based on the Query and the Instruct provided. Note that the answer can '
                      'only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
QWEN_RERANK_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


@dataclass
class YesNoReranker:
    model: str = SKILLROUTER_RERANKER
    revision: str = SKILLROUTER_RERANKER_REVISION
    instruction: str = SKILLROUTER_INSTRUCTION
    desc_max: int = 500
    body_max: int = 2000
    max_length: int = 4096
    cache_path: Optional[Path] = None
    dtype: Optional[str] = None                     # None = float32; "bfloat16" halves memory (part of the cache key)

    def __post_init__(self):
        self._model = self._tok = None
        self._cache: Dict[str, float] = {}
        if self.cache_path and Path(self.cache_path).exists():
            self._cache = json.loads(Path(self.cache_path).read_text(encoding="utf-8"))

    @property
    def spec(self) -> str:
        return f"rerank:{self.model}@{self.revision}"

    def prompt(self, query: str, name: str, desc: str, body: str) -> str:
        doc = f"{name} | {desc[:self.desc_max]} | {body[:self.body_max]}"
        return f"<Instruct>: {self.instruction}\n\n<Query>: {query}\n\n<Document>: {doc}"

    def _key(self, prompt: str) -> str:
        return hashlib.sha256(json.dumps([self.model, self.revision, self.max_length, self.dtype, prompt]).encode("utf-8")).hexdigest()

    def _score_one(self, prompt: str) -> float:
        import torch
        if self._model is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self._tok = AutoTokenizer.from_pretrained(self.model, revision=self.revision, padding_side="left")
            kwargs = {"torch_dtype": getattr(torch, self.dtype)} if self.dtype else {}
            self._model = AutoModelForCausalLM.from_pretrained(self.model, revision=self.revision, **kwargs).eval()
            self._yes = self._tok.convert_tokens_to_ids("yes")
            self._no = self._tok.convert_tokens_to_ids("no")
        prefix = self._tok.encode(QWEN_RERANK_PREFIX, add_special_tokens=False)
        suffix = self._tok.encode(QWEN_RERANK_SUFFIX, add_special_tokens=False)
        body = self._tok(prompt, padding=False, truncation=True, return_attention_mask=False,
                         max_length=self.max_length - len(prefix) - len(suffix))["input_ids"]
        ids = torch.tensor([prefix + body + suffix])
        with torch.no_grad():
            logits = self._model(input_ids=ids, attention_mask=torch.ones_like(ids)).logits[:, -1, :]
        return float(logits[0, self._yes] - logits[0, self._no])

    def score(self, query: str, skills: Sequence) -> List[float]:
        prompts = [self.prompt(query, s.name, s.description, s.body) for s in skills]
        missing = [p for p in prompts if self._key(p) not in self._cache]
        for p in missing:
            self._cache[self._key(p)] = self._score_one(p)
        if missing and self.cache_path:
            path = Path(self.cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(self._cache), encoding="utf-8")
            os.replace(tmp, path)
        return [self._cache[self._key(p)] for p in prompts]
