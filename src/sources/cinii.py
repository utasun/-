"""CiNii Research API アダプタ。

OpenSearch 準拠の JSON エンドポイントを叩く。認証不要。
https://support.nii.ac.jp/ja/cir/r_opensearch
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

import requests

from ..paper import Paper

log = logging.getLogger(__name__)

BASE = "https://cir.nii.ac.jp/opensearch/all"


def _pick(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k]:
            return d[k]
    return default


def _extract_doi(item: dict) -> str | None:
    # dc:identifier に "info:doi/10.xxxx" 形式が入ることがある
    ids = item.get("dc:identifier") or item.get("identifier") or []
    if isinstance(ids, str):
        ids = [ids]
    for i in ids:
        s = i.get("@value") if isinstance(i, dict) else str(i)
        m = re.search(r"10\.\d{4,9}/[^\s\"<>]+", s)
        if m:
            return m.group(0)
    return None


def search(query: str, limit: int = 20) -> Iterable[Paper]:
    """単一クエリでCiNii Researchを検索。"""
    params = {
        "q": query,
        "format": "json",
        "count": limit,
        "sortorder": "0",   # 新着順
    }
    try:
        r = requests.get(BASE, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("CiNii request failed for %r: %s", query, e)
        return []

    items = data.get("items") or data.get("@graph") or []
    if isinstance(items, dict):
        items = [items]

    results: list[Paper] = []
    for it in items:
        title = _pick(it, "title", "dc:title", default="") or ""
        if isinstance(title, dict):
            title = title.get("@value", "")
        abstract = _pick(it, "description", "dc:description", default="") or ""
        if isinstance(abstract, dict):
            abstract = abstract.get("@value", "")
        url = _pick(it, "link", "@id", "id")
        if isinstance(url, dict):
            url = url.get("@id") or url.get("href")

        doi = _extract_doi(it)
        paper_id = doi or (url if isinstance(url, str) else str(it.get("@id") or title))
        if not paper_id or not title:
            continue

        authors_raw = it.get("dc:creator") or it.get("author") or []
        if isinstance(authors_raw, (str, dict)):
            authors_raw = [authors_raw]
        authors = [a.get("@value") if isinstance(a, dict) else str(a) for a in authors_raw]

        date = _pick(it, "prism:publicationDate", "dc:date", "published")
        if isinstance(date, dict):
            date = date.get("@value")
        year = None
        if isinstance(date, str):
            m = re.search(r"(\d{4})", date)
            if m:
                year = int(m.group(1))

        journal = _pick(it, "prism:publicationName", "dc:publisher")
        if isinstance(journal, dict):
            journal = journal.get("@value")

        results.append(Paper(
            id=str(paper_id),
            source="cinii",
            title=str(title).strip(),
            abstract=str(abstract).strip(),
            authors=[a for a in authors if a],
            year=year,
            published=str(date) if date else None,
            url=url if isinstance(url, str) else None,
            doi=doi,
            journal=str(journal) if journal else None,
            keywords_matched=[query],
        ))
    return results
