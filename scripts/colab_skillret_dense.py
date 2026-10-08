"""Run the dense / rerank baselines on the full SkillRet v1.1 test set on a GPU (Google Colab or Kaggle).

What it does
  Encodes the 6,006 test skills ("name | description | skill_md", as in the SkillRet paper) and the 4,392 test queries
  with each embedding model, ranks by cosine, and reranks the SkillRouter top-20 with SkillRouter-Reranker-0.6B.
  Models and dataset are pinned to the same revisions as the repo. It writes ranked lists only: scoring is done
  offline on your machine with `python -m skill_selection eval-run`, against the same qrels and metric code.

Input
  Nothing but internet on the GPU machine. In a Colab cell (GPU runtime):
    !pip -q install "sentence-transformers>=3.0" "transformers>=4.51" huggingface_hub
    !python colab_skillret_dense.py --out runs_skillret --max-len 4096
  (upload this file first, or paste it into a cell with %%writefile colab_skillret_dense.py)

Output
  <out>/<method>.jsonl, one line per query: {"query_id", "selector", "skill_ids": top-100, "scores": top-100}
  <out>/manifest.json: model revisions, max length, GPU, timings. Download the folder, then on your machine:
    python -m skill_selection eval-run --run runs_skillret/skillret-base.jsonl
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

DATASET, DATASET_REV = "ThakiCloud/SKILLRET", "6583d7d2ed07644d0fb8938ed8178f3a7dc42a12"   # v1.1
MODELS = {
    "skillret-base": ("st", "Qwen/Qwen3-Embedding-0.6B", "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3", None),
    "skillret-ft": ("st", "ThakiCloud/SkillRet-Embedding-0.6B", "67f1594c46c40e13a5eb2f4092cc85c98c9ed32d", None),
    "skillrouter-emb": ("hf", "pipizhao/SkillRouter-Embedding-0.6B", "c03c9bcee9fce92ab0262bb6dcf54d174a8ba558",
                        "Instruct: Given a task description, retrieve the most relevant skill document that would help "
                        "an agent complete the task\nQuery:"),
}
RERANKER = ("pipizhao/SkillRouter-Reranker-0.6B", "78986e1142d12857cfd85b8005e62902cd42d858")
RERANK_INSTRUCTION = "Given a task description, judge whether the skill document is relevant and useful for completing the task"
PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct '
          'provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
TOP_SAVE, TOP_RERANK = 100, 20


def load_split():
    from huggingface_hub import hf_hub_download
    def rows(kind):
        path = hf_hub_download(DATASET, f"data/{kind}/test.jsonl", repo_type="dataset", revision=DATASET_REV)
        return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    return rows("skills"), rows("queries")


def skill_text(s):
    return f"{s['name'].strip()} | {(s.get('description') or '').strip()} | {(s.get('skill_md') or s.get('description') or '').strip()}"


def encode_st(model, rev, texts, kind, max_len, bs):
    import torch
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(model, revision=rev, device="cuda", model_kwargs={"torch_dtype": torch.bfloat16})
    m.max_seq_length = max_len
    v = m.encode(texts, batch_size=bs, prompt_name="query" if kind == "query" else None,
                 normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True)
    del m
    torch.cuda.empty_cache()
    return v.astype(np.float32)


def encode_last_token(model, rev, texts, max_len, bs):
    import torch
    import torch.nn.functional as F
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model, revision=rev, padding_side="left")
    m = AutoModel.from_pretrained(model, revision=rev, torch_dtype=torch.bfloat16).cuda().eval()
    order = np.argsort([-len(t) for t in texts])
    out = np.zeros((len(texts), m.config.hidden_size), dtype=np.float32)
    for i in range(0, len(texts), bs):
        idx = order[i:i + bs]
        enc = tok([texts[j] for j in idx], padding=True, truncation=True, max_length=max_len, return_tensors="pt").to("cuda")
        with torch.no_grad():
            h = m(**enc).last_hidden_state[:, -1]
        out[idx] = F.normalize(h.float(), p=2, dim=1).cpu().numpy()
    del m
    torch.cuda.empty_cache()
    return out


def rerank(queries, skills, first, max_len):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(RERANKER[0], revision=RERANKER[1], padding_side="left")
    m = AutoModelForCausalLM.from_pretrained(RERANKER[0], revision=RERANKER[1], torch_dtype=torch.bfloat16).cuda().eval()
    yes, no = tok.convert_tokens_to_ids("yes"), tok.convert_tokens_to_ids("no")
    pre, suf = tok.encode(PREFIX, add_special_tokens=False), tok.encode(SUFFIX, add_special_tokens=False)
    out = []
    for q, (ids, _) in zip(queries, first):
        scores = []
        for sid in ids[:TOP_RERANK]:
            s = skills[sid]
            doc = f"{s['name']} | {(s.get('description') or '')[:500]} | {(s.get('skill_md') or '')[:2000]}"
            prompt = f"<Instruct>: {RERANK_INSTRUCTION}\n\n<Query>: {q['query']}\n\n<Document>: {doc}"
            body = tok(prompt, truncation=True, max_length=max_len - len(pre) - len(suf))["input_ids"]
            x = torch.tensor([pre + body + suf], device="cuda")
            with torch.no_grad():
                logits = m(input_ids=x).logits[0, -1]
            scores.append(float(logits[yes] - logits[no]))
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        head = [ids[i] for i in order]
        out.append((head + ids[TOP_RERANK:], [scores[i] for i in order] + [None] * (len(ids) - TOP_RERANK)))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="runs_skillret")
    p.add_argument("--max-len", type=int, default=4096)
    p.add_argument("--batch", type=int, default=16)
    args = p.parse_args()
    import torch
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    skills, queries = load_split()
    ids, texts = [s["id"] for s in skills], [skill_text(s) for s in skills]
    by_id = {s["id"]: s for s in skills}
    manifest = {"dataset": DATASET, "dataset_revision": DATASET_REV, "max_len": args.max_len,
                "gpu": torch.cuda.get_device_name(0), "methods": {}}
    first_stage = {}
    for name, (kind, model, rev, instruction) in MODELS.items():
        t0 = time.time()
        if kind == "st":
            sv = encode_st(model, rev, texts, "document", args.max_len, args.batch)
            qv = encode_st(model, rev, [q["query"] for q in queries], "query", args.max_len, args.batch)
        else:
            sv = encode_last_token(model, rev, texts, args.max_len, args.batch)
            qv = encode_last_token(model, rev, [instruction + q["query"] for q in queries], args.max_len, args.batch)
        sims = qv @ sv.T
        ranked = []
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for q, row in zip(queries, sims):
                top = np.argsort(-row, kind="stable")[:TOP_SAVE]
                ranked.append(([ids[i] for i in top], [float(row[i]) for i in top]))
                f.write(json.dumps({"query_id": q["id"], "selector": name, "skill_ids": ranked[-1][0],
                                    "scores": ranked[-1][1]}) + "\n")
        first_stage[name] = ranked
        manifest["methods"][name] = {"model": model, "revision": rev, "seconds": round(time.time() - t0, 1)}
        print(name, "done", manifest["methods"][name])
    t0 = time.time()
    reranked = rerank(queries, by_id, first_stage["skillrouter-emb"], args.max_len)
    with open(out / "skillrouter.jsonl", "w", encoding="utf-8") as f:
        for q, (sids, scores) in zip(queries, reranked):
            f.write(json.dumps({"query_id": q["id"], "selector": "skillrouter", "skill_ids": sids, "scores": scores}) + "\n")
    manifest["methods"]["skillrouter"] = {"model": RERANKER[0], "revision": RERANKER[1], "first_stage": "skillrouter-emb",
                                          "rerank_top": TOP_RERANK, "seconds": round(time.time() - t0, 1)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("done:", out)


if __name__ == "__main__":
    main()
