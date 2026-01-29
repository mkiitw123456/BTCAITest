# C.py - V44: 邏輯對齊版 (Kelly + 趨勢否決 + 動態RR)
from A import get_market_data
from B import ask_ai_for_signal
import time
import requests
import os
import json
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")
load_dotenv(env_path)

# ==========================================
# ⚙️ V44 參數設定
# ==========================================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'
DATA_LIMIT = 2000 
LEVERAGE = 20
RISK_PER_TRADE = 0.02 
INITIAL_BALANCE = 10000
SLEEP_TIME = 0.1 
# ==========================================

balance = INITIAL_BALANCE
position = None 
trade_history = []
loss_details = []

# [V44 新增] 凱利公式 (同步 HTML 邏輯)
def calc_kelly(win_rate, risk_reward):
    w = win_rate
    q = 1 - w
    return (w * risk_reward - q) / risk_reward

def send_discord(msg):
    if not DISCORD_WEBHOOK_URL: return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg, "username": "V44 Logic Commander"})
    except: pass

def run_backtest():
    global balance, position, loss_details

    df = get_market_data(SYMBOL, TIMEFRAME, DATA_LIMIT)
    if df.empty: return

    print(f"\n🚀 V44 邏輯對齊系統啟動 (Lv: {LEVERAGE}x)")
    print(f"📊 邏輯: 凱利濾網 + 趨勢否決 + ADX動態盈虧")
    print("=" * 60)
    
    send_discord(f"🚀 **V44 最終邏輯版** 啟動\n本金: {balance} U")

    last_price = 0

    for i in range(200, len(df)):
        row = df.iloc[i]
        price = row['close']
        last_price = price
        ts = row['timestamp']
        time_str = str(ts)
        
        atr = row['ATR']
        adx = row['ADX']
        ema_50 = row['EMA_50']
        
        # 將 Score (0-100) 轉換為 勝率概率 (0.0-1.0) 用於 Kelly 計算
        # 假設 Score 50 = 勝率 50% (中性)
        bull_prob = row['SCORE_BULL'] / 100.0
        bear_prob = row['SCORE_BEAR'] / 100.0
        
        if position is None:
            # [V44 邏輯 1: 動態盈虧比] 同步 HTML
            if adx > 25:
                tp_mult, sl_mult = 3.0, 1.5
                mode_str = "趨勢"
            else:
                tp_mult, sl_mult = 1.2, 1.0
                mode_str = "震盪"
            
            risk_reward = tp_mult / sl_mult

            # [V44 邏輯 2: 凱利濾網]
            kelly_long = calc_kelly(bull_prob, risk_reward)
            kelly_short = calc_kelly(bear_prob, risk_reward)

            # 決策變數
            signal = "WAIT"
            
            # [V44 邏輯 3: 趨勢否決權 (Trend Veto)]
            # 這是 HTML 中的 "RiskLevel" 邏輯硬體化
            
            # --- 判斷做多 ---
            if kelly_long > 0 and bull_prob > 0.5 and bull_prob > bear_prob:
                # 否決條件: 價格在 EMA 之下 (逆勢)
                if price < ema_50: 
                    # 這裡可以選擇 "WAIT" 或是 "降倉操作"。V43 HTML 是標記 Risky。
                    # 為了安全，自動交易建議直接 WAIT，除非你接受高風險。
                    print(Fore.YELLOW + f"[{time_str}] 🛑 否決做多: 價格 < EMA50 (逆勢)")
                else:
                    signal = "BUY"

            # --- 判斷做空 ---
            elif kelly_short > 0 and bear_prob > 0.5 and bear_prob > bull_prob:
                # 否決條件: 價格在 EMA 之上 (逆勢)
                if price > ema_50:
                    print(Fore.YELLOW + f"[{time_str}] 🛑 否決做空: 價格 > EMA50 (逆勢)")
                else:
                    signal = "SELL"

            # --- 執行進場 ---
            if signal != "WAIT":
                # 二次確認: 問 AI (過濾新聞面或極端K線形態)
                # 注意: 這裡傳入 signal 給 AI 參考
                ai_check = ask_ai_for_signal(row, [])
                ai_action = ai_check.get('action', 'WAIT')
                reason = ai_check.get('reason', 'N/A')

                # 只有當 數學邏輯(Kelly/Veto) 和 AI邏輯 一致時才開單
                if (signal == "BUY" and ai_action == "BUY") or \
                   (signal == "SELL" and ai_action == "SELL"):
                    
                    sl_dist = atr * sl_mult
                    tp_dist = atr * tp_mult
                    
                    # 資金控管
                    sl_percent = sl_dist / price 
                    risk_with_leverage = sl_percent * LEVERAGE
                    if risk_with_leverage == 0: risk_with_leverage = 0.01
                    pos_size = (balance * RISK_PER_TRADE) / risk_with_leverage
                    pos_size = min(pos_size, balance) # 不超過本金
                    
                    p_type = 'LONG' if signal == "BUY" else 'SHORT'
                    sl_price = price - sl_dist if signal == "BUY" else price + sl_dist
                    tp_price = price + tp_dist if signal == "BUY" else price - tp_dist

                    position = {
                        'type': p_type, 
                        'entry': price,
                        'sl': sl_price,
                        'tp': tp_price,
                        'size': pos_size,
                        'reason': f"[K:{kelly_long if p_type=='LONG' else kelly_short:.2f}] {reason}",
                        'time': time_str,
                        'mode': mode_str
                    }
                    
                    color = Fore.GREEN if p_type == 'LONG' else Fore.RED
                    msg = (
                        f"{color}🚀 **開單成功 ({p_type})** [{mode_str}]\n"
                        f"時間: {time_str}\n"
                        f"價格: {price:.2f} | ADX: {adx:.1f}\n"
                        f"止損: {sl_price:.2f} | 止盈: {tp_price:.2f}\n"
                        f"Kelly值: {kelly_long if p_type=='LONG' else kelly_short:.2%}\n"
                        f"AI理由: {reason}"
                    )
                    print(msg)
                    send_discord(msg)
                
                else:
                    # AI 否決了數學信號
                    if ai_action == "WAIT":
                        print(f"[{time_str}] 🤖 AI 否決數學信號: {reason}")

            time.sleep(SLEEP_TIME)

        # --- 持倉管理 (維持 V43 不變) ---
        else:
            p_type = position['type']
            entry = position['entry']
            size = position['size']
            
            # 計算損益
            diff = (price - entry) if p_type == 'LONG' else (entry - price)
            pnl = size * (diff / entry) * LEVERAGE
            
            # 止損觸發
            if (p_type == 'LONG' and price <= position['sl']) or \
               (p_type == 'SHORT' and price >= position['sl']):
                balance += pnl
                msg = f"🛑 **止損出場**\n損益: {pnl:.2f} U"
                print(Fore.RED + msg)
                send_discord(msg)
                loss_details.append({"time": time_str, "pnl": pnl, "reason": position['reason']})
                position = None

            # 止盈觸發
            elif (p_type == 'LONG' and price >= position['tp']) or \
                 (p_type == 'SHORT' and price <= position['tp']):
                balance += pnl
                msg = f"💰 **止盈出場**\n損益: +{pnl:.2f} U"
                print(Fore.GREEN + msg)
                send_discord(msg)
                position = None

    # 結算
    print("="*60)
    print(f"📊 V44 最終結算 | 餘額: {balance:.2f} U")
    try:
        with open('losing_trades_v44.json', 'w', encoding='utf-8') as f:
            json.dump(loss_details, f, indent=4, ensure_ascii=False)
    except: pass

if __name__ == "__main__":
    run_backtest()
