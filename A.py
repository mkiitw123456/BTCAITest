# A.py - 數據工廠 (強制修復 EMA/VWAP 欄位問題)
import ccxt
import pandas as pd
import pandas_ta as ta

def get_market_data(symbol='BTC/USDT', timeframe='15m', limit=1000):
    print(f"🔄 V39 系統: 下載 {symbol} 數據 (含 ADX 動態權重)...")
    
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # 🔥【修復 1】去除重複時間戳，防止索引衝突
        df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
        
        # 設定時間索引
        df.set_index('timestamp', inplace=True)
        
        # --- 1. 基礎指標 ---
        df['RSI'] = df.ta.rsi(length=14)
        
        # MACD (處理欄位)
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        # 找出柱狀圖 (Hist) 欄位
        if isinstance(macd, pd.DataFrame):
            hist_col = [c for c in macd.columns if 'h' in c or 'HIST' in c.upper()][0]
            df['MACD_HIST'] = macd[hist_col]
        else:
            df['MACD_HIST'] = macd

        # 🔥【修復 2】EMA 200 強制轉成單一欄位
        ema_result = df.ta.ema(length=200)
        if isinstance(ema_result, pd.DataFrame):
            # 如果回傳是表格，只取第一欄
            df['EMA_200'] = ema_result.iloc[:, 0]
        else:
            # 如果是單行數據，直接用
            df['EMA_200'] = ema_result
        
        # 🔥【修復 3】VWAP 強制轉成單一欄位
        vwap_result = df.ta.vwap()
        if isinstance(vwap_result, pd.DataFrame):
             df['VWAP'] = vwap_result.iloc[:, 0] 
        else:
             df['VWAP'] = vwap_result

        # ATR
        atr_res = df.ta.atr(length=14)
        if isinstance(atr_res, pd.DataFrame):
            df['ATR'] = atr_res.iloc[:, 0]
        else:
            df['ATR'] = atr_res

        # ADX 趨勢強度
        adx_df = df.ta.adx(length=14)
        if isinstance(adx_df, pd.DataFrame):
            # ADX 通常回傳 3 欄 (ADX, DMP, DMN)，我們只要 ADX
            adx_col = [c for c in adx_df.columns if c.startswith('ADX')][0]
            df['ADX'] = adx_df[adx_col]
        else:
            df['ADX'] = adx_df

        # --- 2. V39 智能分數計算 (Smart Score) ---
        
        # 定義訊號 (1=看多, 0=看空)
        s_rsi_b = (df['RSI'] < 45).astype(int)
        s_rsi_s = (df['RSI'] > 55).astype(int)
        
        s_ema_b = (df['close'] > df['EMA_200']).astype(int)
        s_ema_s = (df['close'] < df['EMA_200']).astype(int)
        
        s_macd_b = (df['MACD_HIST'] > 0).astype(int)
        s_macd_s = (df['MACD_HIST'] < 0).astype(int)
        
        s_vwap_b = (df['close'] > df['VWAP']).astype(int)
        s_vwap_s = (df['close'] < df['VWAP']).astype(int)

        # 動態權重分配
        w_trend = df['ADX'].apply(lambda x: 2.0 if x > 25 else 0.5)
        w_osc = df['ADX'].apply(lambda x: 0.5 if x > 25 else 2.0)
        w_base = 1.0

        # 計算總分
        score_bull = (s_rsi_b * w_osc) + (s_ema_b * w_trend) + (s_macd_b * w_trend) + (s_vwap_b * w_base)
        score_bear = (s_rsi_s * w_osc) + (s_ema_s * w_trend) + (s_macd_s * w_trend) + (s_vwap_s * w_base)
        
        total_weight = w_osc + w_trend + w_trend + w_base
        
        df['SCORE_BULL'] = (score_bull / total_weight) * 100
        df['SCORE_BEAR'] = (score_bear / total_weight) * 100

        # 復原索引
        df.reset_index(inplace=True)
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        return df

    except Exception as e:
        import traceback
        print(f"❌ 數據抓取失敗: {e}")
        # traceback.print_exc() # 如果需要詳細錯誤可以打開這行
        return pd.DataFrame()