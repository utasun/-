"""エントリポイント。

GitHub Actions からは引数なしで呼ぶ。ローカル検証時は --dry-run / --no-post /
--no-upload / --only-sources / --limit 等で制御できる。
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import collect, deliver, feedback, filter as pfilter, scoring, state_store, translate


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Daily paper notifier (建設AT)")
    ap.add_argument("--dry-run", action="store_true", help="投稿もアップロードもしない")
    ap.add_argument("--no-post", action="store_true", help="Discord投稿だけスキップ")
    ap.add_argument("--no-upload", action="store_true", help="Drive アップロードだけスキップ")
    ap.add_argument("--only-sources", nargs="+", choices=["cinii", "jstage", "scholar"])
    ap.add_argument("--limit", type=int, default=None, help="最終的に通知する最大件数")
    ap.add_argument("--skip-feedback", action="store_true", help="前日分のフィードバック収集をスキップ")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose > 1 else logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("main")

    # 1. 前日分フィードバックの取り込み (preference を更新してから今日のスコア計算に使う)
    if not args.skip_feedback and not args.dry_run:
        feedback.update_from_reactions()

    cfg = collect.load_config()

    # 2. 収集
    papers = collect.collect_all(only_sources=args.only_sources)

    # 3. 新鮮度フィルタ
    papers = pfilter.filter_freshness(papers, cfg.get("freshness_days", 30))

    # 4. 重複排除 (seen.json)
    seen = state_store.load_seen()
    papers = pfilter.dedupe(papers, seen)
    log.info("After dedupe: %d", len(papers))

    # 5. PDF 取得可能なものだけ残す
    with_pdf: list = []
    for p in papers:
        if pfilter.ensure_pdf(p):
            with_pdf.append(p)
    log.info("With PDF: %d", len(with_pdf))

    # 6. スコアリング
    pref = state_store.load_preference()
    scored = scoring.score_papers(with_pdf, pref)
    scored = scoring.apply_threshold(
        scored,
        threshold=cfg.get("score_threshold", 0.0),
        cold_start_min=cfg.get("cold_start_min_feedback", 30),
        pref=pref,
    )

    # 7. 上限
    if args.limit:
        scored = scored[: args.limit]

    # 8. 翻訳
    scored = translate.translate_papers(scored)

    # 9. 配信
    no_post = args.dry_run or args.no_post
    no_upload = args.dry_run or args.no_upload
    deliver.deliver(scored, no_post=no_post, no_upload=no_upload)

    # 10. seen 更新
    if not args.dry_run:
        for p in scored:
            seen.add(p.id)
        state_store.save_seen(seen)

    log.info("Done. notified=%d", len(scored))
    return 0


if __name__ == "__main__":
    sys.exit(main())
