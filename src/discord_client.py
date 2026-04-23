"""Discord 投稿 + リアクション操作 (REST API)。

- 投稿は Webhook で行い、botを常駐させない。
- リアクションの付与/取得には Bot Token + チャンネルID + メッセージID が必要。
- Webhook URL に ?wait=true を付けるとレスポンスに message id が返るので、
  その id を history に保存して翌日集計に使う。
"""
from __future__ import annotations

import logging
import os
import time
import urllib.parse as up
from typing import Any

import requests

log = logging.getLogger(__name__)

LIKE = "👍"
DISLIKE = "👎"

API_BASE = "https://discord.com/api/v10"


def post_message(content: str, embeds: list[dict] | None = None) -> str | None:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        log.warning("DISCORD_WEBHOOK_URL not set; skipping post")
        return None
    sep = "&" if "?" in url else "?"
    wait_url = f"{url}{sep}wait=true"
    payload: dict[str, Any] = {"content": content}
    if embeds:
        payload["embeds"] = embeds
    try:
        r = requests.post(wait_url, json=payload, timeout=20)
        if r.status_code == 429:
            retry_after = float(r.json().get("retry_after", 1.0))
            time.sleep(retry_after + 0.5)
            r = requests.post(wait_url, json=payload, timeout=20)
        r.raise_for_status()
        return r.json().get("id")
    except Exception as e:
        log.warning("Discord post failed: %s", e)
        return None


def add_reaction(channel_id: str, message_id: str, emoji: str = LIKE) -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        return
    emoji_enc = up.quote(emoji)
    url = f"{API_BASE}/channels/{channel_id}/messages/{message_id}/reactions/{emoji_enc}/@me"
    try:
        r = requests.put(url, headers={"Authorization": f"Bot {token}"}, timeout=15)
        if r.status_code not in (204, 200):
            log.debug("add_reaction %s %s -> %s", message_id, emoji, r.status_code)
    except Exception as e:
        log.warning("add_reaction failed: %s", e)


def count_reactions(channel_id: str, message_id: str, emoji: str) -> int:
    """指定絵文字のリアクション数 (bot 自身を除いた数) を返す。"""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        return 0
    emoji_enc = up.quote(emoji)
    url = f"{API_BASE}/channels/{channel_id}/messages/{message_id}"
    try:
        r = requests.get(url, headers={"Authorization": f"Bot {token}"}, timeout=15)
        if not r.ok:
            return 0
        for rx in r.json().get("reactions", []):
            if rx.get("emoji", {}).get("name") == emoji:
                # 自分もbotで押しているので -1
                return max(int(rx.get("count", 0)) - 1, 0)
        return 0
    except Exception as e:
        log.warning("count_reactions failed: %s", e)
        return 0
