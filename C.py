# C.py - 回測模擬 (V43: JSON 輸出 + 資金控管版)
from A import get_market_data
from B import ask_ai_for_signal
import time
import requests
import os
import json # 👈 匯入 json 模組
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)

# 強制指定 .env 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")
load_dotenv(env_path)

# ==========================================
# ⚙️ V43 參數設定
# ==========================================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'
DATA_LIMIT = 2000 

LEVERAGE = 20
SCORE_THRESHOLD = 60 
RISK_PER_TRADE = 0.02 

INITIAL_BALANCE = 10000
SLEEP_TIME = 0.1 
# ==========================================

balance = INITIAL_BALANCE
position = None 
trade_history = []
loss_details = [] # 👈 用來儲存虧損單的詳細資料

def send_discord(msg):
    if not DISCORD_WEBHOOK_URL: return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg, "username": "V43 AI Trader"})
    except: pass

def run_backtest():
    global balance, position, loss_details

    df = get_market_data(SYMBOL, TIMEFRAME, DATA_LIMIT)
    if df.empty: return

    print(f"\n🚀 V43 智能系統啟動 (Lv: {LEVERAGE}x)")
    print(f"📊 設定: 風控 {RISK_PER_TRADE*100}% | 輸出: losing_trades.json")
    print("=" * 60)
    
    send_discord(f"🚀 **V43 回測啟動**\n本金: {balance} U\n策略: RSI安全區(35-65) + ADX過濾")

    last_price = 0

    for i in range(200, len(df)):
        row = df.iloc[i]
        price = row['close']
        last_price = price
        ts = row['timestamp']
        time_str = str(ts)
        
        atr = row['ATR']
        bull_score = row['SCORE_BULL']
        bear_score = row['SCORE_BEAR']
        
        # --- 手上沒單 ---
        if position is None:
            is_bullish = bull_score > SCORE_THRESHOLD and bull_score > bear_score
            is_bearish = bear_score > SCORE_THRESHOLD and bear_score > bull_score
            
            if is_bullish or is_bearish:
                
                print(f"[{time_str}] 🔍 機會: 多{bull_score:.0f} vs 空{bear_score:.0f} -> ", end="")
                
                decision = ask_ai_for_signal(row, [])
                action = decision.get('action', 'WAIT')
                reason = decision.get('reason', 'N/A')

                # === 進場邏輯 (BUY) ===
                if action == "BUY":
                    sl_dist = atr * 1.5
                    tp_dist = atr * 2.0
                    
                    sl_percent = sl_dist / price 
                    risk_with_leverage = sl_percent * LEVERAGE
                    if risk_with_leverage == 0: risk_with_leverage = 0.01
                    
                    pos_size = (balance * RISK_PER_TRADE) / risk_with_leverage
                    pos_size = min(pos_size, balance)
                    
                    position = {
                        'type': 'LONG', 
                        'entry': price,
                        'sl': price - sl_dist,
                        'tp': price + tp_dist,
                        'size': pos_size,
                        'reason': reason, # 👈 記住原因，之後輸出用
                        'time': time_str
                    }
                    
                    msg = (
                        f"📈 **AI 開多 (LONG)**\n"
                        f"🕒 時間: {time_str}\n"
                        f"💵 進場價: {price:.2f}\n"
                        f"💰 倉位大小: {pos_size:.2f} U\n"
                        f"🛡️ 止損: {price-sl_dist:.2f}\n"
                        f"🎯 止盈: {price+tp_dist:.2f}\n"
                        f"📝 原因: {reason}"
                    )
                    print(Fore.GREEN + f"\n{msg}")
                    send_discord(msg)

                # === 進場邏輯 (SELL) ===
                elif action == "SELL":
                    sl_dist = atr * 1.5
                    tp_dist = atr * 2.0
                    
                    sl_percent = sl_dist / price
                    risk_with_leverage = sl_percent * LEVERAGE
                    if risk_with_leverage == 0: risk_with_leverage = 0.01
                    
                    pos_size = (balance * RISK_PER_TRADE) / risk_with_leverage
                    pos_size = min(pos_size, balance)
                    
                    position = {
                        'type': 'SHORT', 
                        'entry': price,
                        'sl': price + sl_dist,
                        'tp': price - tp_dist,
                        'size': pos_size,
                        'reason': reason,
                        'time': time_str
                    }
                    
                    msg = (
                        f"📉 **AI 開空 (SHORT)**\n"
                        f"🕒 時間: {time_str}\n"
                        f"💵 進場價: {price:.2f}\n"
                        f"💰 倉位大小: {pos_size:.2f} U\n"
                        f"🛡️ 止損: {price+sl_dist:.2f}\n"
                        f"🎯 止盈: {price-tp_dist:.2f}\n"
                        f"📝 原因: {reason}"
                    )
                    print(Fore.RED + f"\n{msg}")
                    send_discord(msg)
                else:
                    print(Fore.YELLOW + "AI 否決 (Wait)")
                
                time.sleep(SLEEP_TIME)

        # --- 手上持倉 ---
        else:
            p_type = position['type']
            entry_price = position['entry']
            pos_size = position['size']
            
            if p_type == 'LONG': raw_pnl = (price - entry_price) / entry_price
            else: raw_pnl = (entry_price - price) / entry_price
            
            real_pnl = pos_size * raw_pnl * LEVERAGE
            
            # 🛑 止損 (LOSS)
            if (p_type == 'LONG' and price <= position['sl']) or \
               (p_type == 'SHORT' and price >= position['sl']):
                balance += real_pnl
                
                msg = f"🛑 **{p_type} 止損**\n時間: {time_str}\n虧損: {real_pnl:.2f} U"
                print(Fore.RED + msg)
                send_discord(msg)
                trade_history.append('LOSS')
                
                # 🔥 記錄虧損單到列表
                loss_record = {
                    "time": time_str,
                    "type": p_type,
                    "entry_price": entry_price,
                    "exit_price": price,
                    "loss_amount": real_pnl,
                    "reason": position['reason']
                }
                loss_details.append(loss_record)
                
                position = None

            # 💰 止盈 (WIN)
            elif (p_type == 'LONG' and price >= position['tp']) or \
                 (p_type == 'SHORT' and price <= position['tp']):
                balance += real_pnl
                msg = f"💰 **{p_type} 止盈**\n時間: {time_str}\n獲利: +{real_pnl:.2f} U"
                print(Fore.GREEN + msg)
                send_discord(msg)
                trade_history.append('WIN')
                position = None

    if position:
        p_type = position['type']
        entry_price = position['entry']
        pos_size = position['size']
        if p_type == 'LONG': raw_pnl = (last_price - entry_price) / entry_price
        else: raw_pnl = (entry_price - last_price) / entry_price
        
        final_pnl = pos_size * raw_pnl * LEVERAGE
        balance += final_pnl
        send_discord(f"🏁 **強制平倉**\n時間: {time_str}\n結算損益: {final_pnl:.2f} U")

    # 🔥 輸出 JSON 檔案
    print("="*60)
    print(f"📊 V43 結算 | 淨利: {balance - INITIAL_BALANCE:.2f} U")
    
    try:
        with open('losing_trades.json', 'w', encoding='utf-8') as f:
            json.dump(loss_details, f, indent=4, ensure_ascii=False)
        print(Fore.CYAN + f"📁 已將 {len(loss_details)} 筆虧損紀錄寫入 'losing_trades.json'")
    except Exception as e:
        print(Fore.RED + f"❌ JSON 寫入失敗: {e}")

    print("="*60)
    send_discord(f"📊 **回測結束**\n最終餘額: {balance:.2f}")

if __name__ == "__main__":
    run_backtest()