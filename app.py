from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import base64
import json

from MessageUtils import is_valid_product_message, calculate_total_amount

app = Flask(__name__)

# LINE Bot設定
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN", "YOUR_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET", "YOUR_CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Firebase初期化：Base64環境変数からデコード
encoded_key = os.getenv("FIREBASE_KEY_BASE64", "")
if encoded_key:
    try:
        decoded_json = json.loads(base64.b64decode(encoded_key))
        cred = credentials.Certificate(decoded_json)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        raise RuntimeError(f"Firebaseの初期化エラー: {e}")
else:
    raise RuntimeError("FIREBASE_KEY_BASE64 が設定されていません")

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    received_text = event.message.text
    user_id = event.source.user_id

    # 全角スペースを半角スペースへ変換
    received_text = raw_text.replace("　", " ")

    if received_text == "合計":
        total_amount = calculate_total_amount()
        reply_text = f"合計金額は {total_amount}円 です。"
    # Firestoreに保存
    elif is_valid_product_message(received_text):
        db.collection("messages").add({
            "user_id": user_id,
            "text": received_text,
            "timestamp": datetime.utcnow()
        })
        reply_text = f"保存しました: {received_text}"
    # 間違った形式
    else:
        reply_text = "「商品名 半角スペース 金額円」の形式で送ってね！（例：りんご 200円）"
    # 応答メッセージ
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

# Renderでは gunicorn で起動するため、app.run() は不要
