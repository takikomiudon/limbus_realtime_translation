# Limbus Translation Server

リンバス・カンパニーの翻訳履歴を表示するためのシンプルな Web サーバーです。

## セットアップ

1. 依存関係のインストール:

```bash
pip install -r requirements.txt
```

2. サーバーの起動:

```bash
python server.py
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
