# A.py (V42: 乖離率與過熱保護版)
import ccxt
import pandas as pd
import pandas_ta as ta

def get_market_data(symbol='BTC/USDT', timeframe='15m', limit=2000):
    print(f"🔄 V42 系統: 下載 {symbol} 數據 (含 EMA乖離率 + 過熱偵測)...")
    
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
        df.set_index('timestamp', inplace=True)
        
        # --- 指標計算 ---
        df['RSI'] = df.ta.rsi(length=14)
        
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if isinstance(macd, pd.DataFrame):
            hist_col = [c for c in macd.columns if 'h' in c or 'HIST' in c.upper()][0]
            df['MACD_HIST'] = macd[hist_col]
        else:
            df['MACD_HIST'] = macd

        # EMA 200
        ema_result = df.ta.ema(length=200)
        df['EMA_200'] = ema_result.iloc[:, 0] if isinstance(ema_result, pd.DataFrame) else ema_result
        
        # 🔥【V42 新增】EMA 乖離率 (Distance from EMA)
        # 計算公式: (收盤價 - EMA200) / EMA200 * 100
        # 正值代表價格在均線上 X%，負值代表在均線下 X%
        df['EMA_DIST'] = (df['close'] - df['EMA_200']) / df['EMA_200'] * 100

        # VWAP & ATR
        vwap_result = df.ta.vwap()
        df['VWAP'] = vwap_result.iloc[:, 0] if isinstance(vwap_result, pd.DataFrame) else vwap_result
        atr_res = df.ta.atr(length=14)
        df['ATR'] = atr_res.iloc[:, 0] if isinstance(atr_res, pd.DataFrame) else atr_res

        # ADX
        adx_df = df.ta.adx(length=14)
        if isinstance(adx_df, pd.DataFrame):
            adx_col = [c for c in adx_df.columns if c.startswith('ADX')][0]
            df['ADX'] = adx_df[adx_col]
        else:
            df['ADX'] = adx_df

        # RVOL (油量)
        vol_sma = df.ta.sma(close=df['volume'], length=20)
        vol_sma = vol_sma.iloc[:, 0] if isinstance(vol_sma, pd.DataFrame) else vol_sma
        df['RVOL'] = df['volume'] / (vol_sma + 0.001)

        # --- V39 智能分數 (保持不變) ---
        s_rsi_b = (df['RSI'] < 45).astype(int)
        s_rsi_s = (df['RSI'] > 55).astype(int)
        s_ema_b = (df['close'] > df['EMA_200']).astype(int)
        s_ema_s = (df['close'] < df['EMA_200']).astype(int)
        s_macd_b = (df['MACD_HIST'] > 0).astype(int)
        s_macd_s = (df['MACD_HIST'] < 0).astype(int)
        s_vwap_b = (df['close'] > df['VWAP']).astype(int)
        s_vwap_s = (df['close'] < df['VWAP']).astype(int)

        w_trend = df['ADX'].apply(lambda x: 2.0 if x > 25 else 0.5)
        w_osc = df['ADX'].apply(lambda x: 0.5 if x > 25 else 2.0)
        w_base = 1.0

        score_bull = (s_rsi_b * w_osc) + (s_ema_b * w_trend) + (s_macd_b * w_trend) + (s_vwap_b * w_base)
        score_bear = (s_rsi_s * w_osc) + (s_ema_s * w_trend) + (s_macd_s * w_trend) + (s_vwap_s * w_base)
        
        total_weight = w_osc + w_trend + w_trend + w_base
        
        df['SCORE_BULL'] = (score_bull / total_weight) * 100
        df['SCORE_BEAR'] = (score_bear / total_weight) * 100

        df.reset_index(inplace=True)
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        return df

    except Exception as e:
        print(f"❌ 數據抓取失敗: {e}")
        return pd.DataFrame()