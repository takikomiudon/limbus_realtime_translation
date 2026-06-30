# Limbus Translation Server

リンバス・カンパニーの翻訳履歴を表示するためのシンプルな Web サーバーです。

## セットアップ

1. リポジトリルートで依存関係をインストールします。

```bash
uv sync
```

2. `.env.example` を `.env` にコピーし、少なくとも次を設定します。

- `API_KEY`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `FIRESTORE_DATABASE`

3. サーバーを起動します。

```bash
uv run uvicorn server.server:app --host 0.0.0.0 --port 8000
```

サーバーは `http://localhost:8000` で起動します。

## エンドポイント

- `GET /`: 翻訳履歴を表示する Web インターフェース
- `POST /api/translations`: 新しい翻訳を保存
- `GET /api/translations`: 保存された翻訳を取得
- `DELETE /api/translations`: 全ての翻訳履歴を削除

## 本番環境での注意点

1. CORS 設定を適切に制限してください
2. データの永続化（データベースの使用）を検討してください
3. 必要に応じて認証を追加してください

## 開発

Firestore 接続は FastAPI の依存性として分離されています。テストでは Fake Repository に差し替えるため、ローカルで実 Firestore に接続せずに確認できます。

```bash
uv run pytest
uv run ruff check .
```

## Firestore emulator

通常の `docker compose up --build` は `.env` の Firestore 接続先を使います。Firestore emulator を使う場合だけ、emulator 用 compose ファイルを追加します。

```bash
docker compose -f docker-compose.yml -f docker-compose.emulator.yml up --build
```

emulator compose 起動中に、integration test を実行できます。

```bash
env API_KEY=change-me \
  GOOGLE_CLOUD_PROJECT=limbus-local \
  FIRESTORE_DATABASE='(default)' \
  FIRESTORE_EMULATOR_HOST=localhost:8080 \
  uv run pytest tests/test_firestore_emulator.py
```
