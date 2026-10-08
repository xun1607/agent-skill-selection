"""Run every baseline on the GR1 benchmark, score it against the draft labels, check each output.

Input: the GR1 snapshot (41 skills, 6 tasks), the draft labels (evaluator only), cached embeddings / rerank scores
(models are loaded only for texts missing from the cache, one model at a time).
Output (artifacts/compare/gr1.json): per method its description (METHODS), per task the full ranking with scores and
the selected set, metrics (Recall/NDCG/Completeness@3/5/10, set precision/recall/F1, size) and acceptance checks.

Methods (all see only task text + skill catalog; none sees labels):
  Random          uniform ranking, mean over 5 seeds (floor)
  BM25            lexical, name | description | body (SkillRet paper baseline)
  M0              Qwen3-Embedding-0.6B on "name: description" (GR1 representation), top-3
  M1 (GR1)        Tier-1 constraint filter (windows, fixed:8192) + M0, top-3 = the GR1 method
  SkillRet-base   Qwen3-Embedding-0.6B on full text: the off-the-shelf baseline row of the SkillRet paper
  SkillRet-FT     ThakiCloud/SkillRet-Embedding-0.6B (fine-tuned on SkillRet), full text
  SkillRouter-Emb pipizhao/SkillRouter-Embedding-0.6B, full text, model-card instruction
  SkillRouter     SkillRouter-Emb top-20 reranked by pipizhao/SkillRouter-Reranker-0.6B (model-card prompt)
  GoS-lite        Graph of Skills retrieval without LLM (selectors/gos_lite.py), bundle <= 8 skills / 12k chars
  SkillReranker-h SkillReranker (ported GR1 core, mode "full"), heuristic parser, Qwen3 scorer, adaptive size
  M5-h            proposed path selection (GR1 core, mode "path", lambda=-1, mu=0.5 tuned on SkillRet train)
"""
from __future__ import annotations

import gc
import hashlib
import json
import random
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from .datasets.gr1 import GR1Benchmark, load_gr1_labels
from .evaluation.metrics import evaluate
from .filters.constraint import Environment, apply_constraints

K_FIXED = 3
DTYPE = "bfloat16"     # all models of the comparison: half the memory of float32 (8 GB machine)
SKILLROUTER_TOP = 20
ENC_QWEN = "st:Qwen/Qwen3-Embedding-0.6B"
ENC_SKILLRET = "st:ThakiCloud/SkillRet-Embedding-0.6B"
ENC_SKILLROUTER = "hf:pipizhao/SkillRouter-Embedding-0.6B"

METHODS = [
    {"id": "Random", "family": "Sàn", "paper": "—", "variant": "Thứ hạng ngẫu nhiên, trung bình 5 seed",
     "input": "Danh sách skill", "output": "Thứ hạng ngẫu nhiên; chọn top-3"},
    {"id": "BM25", "family": "Từ khoá", "paper": "SkillRet (arXiv 2605.05726), baseline",
     "variant": "BM25 Lucene (k1=1.5, b=0.75) trên name | description | body; đã khớp số bài báo trên SkillRet",
     "input": "Mô tả nhiệm vụ + văn bản skill", "output": "Thứ hạng theo điểm BM25; chọn top-3"},
    {"id": "M0", "family": "Vector nhúng", "paper": "—",
     "variant": "Qwen3-Embedding-0.6B trên 'name: description' (cách biểu diễn của GR1), không lọc",
     "input": "Mô tả nhiệm vụ + name, description", "output": "Thứ hạng cosine; chọn top-3"},
    {"id": "M1 (GR1)", "family": "Hệ thống kỳ trước", "paper": "GR1",
     "variant": "Lọc ràng buộc (windows, RAM fixed:8192) rồi M0, top-3",
     "input": "Mô tả nhiệm vụ + name, description + ràng buộc OS/RAM", "output": "Thứ hạng 38 skill còn lại; chọn top-3"},
    {"id": "SkillRet-base", "family": "Vector nhúng", "paper": "SkillRet (arXiv 2605.05726), off-the-shelf baseline",
     "variant": "Qwen3-Embedding-0.6B trên toàn văn name | description | body, prompt mặc định của mô hình",
     "input": "Mô tả nhiệm vụ + toàn văn skill", "output": "Thứ hạng cosine; chọn top-3"},
    {"id": "SkillRet-FT", "family": "Vector nhúng (tinh chỉnh)", "paper": "SkillRet (arXiv 2605.05726)",
     "variant": "ThakiCloud/SkillRet-Embedding-0.6B (tinh chỉnh trên SkillRet), toàn văn, prompt đi kèm mô hình",
     "input": "Mô tả nhiệm vụ + toàn văn skill", "output": "Thứ hạng cosine; chọn top-3"},
    {"id": "SkillRouter-Emb", "family": "Vector nhúng (tinh chỉnh)", "paper": "SkillRouter (arXiv 2603.22455), tầng 1",
     "variant": "pipizhao/SkillRouter-Embedding-0.6B, toàn văn, instruction theo model card",
     "input": "Mô tả nhiệm vụ + toàn văn skill", "output": "Thứ hạng cosine; chọn top-3"},
    {"id": "SkillRouter", "family": "Truy hồi + xếp hạng lại", "paper": "SkillRouter (arXiv 2603.22455), đầy đủ",
     "variant": "SkillRouter-Emb lấy top-20, SkillRouter-Reranker-0.6B xếp lại (prompt và định dạng theo model card)",
     "input": "Mô tả nhiệm vụ + toàn văn skill", "output": "Top-20 xếp lại theo logit(yes) − logit(no); chọn top-3"},
    {"id": "GoS-lite", "family": "Đồ thị skill–skill", "paper": "Graph of Skills (arXiv 2604.05333), tự cài rút gọn",
     "variant": "Hạt giống BM25 + Qwen3 (RRF), PageRank cá nhân hoá có cạnh ngược (gamma_r=0.5) trên đồ thị từ "
                "sub_skills và việc SKILL.md nhắc tên skill khác; không dùng LLM",
     "input": "Mô tả nhiệm vụ + toàn văn skill + đồ thị phụ thuộc", "output": "Thứ hạng theo PageRank; gói ≤ 8 skill / 12.000 ký tự"},
    {"id": "SkillReranker-h", "family": "Phân rã nhiệm vụ + đồ thị trạng thái", "paper": "SkillReranker (arXiv 2607.06283), bản heuristic",
     "variant": "Lõi GR1 (chế độ full) chuyển sang repo này, bộ phân rã heuristic (không LLM), scorer Qwen3 thay cross-encoder",
     "input": "Mô tả nhiệm vụ + toàn văn skill + hồ sơ tiền điều kiện/kết quả (heuristic)",
     "output": "Mỗi giai đoạn chọn 1 skill; số skill tự điều chỉnh"},
    {"id": "M5-h", "family": "Đề xuất (đường đi trên đồ thị trạng thái)", "paper": "Đề xuất GR2, bản heuristic",
     "variant": "Lõi GR1 (chế độ path, lambda=-1, mu=0.5 chỉnh trên SkillRet train), scorer Qwen3",
     "input": "Như SkillReranker-h", "output": "Đường đi s0 → đích; số skill = số bước cần skill"},
]


def text_full(s) -> str:
    return f"{s.name} | {s.description} | {s.body}"


def text_name_desc(s) -> str:
    return f"{s.name}: {s.description}"


def _dense(encoder, skills, tasks, represent: Callable) -> Dict[str, dict]:
    sv = encoder.encode([represent(s) for s in skills], "document")
    tv = encoder.encode([t.text for t in tasks], "query")
    out = {}
    for t, q in zip(tasks, tv):
        scores = sv @ q
        order = np.argsort(-scores, kind="stable")
        out[t.id] = {"ranking": [skills[i].id for i in order], "scores": [round(float(scores[i]), 6) for i in order]}
    return out


def _top_k(result: Dict[str, dict], k: int = K_FIXED) -> Dict[str, dict]:
    for r in result.values():
        r["selected"] = r["ranking"][:k]
    return result


def _release(encoder) -> None:
    inner = getattr(encoder, "inner", encoder)
    for attr in ("_st", "_model", "_tok"):
        if hasattr(inner, attr):
            setattr(inner, attr, None)
    gc.collect()


def set_metrics(selected: Sequence[str], gold: Sequence[str]) -> Dict[str, float]:
    hit = len(set(selected) & set(gold))
    p = hit / len(selected) if selected else 0.0
    r = hit / len(gold) if gold else 0.0
    return {"set_precision": p, "set_recall": r, "set_f1": 2 * p * r / (p + r) if p + r else 0.0,
            "n_selected": float(len(selected))}


def check_output(method: str, result: Dict[str, dict], skill_ids: Sequence[str], eligible: Sequence[str],
                 extra: Optional[Dict[str, bool]] = None) -> List[dict]:
    """Acceptance checks on a real output; every entry is {check, passed, detail}."""
    checks = []
    full = all(sorted(r["ranking"]) == sorted(eligible) for r in result.values())
    checks.append({"check": "Thứ hạng đầy đủ, không trùng", "passed": full,
                   "detail": f"{len(eligible)} skill hợp lệ mỗi nhiệm vụ"})
    if all("scores" in r for r in result.values()):
        mono = all(all(a >= b for a, b in zip(r["scores"], r["scores"][1:])) for r in result.values())
        checks.append({"check": "Điểm không tăng theo hạng", "passed": mono, "detail": ""})
    subset = all(r["selected"] and set(r["selected"]) <= set(r["ranking"]) for r in result.values())
    sizes = sorted({len(r["selected"]) for r in result.values()})
    checks.append({"check": "Tập chọn khác rỗng, nằm trong thứ hạng", "passed": subset, "detail": f"kích thước {sizes}"})
    for name, ok in (extra or {}).items():
        checks.append({"check": name, "passed": bool(ok), "detail": ""})
    return checks


def run_gr1(bench: GR1Benchmark, cache_dir: Path, env: Environment = Environment("windows", 8192)) -> dict:
    from .encoders import build_encoder
    from .rerankers import YesNoReranker
    from .selectors.bm25 import BM25Selector
    from .selectors.gos_lite import dependency_graph, gos_lite
    from .selectors.graph import core, parsing_heuristic as H
    from .selectors.graph.scorers import EncoderScorer

    skills, tasks = bench.skills, bench.tasks
    ids = [s.id for s in skills]
    results: Dict[str, Dict[str, dict]] = {}
    extra: Dict[str, Dict[str, bool]] = {}
    info: Dict[str, dict] = {}

    rand = {t.id: {} for t in tasks}
    for t in tasks:
        perms = []
        for seed in range(5):
            order = list(ids)
            random.Random(f"random|{t.id}|{seed}").shuffle(order)
            perms.append(order)
        rand[t.id] = {"ranking": perms[0], "selected": perms[0][:K_FIXED], "all_seeds": perms}
    results["Random"] = rand

    bm25 = BM25Selector()
    bm25.fit(skills)
    results["BM25"] = {}
    for t in tasks:
        s = bm25.scores(t.text)
        order = np.argsort(-s, kind="stable")
        results["BM25"][t.id] = {"ranking": [ids[i] for i in order], "scores": [round(float(s[i]), 6) for i in order]}
    _top_k(results["BM25"])

    qwen = build_encoder(ENC_QWEN, cache_dir=cache_dir, dtype=DTYPE, batch_size=1)
    info["qwen"] = qwen.info()
    results["M0"] = _top_k(_dense(qwen, skills, tasks, text_name_desc))
    kept, reasons = apply_constraints(skills, env)
    m1 = _dense(qwen, kept, tasks, text_name_desc)
    results["M1 (GR1)"] = _top_k(m1)
    results["SkillRet-base"] = _top_k(_dense(qwen, skills, tasks, text_full))

    # graph methods reuse the Qwen3 encoder (multilingual: GR1 tasks are Vietnamese, skills English)
    scorer = EncoderScorer(qwen)
    for name, mode in (("SkillReranker-h", "full"), ("M5-h", "path")):
        results[name] = {}
        plans_ok = []
        for t in tasks:
            plan = H.decompose(t.text)
            cands = []
            for s in skills:
                c = H.contract(s.name, s.description, s.body)
                cands.append(core.Candidate(s.id, text_full(s), c.precondition, c.completion))
            res = core.select(t.text, plan, cands, scorer, mode, core.SelectParams(lam=-1.0, mu=0.5, k=K_FIXED))
            results[name][t.id] = {"ranking": res.ranking, "selected": res.selected,
                                   "n_states": len(plan.states), "plan_valid": plan.valid}
            plans_ok.append(len(plan.states) == len(plan.subtasks) + 1)
        extra[name] = {"Kế hoạch hợp lệ: số trạng thái = số bước + 1": all(plans_ok)}

    lexical = {t.id: results["BM25"][t.id]["ranking"] for t in tasks}
    semantic = {t.id: results["SkillRet-base"][t.id]["ranking"] for t in tasks}
    graph = dependency_graph(skills, {s.id: bench.skill_md(s) for s in skills if bench.skill_md(s)})
    lengths = {s.id: len(text_full(s)) for s in skills}
    results["GoS-lite"], mass_ok = {}, []
    for t in tasks:
        ranking, bundle, score = gos_lite(ids, lexical[t.id], semantic[t.id], graph, lengths)
        results["GoS-lite"][t.id] = {"ranking": ranking, "selected": bundle}
        mass_ok.append(abs(sum(score.values()) - 1.0) < 1e-9)
    n_edges = sum(len(v) for v in graph.values())
    info["gos_graph"] = {"n_edges": n_edges, "edges": {u: v for u, v in graph.items() if v}}
    extra["GoS-lite"] = {"PageRank là phân phối xác suất (tổng = 1)": all(mass_ok),
                         "Gói skill ≤ 8 skill và ≤ 12.000 ký tự (một skill quá dài vẫn được giữ)": all(
                             len(r["selected"]) <= 8 and (len(r["selected"]) == 1
                                                          or sum(lengths[s] for s in r["selected"]) <= 12000)
                             for r in results["GoS-lite"].values())}
    _release(qwen)

    for spec, name in ((ENC_SKILLRET, "SkillRet-FT"), (ENC_SKILLROUTER, "SkillRouter-Emb")):
        enc = build_encoder(spec, cache_dir=cache_dir, dtype=DTYPE, batch_size=1)
        info[name] = enc.info()
        results[name] = _top_k(_dense(enc, skills, tasks, text_full))
        _release(enc)

    reranker = YesNoReranker(cache_path=Path(cache_dir) / "rerank_skillrouter.json", dtype=DTYPE)
    info["SkillRouter-Reranker"] = {"spec": reranker.spec, "top": SKILLROUTER_TOP}
    by_id = {s.id: s for s in skills}
    results["SkillRouter"], tail_ok = {}, []
    for t in tasks:
        first = results["SkillRouter-Emb"][t.id]["ranking"]
        head = [by_id[i] for i in first[:SKILLROUTER_TOP]]
        sc = reranker.score(t.text, head)
        order = sorted(range(len(head)), key=lambda i: (-sc[i], i))
        ranking = [head[i].id for i in order] + first[SKILLROUTER_TOP:]
        results["SkillRouter"][t.id] = {"ranking": ranking, "selected": ranking[:K_FIXED],
                                        "rerank_scores": {head[i].id: round(sc[i], 4) for i in order}}
        tail_ok.append(ranking[SKILLROUTER_TOP:] == first[SKILLROUTER_TOP:]
                       and set(ranking[:SKILLROUTER_TOP]) == set(first[:SKILLROUTER_TOP]))
    extra["SkillRouter"] = {"Chỉ xếp lại top-20, phần còn lại giữ nguyên": all(tail_ok)}
    reranker._model = None
    gc.collect()
    return {"results": results, "extra_checks": extra, "info": info, "tier1_excluded": reasons}


def score_gr1(run: dict, bench: GR1Benchmark) -> dict:
    labels = load_gr1_labels(bench.root)
    qrels = labels["qrels"]
    ids = [s.id for s in bench.skills]
    eligible_m1 = [i for i in ids if i not in run["tier1_excluded"]]
    table, per_task, checks = {}, {}, {}
    for m in [x["id"] for x in METHODS]:
        res = run["results"][m]
        rankings = ([{t: r["all_seeds"][s] for t, r in res.items()} for s in range(5)] if m == "Random"
                    else [{t: r["ranking"] for t, r in res.items()}])
        reports = [evaluate(rk, qrels, ks=(3, 5, 10)) for rk in rankings]
        mean = {k: float(np.mean([rep.mean[k] for rep in reports])) for k in reports[0].mean if k != "n_selected"}
        sets = [set_metrics(r["selected"], list(qrels[t])) for t, r in res.items()]
        mean.update({k: float(np.mean([s[k] for s in sets])) for k in sets[0]})
        table[m] = mean
        per_task[m] = {t: {"selected": r["selected"], "hits": sorted(set(r["selected"]) & set(qrels[t])),
                           "recall@3": reports[0].per_query[t]["Recall@3"],
                           **({"n_states": r["n_states"]} if "n_states" in r else {})} for t, r in res.items()}
        eligible = eligible_m1 if m == "M1 (GR1)" else ids
        checks[m] = check_output(m, res, ids, eligible, run["extra_checks"].get(m))
        floor = table.get("Random", {}).get("Recall@5")
        if m != "Random" and floor is not None:
            checks[m].append({"check": "Recall@5 cao hơn ngẫu nhiên (nhãn nháp, chỉ tham khảo)",
                              "passed": mean["Recall@5"] > floor, "detail": f"{mean['Recall@5']:.3f} vs {floor:.3f}"})
    digest = hashlib.sha256(json.dumps({m: {t: r["ranking"] for t, r in run["results"][m].items()}
                                        for m in run["results"]}, sort_keys=True).encode()).hexdigest()
    return {"labels_status": labels["status"], "metrics": table, "per_task": per_task, "checks": checks,
            "rankings_sha256": digest}
