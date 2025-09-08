import os
import discord
from discord.ext import commands
from dotenv import load_dotenv  # 新增這行

# 載入環境變數
load_dotenv('.env') 

print("當前工作目錄:", os.getcwd())
print("環境變數 DISCORD_TOKEN:", os.getenv("DISCORD_TOKEN"))

# 從環境變數讀取 Token
TOKEN = os.getenv("DISCORD_TOKEN")
print(f"DISCORD_TOKEN: {TOKEN}")

if TOKEN is None:
    print("❌ 錯誤：無法讀取 DISCORD_TOKEN")
    # 嘗試直接讀取檔案
    try:
        with open('.env', 'r') as f:
            content = f.read()
            print(".env 檔案內容:")
            print(content)
    except Exception as e:
        print(f"讀取 .env 檔案失敗: {e}")
    exit(1)

# 設定意圖
intents = discord.Intents.default()
intents.message_content = True

# 建立 Bot 物件，設定前綴詞
bot = commands.Bot(command_prefix="!", intents=intents)

# 當 Bot 上線時觸發
@bot.event
async def on_ready():
    print(f"已登入為 {bot.user}")

# 當有人輸入 !hello 時，Bot 會回覆
@bot.command()
async def hello(ctx):
    await ctx.send("哈囉！我是你的第一個 Discord Bot 🤖")

# 啟動 Bot
bot.run(TOKEN)
