# B.py - AI 大腦 (V44: Python 硬體防火牆版)
import google.generativeai as genai
import json
import warnings
import time
import os
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")
load_dotenv(env_path)

keys_str = os.getenv("GEMINI_KEYS")
if not keys_str: raise ValueError("找不到 GEMINI_KEYS")
API_KEYS = [k.strip() for k in keys_str.split(',') if k.strip()]

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
    
    # ==========================================
    # 🔥 V44 硬體防火牆 (Hard-Coded Filters)
    # ==========================================
    # 我們不再依賴 AI 判斷數值，直接用 Python 強制執行紀律
    
    rsi = row['RSI']
    adx = row['ADX']
    rvol = row['RVOL']
    ema_dist = row['EMA_DIST']
    
    # 1. 嚴格的 RSI 安全區 (35 ~ 65)
    # 只要超出這個範圍，代表肉不多了，風險大於利潤，直接觀望
    if rsi > 65: 
        return {"action": "WAIT", "reason": f"🛑 硬體攔截: RSI {rsi:.1f} 過熱 (大於 65)，拒絕追多"}
    if rsi < 35: 
        return {"action": "WAIT", "reason": f"🛑 硬體攔截: RSI {rsi:.1f} 過冷 (小於 35)，拒絕追空"}

    # 2. 嚴格的 ADX 門檻
    if adx < 20:
        return {"action": "WAIT", "reason": f"🛑 硬體攔截: ADX {adx:.1f} 過低，市場無方向 (死魚盤)"}
    
    # 3. 嚴格的乖離率保護
    if abs(ema_dist) > 2.0:
        return {"action": "WAIT", "reason": f"🛑 硬體攔截: 乖離率 {ema_dist:.1f}% 過大，等待回歸均線"}

    # ==========================================
    # 通過防火牆後，才呼叫 AI 進行「質化分析」
    # ==========================================
    rotate_key()
    
    if adx > 50: market_state = "⚠️ 極度過熱"
    elif adx > 25: market_state = "🚀 強烈趨勢"
    else: market_state = "⚖️ 普通震盪"
    
    vol_state = "🔥 爆量" if rvol > 1.2 else "⚖️ 正常"

    score_bull = row['SCORE_BULL']
    score_bear = row['SCORE_BEAR']
    
    prompt = f"""
    你是 V44 頂尖交易員。我們已經通過了嚴格的數學濾網 (RSI 35-65, ADX>20)，現在需要你的【市場解讀能力】。
    
    【市場數據】
    1. 趨勢 (ADX): {adx:.1f} ({market_state})
    2. 動能 (RVOL): {rvol:.2f} ({vol_state})
    3. RSI: {rsi:.1f} (目前處於安全操作區)
    
    【智能評分】
    多頭: {score_bull:.1f} / 空頭: {score_bear:.1f}
    
    【決策任務】
    請綜合判斷是否進場：
    1. **量能確認**：RVOL 是否 > 0.8？如果是「爆量 (>1.2)」，則訊號可信度加倍。
    2. **分數確認**：多空分數差距是否 > 15？
    3. **趨勢確認**：ADX 是否支持目前的 EMA 方向？
    
    回傳 JSON: {{"action": "BUY" | "SELL" | "WAIT", "reason": "簡短分析量能與趨勢結構"}}
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