# B.py - AI 大腦 (V43: 邏輯校準版)
import google.generativeai as genai
import json
import warnings
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
    # 🔥 V43 核心防火牆 (同步 HTML 邏輯)
    # ==========================================
    
    rsi = row['RSI']
    adx = row['ADX']
    rvol = row['RVOL']
    ema_dist = row['EMA_DIST']
    
    # 1. ADX 濾網 (同步 HTML: < 20 為死魚盤)
    if adx < 20:
        return {"action": "WAIT", "reason": f"🛑 V43 攔截: ADX {adx:.1f} < 20，強制盤整觀望"}
    
    # 2. 量能底線 (保留 0.8 防止虛假波動)
    if rvol < 0.8:
        return {"action": "WAIT", "reason": f"🛑 V43 攔截: RVOL {rvol:.2f} 縮量，動能不足"}
    
    # 3. [修正] 乖離率防呆 (同步 HTML: 1.5% 警戒線)
    # HTML 邏輯: if bias > 1.5 (15m) -> Wait
    if abs(ema_dist) > 1.5: 
        status = "超買" if ema_dist > 0 else "超賣"
        return {"action": "WAIT", "reason": f"🛑 V43 攔截: 乖離率 {ema_dist:.1f}% ({status})，禁止追單"}

    # ==========================================
    # 交給 AI 進行最終確認
    # ==========================================
    rotate_key()
    
    if adx > 50: market_state = "⚠️ 極度強勢 (注意反轉)"
    else: market_state = "🚀 健康趨勢"
    
    vol_state = "🔥 爆量" if rvol > 1.2 else "📈 放量"

    # RSI 狀態描述
    if rsi > 70: rsi_state = "🔥 超買鈍化區"
    elif rsi < 30: rsi_state = "❄️ 超賣鈍化區"
    else: rsi_state = "✅ 安全操作區"

    score_bull = row['SCORE_BULL']
    score_bear = row['SCORE_BEAR']
    
    prompt = f"""
    你是 V43 戰情室的 AI 指揮官。所有硬體指標 (ADX, Bias, RVOL) 都已通過檢查。
    現在請根據 Smart Score 和 RSI 進行最後的趨勢確認。
    
    【市場數據】
    1. 趨勢 (ADX): {adx:.1f} ({market_state})
    2. 動能 (RVOL): {rvol:.2f} ({vol_state})
    3. RSI: {rsi:.1f} ({rsi_state})
    4. 乖離率 (EMA50): {ema_dist:.2f}% (已在安全範圍內)
    
    【智能評分】
    多頭: {score_bull:.1f} / 空頭: {score_bear:.1f}
    
    【V43 決策邏輯】
    1. **順勢原則**：多頭分數高做多，空頭分數高做空。差距需 > 10。
    2. **指標共振**：RSI 與分數方向必須一致。
    3. **回傳格式**：嚴格使用 JSON。
    
    回傳 JSON: {{"action": "BUY" | "SELL" | "WAIT", "reason": "簡短原因"}}
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
