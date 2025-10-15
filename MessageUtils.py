# MessageUtils.py
# 標準ライブラリ
import re
import calendar
from datetime import datetime, timedelta

# サードパーティライブラリ
from firebase_admin import firestore

from Categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES, FINANCIAL_ASSETS_CATEGORIES

def convert_zen_to_han(text):
    # 全角数字を半角数字に変換（Unicodeベース）
    return text.translate(str.maketrans(
        "０１２３４５６７８９",  # 全角
        "0123456789"             # 半角
    ))

def match_category(raw_text, category_list):
    for category in category_list:
        if category in raw_text:
            return category
    return None

def classify_transaction(text):
    text = convert_zen_to_han(text)
    pattern = r"^([^\d]+?)([\d,]+)円?$"
    match = re.match(pattern, text)
    if not match:
        return {"tag": "不明", "category": "未分類", "amount": None}

    raw_category = match.group(1).strip()
    try:
        amount = int(match.group(2).replace(",", ""))
    except ValueError:
        return {"tag": "不明", "category": "未分類", "amount": None}

    # 分類ロジック（収入優先→支出→未分類）
    if cat := match_category(raw_category, INCOME_CATEGORIES):
        tag = "収入"
        category = cat
    elif cat := match_category(raw_category, EXPENSE_CATEGORIES):
        tag = "支出"
        category = cat
    elif cat := match_category(raw_category, FINANCIAL_ASSETS_CATEGORIES):
        tag = "金融資産"
        category = cat
    else:
        tag = "不明"
        category = "未分類"
    
    return {"tag": tag, "category": category, "amount": amount}

# バリデーション（True/False）
def is_valid_product_message(text):
    result = classify_transaction(text)
    return result.get("amount") is not None

# 抽出（カテゴリ・金額）
def extract_category_and_amount(text):
    result = classify_transaction(text)
    return result or {"tag": "不明", "category": "未分類", "amount": None}

def parse_month_and_category(text):
    now = datetime.now()
    # 月に関する表現の正規表現
    month_match = re.search(r"(先月|今月|(\d{1,2})月)", text)
    # カテゴリ抽出（"の◯◯", "って◯◯", などを拾う）
    category_match = re.search(r"(?:の|って)([一-龠ぁ-んァ-ンa-zA-Z]+)", text)

    # 月の判定
    if month_match:
        if month_match.group(1) == "今月":
            month = now.month
            year = now.year
        elif month_match.group(1) == "先月":
            first_of_this_month = datetime(now.year, now.month, 1)
            last_month_date = first_of_this_month - timedelta(days=1)
            month = last_month_date.month
            year = last_month_date.year
        else:
            month = int(month_match.group(2))
            year = now.year
            if month > now.month:
                year -= 1
    else:
        return None, None, None  # 月が不明な場合は処理しない

    # カテゴリ名の抽出
    if category_match:
        category = category_match.group(1)
    else:
        category = None

    return year, month, category

def calculate_category_total_by_month(db, user_id, year, month, category):
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)

    query = db.collection("messages").where("user_id", "==", user_id) \
                                     .where("timestamp", ">=", start_date) \
                                     .where("timestamp", "<=", end_date) \
                                     .where("category", "==", category)

    total = sum(doc.to_dict().get("amount", 0) for doc in query.stream())
    return total