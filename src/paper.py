"""共通データモデル: Paper。各ソースアダプタがこの形に正規化する。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Paper:
    id: str                 # 一意ID (DOI があれば DOI、なければ URL)
    source: str             # "cinii" | "jstage" | "scholar"
    title: str
    abstract: str           # 原文要旨 (空文字の場合もある)
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    published: Optional[str] = None   # ISO 8601 文字列
    url: Optional[str] = None         # 記事ページ
    pdf_url: Optional[str] = None     # 直リンク (判定後に確定)
    doi: Optional[str] = None
    journal: Optional[str] = None
    keywords_matched: list[str] = field(default_factory=list)

    # 後工程で追加される
    abstract_ja: Optional[str] = None
    score: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)
