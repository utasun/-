"""全ソース統合収集。"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .paper import Paper
from .sources import cinii, jstage, scholar

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "keywords.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_all(only_sources: list[str] | None = None) -> list[Paper]:
    cfg = load_config()
    queries: list[str] = cfg.get("queries", [])
    limits: dict = cfg.get("limits", {})

    sources = {
        "cinii": (cinii.search, limits.get("cinii", 20)),
        "jstage": (jstage.search, limits.get("jstage", 20)),
        "scholar": (scholar.search, limits.get("scholar", 10)),
    }
    if only_sources:
        sources = {k: v for k, v in sources.items() if k in only_sources}

    all_papers: dict[str, Paper] = {}
    for name, (fn, lim) in sources.items():
        for q in queries:
            log.info("Searching %s for %r", name, q)
            for p in fn(q, lim):
                # 同じ論文が複数クエリで引っかかった場合は matched キーワードをマージ
                if p.id in all_papers:
                    existing = all_papers[p.id]
                    for kw in p.keywords_matched:
                        if kw not in existing.keywords_matched:
                            existing.keywords_matched.append(kw)
                else:
                    all_papers[p.id] = p

    log.info("Collected %d unique papers across %d sources", len(all_papers), len(sources))
    return list(all_papers.values())
