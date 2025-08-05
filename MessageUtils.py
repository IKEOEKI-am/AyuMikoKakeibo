# MessageUtils.py
import re
from firebase_admin import firestore

# メッセージ形式のバリデーション（商品名 数字 円）
def is_valid_product_message(text):
    pattern = r"^[\wぁ-んァ-ン一-龥ー\s]+ (\d+)円$"
    return re.match(pattern, text)

# 金額の合計を計算
def calculate_total_amount():
    db = firestore.client()
    total = 0
    price_pattern = re.compile(r"\s(\d+)円$")
    messages = db.collection("messages").stream()

    for doc in messages:
        data = doc.to_dict()
        text = data.get("text", "")
        match = price_pattern.search(text)
        if match:
            total += int(match.group(1))
    return total