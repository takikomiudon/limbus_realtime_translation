# リアルタイム音声翻訳プログラム

このリポジトリは、マイクから韓国語音声をリアルタイムで取得し、Google Cloud Speech-to-Text と Gemini API を使って日本語へ翻訳するためのツールです。翻訳結果は任意で FastAPI サーバーへ送信し、Firestore に保存してブラウザで閲覧できます。

## 前提条件

- Python 3.11 以上（このリポジトリでは `.python-version` で 3.12 を指定）
- uv
- Google Cloud Platform のアカウント
- Google Cloud Speech-to-Text API の有効化
- Firestore の有効化
- Google Cloud サービスアカウントキー（JSON ファイル）
- Gemini API キー
- macOS で `pyaudio` を使う場合は PortAudio

macOS では、`pyaudio` のインストール前に次を実行してください。

```bash
brew install portaudio
```

## セットアップ

1. サーバー開発用の依存関係をインストールします。

```bash
uv sync
```

クライアントのマイク入力・音声認識まで使う場合は、音声関連の optional dependency も入れます。

```bash
uv sync --extra client
```

2. 環境変数ファイルを作成します。

```bash
cp .env.example .env
```

`.env` には以下を設定します。

- `GOOGLE_API_KEY`: Gemini API キー
- `GOOGLE_APPLICATION_CREDENTIALS`: Google Cloud サービスアカウント JSON のパス
- `API_BASE_URL`: 翻訳送信先。ローカルサーバーの場合は `http://localhost:8000/api/translations`
- `API_KEY`: クライアントとサーバーで共有する API キー
- `FIRESTORE_DATABASE`: Firestore database 名

既存の `pip` 運用を使う場合は、互換用の requirements も利用できます。

```bash
pip install -r requirements.txt
pip install -r server/requirements.txt
```

## サーバーの起動

翻訳履歴を保存・表示するサーバーを起動します。

```bash
uv run uvicorn server.server:app --host 0.0.0.0 --port 8000
```

ブラウザで `http://localhost:8000` を開くと、翻訳履歴を確認できます。

## Docker

Docker でサーバーを起動できます。このコマンドは `.env` を読み、通常のローカル起動と同じ Firestore 接続先を使います。

```bash
docker compose up --build
```

別のターミナルで疎通を確認します。

```bash
curl -fsS http://localhost:8000/
curl -fsS http://localhost:8000/api/translations
```

Firestore emulator を使う場合だけ、emulator 用 compose ファイルを追加します。これは本物の Firestore ではなく、空のローカル emulator を見ます。

```bash
docker compose -f docker-compose.yml -f docker-compose.emulator.yml up --build
```

emulator に対する integration test は、emulator compose 起動中に次を実行します。

```bash
env API_KEY=change-me \
  GOOGLE_CLOUD_PROJECT=limbus-local \
  FIRESTORE_DATABASE='(default)' \
  FIRESTORE_EMULATOR_HOST=localhost:8080 \
  uv run pytest tests/test_firestore_emulator.py
```

## クライアントの起動

マイク入力から翻訳を開始します。

```bash
uv sync --extra client
uv run python main.py
```

マイクに向かって話しかけると、認識された韓国語と日本語翻訳がコンソールに表示されます。`API_BASE_URL` と `API_KEY` を設定している場合、翻訳結果はサーバーにも送信されます。

## 開発用コマンド

```bash
uv run pytest
uv run ruff check .
docker build -t limbus-translation-server .
```

CI は GitHub Actions の `.github/workflows/ci.yml` で、uv sync、Ruff、pytest、Docker build、Firestore emulator integration test を実行します。
`main` ブランチへの push では、これらの job が成功した後に Cloud Run へ自動デプロイします。

## Cloud Run 自動デプロイ

GitHub Actions から Cloud Run へデプロイするには、GitHub repository の Settings で以下を設定します。

Secrets:

- `GCP_SA_KEY`: Google Cloud サービスアカウントキー JSON の全文
- `API_KEY`: クライアントと Cloud Run サーバーで共有する API キー

Variables:

- `GCP_PROJECT_ID`: デプロイ先の Google Cloud project ID
- `GCP_REGION`: Cloud Run と Artifact Registry の region（例: `asia-northeast1`）
- `ARTIFACT_REGISTRY_REPOSITORY`: Docker image を push する Artifact Registry repository 名
- `CLOUD_RUN_SERVICE`: Cloud Run service 名
- `FIRESTORE_DATABASE`: Cloud Run サーバーが使う Firestore database 名
- `CORS_ORIGINS`: 許可する CORS origin。複数指定する場合は comma 区切り

Artifact Registry repository は事前に作成しておきます。Cloud Run service は存在しない場合、deploy 時に作成されます。

`GCP_SA_KEY` のサービスアカウントには、少なくとも以下の権限を付与します。

- Cloud Run Admin
- Artifact Registry Writer
- Service Account User
- Firestore への読み書きに必要な権限

自動デプロイで作成される Docker image は、以下の形式で Artifact Registry に push されます。

```text
REGION-docker.pkg.dev/PROJECT_ID/REPOSITORY/limbus-translation-server:GITHUB_SHA
```

## コード構成

- `main.py`: 互換用のクライアント起動 entrypoint
- `client/`: マイク入力、Speech-to-Text、Gemini 翻訳、サーバー送信
- `server/server.py`: 互換用の ASGI entrypoint
- `server/app.py`: FastAPI app factory、依存性、route 定義
- `server/repository.py`: Firestore repository
- `server/templates/`: ブラウザ表示用 HTML

## カスタムボキャブラリーについて

このプログラムは Google Cloud Speech-to-Text のカスタムボキャブラリー機能を使用しています。
特定の専門用語や固有名詞の認識精度を向上させるために、カスタムボキャブラリーを設定することができます。
