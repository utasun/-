"""Discord リアクション集計 → preference.json 更新。"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from . import discord_client, scoring, state_store
from .paper import Paper

log = logging.getLogger(__name__)

# 埋め込みを何件まで保持するか (古いものから捨てる)
MAX_KEEP = 50


def _paper_from(dct: dict) -> Paper:
    return Paper(**{k: v for k, v in dct.items() if k in Paper.__dataclass_fields__})


def update_from_reactions() -> dict:
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    if not channel_id:
        log.warning("DISCORD_CHANNEL_ID not set; skipping feedback update")
        return state_store.load_preference()

    history = state_store.iter_history()
    pref = state_store.load_preference()
    changed = False

    for entry in history:
        if entry.get("feedback_collected"):
            continue
        msg_id = entry.get("message_id")
        if not msg_id:
            continue
        likes = discord_client.count_reactions(channel_id, msg_id, discord_client.LIKE)
        dislikes = discord_client.count_reactions(channel_id, msg_id, discord_client.DISLIKE)
        if likes == 0 and dislikes == 0:
            # まだ判断されていない可能性。一定日数過ぎていればあきらめる
            posted = entry.get("posted_at")
            if posted:
                try:
                    age = datetime.now(timezone.utc) - datetime.fromisoformat(posted)
                    if age.days < 3:
                        continue
                except Exception:
                    pass
            entry["feedback_collected"] = True
            changed = True
            continue

        paper = _paper_from(entry["paper"])
        text = f"{paper.title}\n{paper.abstract}"
        vec = scoring.embed(text).tolist()

        if likes > dislikes:
            pref.setdefault("liked_embeddings", []).append(vec)
            pref["feedback_count"]["like"] = pref["feedback_count"].get("like", 0) + 1
            for kw in paper.keywords_matched:
                pref.setdefault("keyword_weights", {})
                pref["keyword_weights"][kw] = round(pref["keyword_weights"].get(kw, 0.0) + 0.1, 3)
        elif dislikes > likes:
            pref.setdefault("disliked_embeddings", []).append(vec)
            pref["feedback_count"]["dislike"] = pref["feedback_count"].get("dislike", 0) + 1
            for kw in paper.keywords_matched:
                pref.setdefault("keyword_weights", {})
                pref["keyword_weights"][kw] = round(pref["keyword_weights"].get(kw, 0.0) - 0.1, 3)
        # 同数は情報なしとして扱う

        entry["feedback_collected"] = True
        changed = True

    # 古い埋め込みは捨てる (直近の好みを優先)
    for key in ("liked_embeddings", "disliked_embeddings"):
        if len(pref.get(key, [])) > MAX_KEEP:
            pref[key] = pref[key][-MAX_KEEP:]

    if changed:
        state_store.rewrite_history(history)
        state_store.save_preference(pref)
    return pref
