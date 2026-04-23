"""Discord 通知 + Drive アップロード + history 記録。"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Iterable

import requests

from . import discord_client, drive, state_store
from .paper import Paper

log = logging.getLogger(__name__)


def _truncate(text: str, n: int) -> str:
    text = text.strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _embed_for(paper: Paper, drive_link: str | None) -> dict:
    desc = paper.abstract_ja or paper.abstract or ""
    fields = []
    if paper.authors:
        fields.append({"name": "著者", "value": _truncate(", ".join(paper.authors), 200), "inline": False})
    if paper.journal:
        fields.append({"name": "掲載誌", "value": _truncate(paper.journal, 200), "inline": True})
    if paper.year:
        fields.append({"name": "発行年", "value": str(paper.year), "inline": True})
    if drive_link:
        fields.append({"name": "Drive", "value": drive_link, "inline": False})
    if paper.score is not None:
        fields.append({"name": "関連度", "value": f"{paper.score:+.3f}", "inline": True})
    return {
        "title": _truncate(paper.title, 240),
        "description": _truncate(desc, 1800),
        "url": paper.url or paper.pdf_url,
        "fields": fields,
        "footer": {"text": f"{paper.source} • matched: {', '.join(paper.keywords_matched[:3])}"},
    }


def _download_pdf(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        data = r.content
        if not data:
            return None
        return data
    except Exception as e:
        log.warning("PDF download failed %s: %s", url, e)
        return None


def deliver(papers: Iterable[Paper], no_post: bool = False, no_upload: bool = False) -> list[str]:
    papers = list(papers)
    channel_id = os.environ.get("DISCORD_CHANNEL_ID", "")
    posted_ids: list[str] = []

    for p in papers:
        drive_link = None
        if not no_upload and p.pdf_url:
            pdf_bytes = _download_pdf(p.pdf_url)
            if pdf_bytes:
                safe = (p.title or p.id)[:60].replace("/", "_")
                fname = f"{p.source}_{(p.year or 'NA')}_{safe}.pdf"
                drive_link = drive.upload_pdf(pdf_bytes, fname)

        if no_post:
            log.info("[dry] %s | %s", p.title, p.pdf_url)
            continue

        msg_id = discord_client.post_message(content="", embeds=[_embed_for(p, drive_link)])
        if msg_id:
            posted_ids.append(msg_id)
            if channel_id:
                discord_client.add_reaction(channel_id, msg_id, discord_client.LIKE)
                discord_client.add_reaction(channel_id, msg_id, discord_client.DISLIKE)
            state_store.append_history({
                "message_id": msg_id,
                "channel_id": channel_id,
                "paper": p.to_dict(),
                "drive_link": drive_link,
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "feedback_collected": False,
            })
    return posted_ids
