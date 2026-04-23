"""重複排除 / PDF可否判定 / 関連度スコアリング。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import requests

from .paper import Paper
from . import state_store

log = logging.getLogger(__name__)

PDF_CONTENT_TYPES = ("application/pdf", "application/octet-stream")


def dedupe(papers: Iterable[Paper], seen: set[str]) -> list[Paper]:
    """seen に含まれないものだけを返す (呼び出し側で後から seen を更新)。"""
    out: list[Paper] = []
    local_seen: set[str] = set()
    for p in papers:
        if p.id in seen or p.id in local_seen:
            continue
        local_seen.add(p.id)
        out.append(p)
    return out


def _head(url: str) -> tuple[int, str]:
    try:
        r = requests.head(url, allow_redirects=True, timeout=15)
        return r.status_code, r.headers.get("Content-Type", "")
    except Exception as e:
        log.debug("HEAD failed for %s: %s", url, e)
        return 0, ""


def ensure_pdf(paper: Paper) -> Optional[Paper]:
    """PDFリンクが取れたものだけ返す (取れなければ None)。

    - すでに pdf_url が埋まっていればそれを信頼 (J-STAGE のケース)
    - なければ url を HEAD してPDFかどうか確認
    - なければ DOI から CrossRef 経由で PDF 候補を探す (簡易)
    """
    if paper.pdf_url:
        return paper
    if paper.url:
        status, ctype = _head(paper.url)
        if status == 200 and any(t in ctype.lower() for t in PDF_CONTENT_TYPES):
            paper.pdf_url = paper.url
            return paper
    if paper.doi:
        try:
            r = requests.get(
                f"https://api.crossref.org/works/{paper.doi}",
                timeout=15,
            )
            if r.ok:
                msg = r.json().get("message", {})
                for link in msg.get("link", []):
                    if "pdf" in (link.get("content-type") or "").lower():
                        paper.pdf_url = link["URL"]
                        return paper
        except Exception as e:
            log.debug("CrossRef lookup failed for %s: %s", paper.doi, e)
    return None


def filter_freshness(papers: Iterable[Paper], max_days: int) -> list[Paper]:
    if max_days <= 0:
        return list(papers)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_days)
    out: list[Paper] = []
    for p in papers:
        if not p.published:
            out.append(p)  # 発行日不明は通す
            continue
        try:
            # best-effort: YYYY / YYYY-MM / YYYY-MM-DD / full ISO
            text = p.published[:10]
            parts = text.split("-")
            y = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 1
            d = int(parts[2]) if len(parts) > 2 else 1
            pub = datetime(y, m, d, tzinfo=timezone.utc)
        except Exception:
            out.append(p)
            continue
        if pub >= cutoff:
            out.append(p)
    return out
