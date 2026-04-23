"""Google Scholar アダプタ (オプション)。

scholarly パッケージを使う。レート制限やIPブロックのリスクがあるため
失敗してもパイプラインが止まらない構造にしている。
"""
from __future__ import annotations

import logging
from typing import Iterable

from ..paper import Paper

log = logging.getLogger(__name__)


def search(query: str, limit: int = 10) -> Iterable[Paper]:
    try:
        from scholarly import scholarly  # type: ignore
    except Exception as e:
        log.warning("scholarly not available: %s", e)
        return []

    results: list[Paper] = []
    try:
        it = scholarly.search_pubs(query)
        for _ in range(limit):
            try:
                raw = next(it)
            except StopIteration:
                break
            bib = raw.get("bib") or {}
            title = bib.get("title") or ""
            if not title:
                continue
            url = raw.get("pub_url") or raw.get("eprint_url")
            pdf_url = raw.get("eprint_url") if raw.get("eprint_url", "").lower().endswith(".pdf") else None
            results.append(Paper(
                id=url or title,
                source="scholar",
                title=title,
                abstract=bib.get("abstract") or "",
                authors=bib.get("author", "").split(" and ") if isinstance(bib.get("author"), str) else bib.get("author", []),
                year=int(bib["pub_year"]) if str(bib.get("pub_year", "")).isdigit() else None,
                url=url,
                pdf_url=pdf_url,
                journal=bib.get("venue"),
                keywords_matched=[query],
            ))
    except Exception as e:
        log.warning("Google Scholar search failed for %r: %s", query, e)
    return results
