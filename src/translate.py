"""要旨を日本語に翻訳 (Google Cloud Translation v3)。"""
from __future__ import annotations

import logging
import os
from typing import Iterable

from .paper import Paper

log = logging.getLogger(__name__)


def _client():
    from google.cloud import translate_v2 as translate  # type: ignore
    return translate.Client()


def _is_japanese(text: str) -> bool:
    # ざっくり: 日本語特有の文字が閾値以上なら翻訳不要とみなす
    if not text:
        return True
    jp = sum(1 for ch in text if "぀" <= ch <= "ヿ" or "一" <= ch <= "鿿")
    return jp / max(len(text), 1) > 0.2


def translate_papers(papers: Iterable[Paper]) -> list[Paper]:
    papers = list(papers)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        log.warning("GOOGLE_APPLICATION_CREDENTIALS not set; skipping translation")
        for p in papers:
            p.abstract_ja = p.abstract
        return papers

    try:
        client = _client()
    except Exception as e:
        log.warning("Translate client init failed: %s", e)
        for p in papers:
            p.abstract_ja = p.abstract
        return papers

    for p in papers:
        if not p.abstract:
            p.abstract_ja = ""
            continue
        if _is_japanese(p.abstract):
            p.abstract_ja = p.abstract
            continue
        try:
            res = client.translate(p.abstract, target_language="ja", format_="text")
            p.abstract_ja = res.get("translatedText", p.abstract)
        except Exception as e:
            log.warning("Translate failed for %s: %s", p.id, e)
            p.abstract_ja = p.abstract
    return papers
