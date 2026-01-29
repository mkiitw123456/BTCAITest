# B.py
import google.generativeai as genai
import json
import warnings
import time
import os
from dotenv import load_dotenv # 👈 新增

# 載入 .env 檔案
load_dotenv()

# ==========================================
# 🔑 API KEY 池 (從環境變數讀取)
# ==========================================
keys_str = os.getenv("GEMINI_KEYS")
if not keys_str:
    raise ValueError("❌ 找不到 GEMINI_KEYS，請檢查 .env 檔案！")

# 將逗號隔開的字串轉回 List
API_KEYS = [k.strip() for k in keys_str.split(',') if k.strip()]
# ==========================================

warnings.filterwarnings("ignore")
current_key_index = 0
model = None

def get_best_model_for_key(api_key):
    genai.configure(api_key=api_key)
    try:
        valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in valid_models if 'flash' in m), None)
        target = target or next((m for m in valid_models if 'pro' in m), valid_models[0] if valid_models else None)
        return genai.GenerativeModel(target.replace("models/", "")) if target else None
    except: return None

def rotate_key():
    global current_key_index, model
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    model = get_best_model_for_key(API_KEYS[current_key_index])

rotate_key()

def ask_ai_for_signal(row, trend):
    global model
    rotate_key()
    
    # 判斷市場狀態
    adx_val = row['ADX']
    market_state = "強烈趨勢中 (Trend)" if adx_val > 25 else "震盪盤整中 (Range)"
    
    # 取得 V39 智能分數
    score_bull = row['SCORE_BULL']
    score_bear = row['SCORE_BEAR']
    
    prompt = f"""
    你是 V39 高階交易算法的決策中樞。請根據數學機率進行交易：
    
    【市場狀態】
    ADX: {adx_val:.1f} ({market_state})
    - ADX > 25 時，應順著 EMA/MACD 交易。
    - ADX < 25 時，應重視 RSI 超買超賣。
    
    【V39 智能評分 (已加權)】
    多頭得分: {score_bull:.1f} / 100
    空頭得分: {score_bear:.1f} / 100
    
    【當前數據】
    價格: {row['close']}
    RSI: {row['RSI']:.1f}
    MACD柱: {row['MACD_HIST']:.4f}
    EMA200: {row['EMA_200']:.1f}
    
    【凱利決策邏輯】
    1. 只有當某一方的「智能得分」顯著高於另一方 (例如 > 60分)，才考慮進場。
    2. 如果 多頭得分 > 60 且 多頭得分 > 空頭得分 -> 考慮 BUY。
    3. 如果 空頭得分 > 60 且 空頭得分 > 多頭得分 -> 考慮 SELL。
    4. 如果分數接近或都低於 50 -> 絕對 WAIT (凱利值為負，不賭博)。
    
    回傳 JSON: {{"action": "BUY" | "SELL" | "WAIT", "reason": "簡短理由 (含分數分析)"}}
    """

    max_retries = len(API_KEYS)
    for _ in range(max_retries):
        if model is None: rotate_key(); continue
        try:
            response = model.generate_content(prompt)
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except:
            rotate_key()
            continue

    return {"action": "WAIT", "reason": "All Keys Failed"}