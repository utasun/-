# 建設AT 論文デイリー通知

建設業界の先端/応用技術分野 (BIM, ICT施工, 建設DX, 建設ロボット, AI 等) の論文を
**毎日** 自動で検索・翻訳・Discord通知・Google Drive保存し、👍/👎 リアクションで
推薦精度を上げていくパイプライン。

## 全体像

```
GitHub Actions (cron 毎日 08:00 JST)
  └─ src.main
       1. Discord リアクション収集 → preference.json 更新
       2. CiNii / J-STAGE / (Google Scholar) を横断検索
       3. 発行日フィルタ + 重複排除 (state/seen.json)
       4. PDF取得可否チェック
       5. 埋め込みベクトルで関連度スコア + 閾値フィルタ
       6. Google Translation で要旨を日本語化
       7. Discord Webhook で投稿 (👍👎 を初期リアクションとして付与)
       8. PDF を Google Drive にアップロード (日付サブフォルダ)
       9. state/ をコミット & push
```

## セットアップ

### 1. GitHub Secrets を登録

| Secret | 用途 | 取得方法 |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | 投稿先 Webhook URL | Discord チャンネル設定 → 連携サービス → Webhook |
| `DISCORD_BOT_TOKEN` | リアクション付与/集計用 | [Discord Developer Portal](https://discord.com/developers/applications) で Bot 作成 |
| `DISCORD_CHANNEL_ID` | リアクション対象のチャンネルID | 開発者モード ON → チャンネル右クリック → IDコピー |
| `GCP_SA_KEY` | Google Cloud サービスアカウントJSON 本体 | IAM → サービスアカウント → 鍵を作成 (JSON) |
| `GDRIVE_FOLDER_ID` | PDF保存先フォルダID | Drive フォルダURLの末尾文字列。サービスアカウントに「編集者」権限で共有 |

Bot は以下の権限で招待: `Read Message History`, `Add Reactions`, `View Channels`。
常駐不要 (REST でしか叩かない)。

GCP 側で必要な API:
- Cloud Translation API
- Google Drive API

### 2. 検索キーワードを調整

`config/keywords.yaml` を編集。初期値は建設DX関連。

### 3. 実行

GitHub Actions の `daily-paper-notifier` を手動実行 (`workflow_dispatch`) して
動作確認したあと、cron に任せる。

## ローカルでの動作確認

```bash
pip install -r requirements.txt

# APIに触るだけで投稿/保存しない
python -m src.main --dry-run -v

# J-STAGE だけ、1件だけ本番投稿
export DISCORD_WEBHOOK_URL=... DISCORD_BOT_TOKEN=... DISCORD_CHANNEL_ID=...
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp.json GDRIVE_FOLDER_ID=...
python -m src.main --only-sources jstage --limit 1 -v

# 前日分の 👍/👎 だけ取り込む
python -c "from src import feedback; feedback.update_from_reactions()"
```

## フィードバックによる学習

- 通知メッセージの 👍/👎 を翌日の run が REST で取得
- 👍 が多い → `liked_embeddings` に要旨の埋め込みを追加 & 一致キーワードの重みを +0.1
- 👎 が多い → `disliked_embeddings` に追加 & 重みを -0.1
- スコア = cosine(論文, 好き重心) − cosine(論文, 嫌い重心) + 重み和
- cold start (`feedback_count.like + dislike < 30`) 中はスコア閾値を無効化して全件通す

埋め込みモデル: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
(日英混在の要旨でも扱える軽量多言語モデル)

## 状態ファイル

- `state/seen.json` — 過去に通知した論文ID (DOI / URL)
- `state/preference.json` — 選好ベクトル・キーワード重み・フィードバック件数
- `state/history.jsonl` — 送信メッセージの一覧 (フィードバック集計対象)

これらは GitHub Actions が自動で `git commit && git push` する。

## ディレクトリ

```
.
├── .github/workflows/daily.yml
├── src/
│   ├── main.py              # エントリ
│   ├── collect.py           # 各ソース横断
│   ├── filter.py            # 重複/PDF/新鮮度
│   ├── scoring.py           # 埋め込み + 閾値
│   ├── translate.py         # Google Translation
│   ├── drive.py             # Google Drive
│   ├── discord_client.py    # Webhook & REST
│   ├── deliver.py           # 投稿 + Drive + history
│   ├── feedback.py          # リアクション集計 → preference
│   ├── state_store.py       # state I/O
│   ├── paper.py             # 共通データモデル
│   └── sources/
│       ├── cinii.py
│       ├── jstage.py
│       └── scholar.py
├── config/keywords.yaml
├── state/
└── requirements.txt
```

## 注意点

- **Google Scholar** は公式APIが無いため `scholarly` でスクレイピング。レート制限/IP ブロックの可能性あり。失敗してもパイプライン全体は止まらない。
- **無料枠**: Google Translation は月 50万文字までが 0円枠。要旨のみの翻訳なら十分収まる想定。
- **PDF取得不可** の論文は通知対象から除外される。要旨だけ欲しい場合は `filter.ensure_pdf` の呼び出しを外す。
