# Ported verbatim from GR1 experiments/skill_graph/parsing_heuristic.py (sha256 cdbdd3149b22252aaa278f59664763929ae0834d7f1db15b9b7f41df015441ab, uncommitted in GR1).
# Parity with the original: tests/unit/test_graph_parity.py.
"""
Rule-of-thumb parser (no LLM, no API): the zero-cost stand-in for parsing.py, used by the S2 sandbox run.
It is deliberately simple; results obtained with it are a lower bound for what an LLM parser can give.

  decompose(task) -> TaskPlan
      Enumeration markers ("First,", "(2)", "Then", "Finally,", ...) split the request into sub-tasks. Without
      markers, every sentence that asks for something starts a sub-task (the sentences after it are appended).
      At most MAX_SUBTASKS: the shortest adjacent pair is merged until it fits. The text before the first sub-task
      is the initial state s_0 (the first sentence when there is none); state s_i (i >= 1) is the text of the
      completed sub-task i.
  contract(name, description, body) -> Contract
      precondition  the "Use when ..." clause of the description and/or a "Prerequisites / Requirements / When to
                    use" section of SKILL.md; None when neither exists
      completion    the description without its "Use when" clause, plus an "Output / Success criteria" section;
                    a description that is only a trigger falls back to the first sentence of "Overview / Purpose"
Neither function reads labels or the number of gold skills.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .core import TaskPlan

MAX_SUBTASKS = 4
SECTION_CHARS = 300
PRE_MAX_CHARS = 500
POST_MAX_CHARS = 500

MARKER_RE = re.compile(
    r"(?:(?<=\s)|^)(?:\(\d\)|\d[.)](?=\s)|(?:first|second|third|fourth|fifth)(?:ly)?,|finally,|lastly,|next,|"
    r"(?:and )?then,?(?=\s)|after that,?|also,|additionally,|on top of that,?|separately,)", re.I)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
REQUEST_RE = re.compile(
    r"\b(i need|i want|i'd like|i would like|can you|could you|help (?:me|us)|please|we need|we want|"
    r"design|build|create|write|implement|set up|generate|review|analy[sz]e|fix|add|make|explain|include|"
    r"produce|draft|refactor|migrate|deploy|test|audit|optimi[sz]e)\b", re.I)

TRIGGER_RE = re.compile(
    r"\b(?:use (?:this skill |it )?(?:when|for|if|whenever|to)|trigger(?:s|ed)? (?:when|on|by)|invoke when|"
    r"activate(?:s)? when|when (?:the )?user)\b", re.I)
HEADING_RE = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*$")
CODE_RE = re.compile(r"```.*?```", re.S)
FRONT_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)
PRE_HEADS = ("prerequisite", "requirement", "when to use", "dependencies", "before you start", "inputs")
POST_HEADS = ("output", "success criteria", "deliverable", "result")
ABOUT_HEADS = ("overview", "purpose", "what this skill does", "capabilities", "summary")


def _clean(text: str) -> str:
    text = re.sub(r"[`*_>#|]+", " ", text)
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()


def _merge_shortest(parts: List[str], limit: int) -> List[str]:
    parts = list(parts)
    while len(parts) > limit:
        i = min(range(len(parts) - 1), key=lambda j: len(parts[j]) + len(parts[j + 1]))
        parts[i:i + 2] = [parts[i] + " " + parts[i + 1]]
    return parts


def split_request(task: str) -> Tuple[str, List[str]]:
    """(context, sub-tasks) of a task text."""
    text = task.strip()
    cuts = [m.start() for m in MARKER_RE.finditer(text)]
    if cuts:
        context = text[:cuts[0]].strip()
        bounds = cuts + [len(text)]
        subs = [text[a:b].strip() for a, b in zip(bounds[:-1], bounds[1:])]
    else:
        context_parts: List[str] = []
        subs = []
        for sent in (s.strip() for s in SENTENCE_RE.split(text)):
            if not sent:
                continue
            if REQUEST_RE.search(sent):
                subs.append(sent)
            elif subs:
                subs[-1] += " " + sent
            else:
                context_parts.append(sent)
        context = " ".join(context_parts)
    subs = [s for s in subs if len(s) > 2] or [text]
    return context, _merge_shortest(subs, MAX_SUBTASKS)


def decompose(task: str) -> TaskPlan:
    context, subs = split_request(task)
    s0 = context or SENTENCE_RE.split(task.strip())[0]
    return TaskPlan(subtasks=tuple(subs), states=(s0, *subs))


def _sections(body: str) -> Dict[str, str]:
    """Normalised heading -> text up to the next heading (code blocks removed); first occurrence wins."""
    body = CODE_RE.sub(" ", FRONT_RE.sub("", body))
    heads = list(HEADING_RE.finditer(body))
    out: Dict[str, str] = {}
    for h, nxt in zip(heads, heads[1:] + [None]):
        key = re.sub(r"[^a-z ]", "", h.group(1).lower()).strip()
        out.setdefault(key, body[h.end():nxt.start() if nxt else len(body)])
    return out


def _section(sections: Dict[str, str], wanted) -> str:
    for key, text in sections.items():
        if any(w in key for w in wanted):
            cleaned = _clean(text)
            if cleaned:
                return cleaned[:SECTION_CHARS]
    return ""


@dataclass(frozen=True)
class Contract:
    precondition: Optional[str]
    completion: str
    pre_source: str            # "trigger" | "section" | "both" | "none"
    post_source: str           # "description" | "section" | "both" | "fallback"


def contract(name: str, description: str, body: str) -> Contract:
    desc = _clean(description)
    m = TRIGGER_RE.search(desc)
    what, trigger = (desc[:m.start()].strip(), desc[m.start():].strip()) if m else (desc, "")
    sections = _sections(body or "")
    pre_sec = _section(sections, PRE_HEADS)
    post_sec = _section(sections, POST_HEADS)

    pre = " ".join(x for x in (trigger, pre_sec) if x)[:PRE_MAX_CHARS] or None
    pre_source = {(True, True): "both", (True, False): "trigger", (False, True): "section"}.get(
        (bool(trigger), bool(pre_sec)), "none")

    if len(what) < 20:                                    # the description is only a trigger
        about = _section(sections, ABOUT_HEADS)
        what = SENTENCE_RE.split(about)[0] if about else ""
        desc_ok = False
    else:
        desc_ok = True
    post = " ".join(x for x in (what, post_sec) if x)[:POST_MAX_CHARS]
    post_source = {(True, True): "both", (True, False): "description", (False, True): "section"}.get(
        (desc_ok, bool(post_sec)), "fallback")
    if not post:
        post = f"{name}. {desc}"[:POST_MAX_CHARS]
    return Contract(pre, post, pre_source, post_source)
