# リアルタイム音声翻訳プログラム

このプログラムは、マイクからの音声入力をリアルタイムで取得し、Google Cloud Speech-to-Text と Translate API を使用して翻訳を行います。

## 前提条件

- Python 3.8 以上
- Google Cloud Platform のアカウント
- Google Cloud Speech-to-Text API の有効化
- Google Cloud Translate API の有効化
- サービスアカウントキー（JSON ファイル）

## セットアップ

1. 必要なパッケージのインストール:

```bash
pip install -r requirements.txt
```

2. 環境変数の設定:

- `.env.example`ファイルを`.env`にコピーし、必要な情報を入力してください。
- Google Cloud のサービスアカウントキーのパスを設定してください。

## 使用方法

1. プログラムの実行:

```bash
python realtime_translator.py
```

2. マイクに向かって話しかけてください。
3. 翻訳結果がリアルタイムで表示されます。

## カスタムボキャブラリーについて

このプログラムは Google Cloud Speech-to-Text のカスタムボキャブラリー機能を使用しています。
特定の専門用語や固有名詞の認識精度を向上させるために、カスタムボキャブラリーを設定することができます。
