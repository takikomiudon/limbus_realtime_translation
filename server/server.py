import asyncio
import logging
import os
import time
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader
from google.cloud import firestore
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()
logging.basicConfig(level=logging.INFO)

# レート制限の設定
RATE_LIMIT_SECONDS = 0.5  # 0.5秒あたりの最大リクエスト数（1秒間に2リクエストまで）
rate_limit_store = {}

# Firestoreの再試行設定
RETRY_MULTIPLIER = 1.5  # 再試行間隔の乗数
INITIAL_RETRY_DELAY = 1.0  # 初期再試行間隔（秒）
MAX_RETRY_DELAY = 30.0  # 最大再試行間隔（秒）
MAX_RETRY_ATTEMPTS = 3  # 最大再試行回数

def with_firestore_retry(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        retry_delay = INITIAL_RETRY_DELAY
        attempts = 0
        
        while attempts < MAX_RETRY_ATTEMPTS:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                attempts += 1
                if attempts == MAX_RETRY_ATTEMPTS:
                    logging.error(f"Failed after {attempts} attempts: {str(e)}")
                    raise HTTPException(
                        status_code=503,
                        detail="Database service temporarily unavailable"
                    )
                
                logging.warning(f"Attempt {attempts} failed: {str(e)}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * RETRY_MULTIPLIER, MAX_RETRY_DELAY)
        
        return None
    return wrapper

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # HTMLページへのアクセスは緩めのレート制限を適用
        client_ip = request.client.host
        current_time = time.time()

        if request.url.path == "/":
            # HTMLページは3秒に1回まで
            if client_ip in rate_limit_store:
                last_request_time = rate_limit_store[client_ip]
                if current_time - last_request_time < 3:
                    raise HTTPException(
                        status_code=429,
                        detail="Too many requests. Please try again later."
                    )
        # APIエンドポイントは0.5秒に1回まで
        elif request.url.path.startswith("/api/"):
            if client_ip in rate_limit_store:
                last_request_time = rate_limit_store[client_ip]
                if current_time - last_request_time < RATE_LIMIT_SECONDS:
                    raise HTTPException(
                        status_code=429,
                        detail="Too many requests. Please try again later."
                    )

        rate_limit_store[client_ip] = current_time
        return await call_next(request)


app = FastAPI(title="Limbus Translation API")

# セキュリティミドルウェアの追加
app.add_middleware(RateLimitMiddleware)

# Firestoreクライアントの初期化
try:
    db = firestore.Client(
        database='limbus-realtime-translator'
    )
    # 接続テスト
    db.collection('translations').limit(1).get()
    logging.info("Successfully connected to Firestore")
except Exception as e:
    logging.error(f"Failed to initialize Firestore client: {e}")
    raise

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key"],
)

# APIキー認証の設定
API_KEY = os.environ["API_KEY"]
api_key_header = APIKeyHeader(name="X-API-Key")


async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    return api_key


# 翻訳データのモデル
class Translation(BaseModel):
    timestamp: int
    translation: str


@app.post("/api/translations")
@with_firestore_retry
async def create_translation(
    translation: Translation,
    api_key: str = Depends(get_api_key)
):
    """新しい翻訳を保存するエンドポイント"""
    try:
        # Firestoreに保存
        doc_ref = db.collection('translations').document()
        doc_ref.set({
            'timestamp': translation.timestamp,
            'translation': translation.translation,
            'created_at': datetime.now()
        })
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Failed to save translation: {e}")
        raise


@app.get("/api/translations")
@with_firestore_retry
async def get_translations(
    limit: int = 100,
):
    """保存された翻訳を取得するエンドポイント"""
    if limit > 1000:  # 最大取得件数の制限
        limit = 1000

    try:
        # Firestoreから取得
        translations_ref = db.collection('translations')
        docs = translations_ref.order_by(
            'timestamp',
            direction=firestore.Query.ASCENDING
        ).limit(limit).stream()

        translations = []
        for doc in docs:
            data = doc.to_dict()
            translations.append({
                'timestamp': data['timestamp'],
                'translation': data['translation']
            })

        return {"translations": translations}
    except Exception as e:
        logging.error(f"Failed to fetch translations: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


# シンプルなHTMLページを提供するエンドポイント
@app.get("/")
async def get_html():
    """翻訳履歴を表示するシンプルなWebページを返す"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Limbus Translation History v1.2</title>
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
            button:disabled {
                background: #cccccc;
                cursor: not-allowed;
            }
            h1 {
                position: sticky;
                top: 0;
                background: #f5f5f5;
                margin: 0;
                padding: 20px 0;
                z-index: 100;
            }
            #error-message {
                color: red;
                margin: 10px 0;
                display: none;
            }
            #refresh-button {
                margin-left: 10px;
            }
        </style>
    </head>
    <body>
        <h1>Limbus Translation History v1.2</h1>
        <div id="controls">
            <button onclick="toggleAutoScroll()" id="autoScrollBtn">自動スクロール: ON</button>
            <button onclick="manualRefresh()" id="refresh-button">手動更新</button>
        </div>
        <div id="error-message">エラーが発生しました。しばらく待ってから手動更新ボタンを押してください。</div>
        <div id="translations"></div>

        <script>
            let autoScroll = true;
            let lastTranslationCount = 0;
            let isUpdating = false;
            let updateInterval = 3000; // 3秒ごとに更新に変更
            let errorCount = 0;
            const MAX_ERROR_COUNT = 3;
            let nextUpdateTime = 0;
            const MIN_UPDATE_INTERVAL = 2000; // 最小更新間隔を2秒に変更

            function formatTimestamp(timestamp) {
                const date = new Date(timestamp);
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                const seconds = String(date.getSeconds()).padStart(2, '0');
                return `${year}年${month}月${day}日 ${hours}:${minutes}:${seconds}`;
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

            async function manualRefresh() {
                const now = Date.now();
                if (now < nextUpdateTime) {
                    return; // 最小更新間隔を守る
                }

                const refreshButton = document.getElementById('refresh-button');
                refreshButton.disabled = true;

                try {
                    await updateTranslations();
                    errorCount = 0;
                    document.getElementById('error-message').style.display = 'none';
                } catch (error) {
                    console.error('更新エラー:', error);
                    handleError();
                } finally {
                    refreshButton.disabled = false;
                    nextUpdateTime = Date.now() + MIN_UPDATE_INTERVAL;
                }
            }

            function handleError() {
                errorCount++;
                const errorMessage = document.getElementById('error-message');
                errorMessage.style.display = 'block';

                if (errorCount >= MAX_ERROR_COUNT) {
                    // エラーが続く場合は自動更新を停止
                    clearInterval(updateTimer);
                    errorMessage.textContent = 'エラーが続いたため自動更新を停止しました。手動更新をお試しください。';
                }
            }

            async function updateTranslations() {
                if (isUpdating) return;
                isUpdating = true;

                try {
                    const response = await fetch('/api/translations');
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const data = await response.json();

                    if (data.translations.length !== lastTranslationCount) {
                        const container = document.getElementById('translations');
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
                } catch (error) {
                    console.error('Fetch error:', error);
                    handleError();
                } finally {
                    isUpdating = false;
                }
            }

            // 初回読み込み
            updateTranslations();

            // 定期的な更新
            const updateTimer = setInterval(async () => {
                if (document.hidden) return; // ページが非表示の場合は更新しない
                await updateTranslations();
            }, updateInterval);

            // ページの表示状態が変わったときの処理
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) {
                    updateTranslations(); // ページが表示されたときに更新
                }
            });

            // ページを閉じる前にタイマーをクリア
            window.addEventListener('beforeunload', () => {
                clearInterval(updateTimer);
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
