"""state/ 配下の JSON / JSONL ファイルの読み書きを一元化。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
SEEN = STATE_DIR / "seen.json"
PREFERENCE = STATE_DIR / "preference.json"
HISTORY = STATE_DIR / "history.jsonl"


def load_seen() -> set[str]:
    if not SEEN.exists():
        return set()
    data = json.loads(SEEN.read_text(encoding="utf-8") or '{"ids": []}')
    return set(data.get("ids", []))


def save_seen(ids: set[str]) -> None:
    SEEN.write_text(
        json.dumps({"ids": sorted(ids)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_preference() -> dict:
    if not PREFERENCE.exists():
        return {
            "liked_embeddings": [],
            "disliked_embeddings": [],
            "keyword_weights": {},
            "feedback_count": {"like": 0, "dislike": 0},
        }
    return json.loads(PREFERENCE.read_text(encoding="utf-8"))


def save_preference(pref: dict) -> None:
    PREFERENCE.write_text(
        json.dumps(pref, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_history(entry: dict) -> None:
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def iter_history() -> list[dict]:
    if not HISTORY.exists():
        return []
    out: list[dict] = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def rewrite_history(entries: list[dict]) -> None:
    with open(HISTORY, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
