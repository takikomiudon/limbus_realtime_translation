import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader
from google.cloud import firestore
from pydantic import BaseModel

load_dotenv()


app = FastAPI(title="Limbus Translation API")

# Firestoreクライアントの初期化
db = firestore.Client(
    database='limbus-realtime-translator'
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限してください
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key"],
)

# APIキー認証の設定
API_KEY = os.environ["API_KEY"]
api_key_header = APIKeyHeader(name="X-API-Key")


async def get_api_key(api_key: str = Security(api_key_header)):
    if not API_KEY:
        logging.error("API key not configured in server")
        raise HTTPException(status_code=500, detail="API key not configured")
    if api_key != API_KEY:
        logging.error(f"Invalid API key: {api_key} != {API_KEY}")
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


# 翻訳データのモデル
class Translation(BaseModel):
    timestamp: int
    translation: str


@app.post("/api/translations")
async def create_translation(
    translation: Translation,
    api_key: str = Depends(get_api_key)
):
    """新しい翻訳を保存するエンドポイント"""
    # Firestoreに保存
    doc_ref = db.collection('translations').document()
    doc_ref.set({
        'timestamp': translation.timestamp,
        'translation': translation.translation,
        'created_at': datetime.now()
    })
    return {"status": "success"}


@app.get("/api/translations")
async def get_translations(limit: int = 100):
    """保存された翻訳を取得するエンドポイント"""
    # Firestoreから取得
    translations_ref = db.collection('translations')
    docs = translations_ref.order_by('timestamp', direction=firestore.Query.ASCENDING).limit(limit).stream()
    
    translations = []
    for doc in docs:
        data = doc.to_dict()
        translations.append({
            'timestamp': data['timestamp'],
            'translation': data['translation']
        })
    
    return {"translations": translations}


# シンプルなHTMLページを提供するエンドポイント
@app.get("/")
async def get_html():
    """翻訳履歴を表示するシンプルなWebページを返す"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Limbus Translation History</title>
        <meta charset="utf-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }
            #translations {
                max-height: 80vh;
                overflow-y: auto;
                padding-right: 10px;
            }
            .translation {
                background: white;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .timestamp {
                color: #666;
                font-size: 0.9em;
            }
            .text {
                margin-top: 5px;
                font-size: 1.1em;
            }
            #controls {
                position: sticky;
                top: 0;
                background: #f5f5f5;
                padding: 20px 0;
                margin-bottom: 20px;
                z-index: 100;
            }
            button {
                padding: 8px 15px;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background: #0056b3;
            }
            h1 {
                position: sticky;
                top: 0;
                background: #f5f5f5;
                margin: 0;
                padding: 20px 0;
                z-index: 100;
            }
        </style>
    </head>
    <body>
        <h1>Limbus Translation History v1</h1>
        <div id="controls">
            <button onclick="toggleAutoScroll()" id="autoScrollBtn">自動スクロール: ON</button>
        </div>
        <div id="translations"></div>

        <script>
            let autoScroll = true;
            let lastTranslationCount = 0;

            function formatTimestamp(timestamp) {
                return new Date(timestamp).toLocaleString('ja-JP');
            }

            function toggleAutoScroll() {
                autoScroll = !autoScroll;
                document.getElementById('autoScrollBtn').textContent = 
                    `自動スクロール: ${autoScroll ? 'ON' : 'OFF'}`;
            }

            function scrollToBottom() {
                if (autoScroll) {
                    const container = document.getElementById('translations');
                    container.scrollTop = container.scrollHeight;
                }
            }

            function updateTranslations() {
                fetch('/api/translations')
                    .then(response => response.json())
                    .then(data => {
                        const container = document.getElementById('translations');
                        if (data.translations.length !== lastTranslationCount) {
                            container.innerHTML = data.translations
                                .map(t => `
                                    <div class="translation">
                                        <div class="timestamp">
                                            ${formatTimestamp(t.timestamp)}
                                        </div>
                                        <div class="text">${t.translation}</div>
                                    </div>
                                `)
                                .join('');
                            lastTranslationCount = data.translations.length;
                            scrollToBottom();
                        }
                    });
            }

            // 初回読み込み
            updateTranslations();

            // 定期的に更新
            setInterval(updateTranslations, 5000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, media_type="text/html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
