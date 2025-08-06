# 標準ライブラリ
import os
import base64
import json
from datetime import datetime, timedelta

# サードパーティライブラリ
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import firebase_admin
from firebase_admin import credentials, firestore

from MessageUtils import is_valid_product_message, extract_category_and_amount, parse_month_and_category, calculate_category_total_by_month
from Categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES

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
    received_text = received_text.replace("　", " ")

    print("受け取ったメッセージ:", received_text)
    
    year, month, category = parse_month_and_category(received_text)
    if received_text == "カテゴリー":
        reply_lines = ["📂 カテゴリ一覧", "\n🧾 支出カテゴリ:"]
        reply_lines += [f"- {cat}" for cat in EXPENSE_CATEGORIES]
        reply_lines += ["\n💰 収入カテゴリ:"]
        reply_lines += [f"- {cat}" for cat in INCOME_CATEGORIES]
        reply_text = "\n".join(reply_lines)
    elif year and month and category:
        total = calculate_category_total_by_month(db, user_id, year, month, category)
        reply_text = f"{year}年{month}月の「{category}」は {total}円 です。"
    # Firestoreに保存
    elif is_valid_product_message(received_text):
        transaction = extract_category_and_amount(received_text)
        db.collection("messages").add({
            "user_id": user_id,
            "tag": transaction["tag"],
            "category": transaction["category"],
            "amount": transaction["amount"],
            "timestamp": datetime.utcnow(),
            "text": received_text
        })
        reply_text = f"保存しました: {received_text}"
    # 間違った形式
    else:
        reply_text = "商品名と金額を送って！"
    # 応答メッセージ
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

