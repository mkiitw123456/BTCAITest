# check_models.py - 查詢可用的 AI 模型名稱
import google.generativeai as genai
import os

# ==========================================
# 設定 API KEY
API_KEY = "你的_GEMINI_API_KEY"
# ==========================================

genai.configure(api_key=API_KEY)

print("正在查詢您的 API Key 可用的模型列表...\n")

try:
    count = 0
    for m in genai.list_models():
        # 我們只關心能「生成內容 (generateContent)」的模型
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ 可用模型: {m.name}")
            count += 1
    
    if count == 0:
        print("❌ 找不到任何可用模型，請檢查 API Key 是否有開通權限。")
    else:
        print(f"\n查詢完成！請將上面其中一個名稱 (例如 models/gemini-1.5-flash) 填入 B.py")

except Exception as e:
    print(f"❌ 查詢失敗: {e}")