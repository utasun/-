"""J-STAGE WebAPI アダプタ。

service=3 (ArticleSearch) を使う。XMLレスポンスをパースして正規化する。
https://www.jstage.jst.go.jp/static/pages/JstageServices/TAB3/-char/ja
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Iterable

import requests

from ..paper import Paper

log = logging.getLogger(__name__)

BASE = "https://api.jstage.jst.go.jp/searchapi/do"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _text(el, tag: str) -> str:
    if el is None:
        return ""
    found = el.find(tag, NS)
    return (found.text or "").strip() if found is not None and found.text else ""


def search(query: str, limit: int = 20) -> Iterable[Paper]:
    params = {
        "service": 3,
        "text": query,
        "count": limit,
        "sort": 1,  # 新着順
    }
    try:
        r = requests.get(BASE, params=params, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        log.warning("J-STAGE request failed for %r: %s", query, e)
        return []

    results: list[Paper] = []
    for entry in root.findall("atom:entry", NS):
        title = _text(entry, "atom:article_title") or _text(entry, "atom:title")
        if not title:
            continue
        abstract = _text(entry, "atom:article_abstract") or _text(entry, "atom:abstract")
        # J-STAGE 記事URL
        article_link = None
        pdf_link = None
        for link in entry.findall("atom:link", NS):
            href = link.get("href")
            rel = link.get("rel", "")
            ltype = link.get("type", "")
            if not href:
                continue
            if "pdf" in href.lower() or "pdf" in ltype.lower():
                pdf_link = href
            elif article_link is None and rel in ("", "alternate"):
                article_link = href

        doi = _text(entry, "prism:doi")
        date = _text(entry, "prism:publicationDate") or _text(entry, "atom:updated")
        year = None
        if date:
            m = re.search(r"(\d{4})", date)
            if m:
                year = int(m.group(1))
        journal = _text(entry, "prism:publicationName")

        authors = []
        for a in entry.findall("atom:author", NS):
            name = _text(a, "atom:name")
            if name:
                authors.append(name)

        paper_id = doi or article_link or title
        results.append(Paper(
            id=paper_id,
            source="jstage",
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            published=date or None,
            url=article_link,
            pdf_url=pdf_link,
            doi=doi or None,
            journal=journal or None,
            keywords_matched=[query],
        ))
    return results
