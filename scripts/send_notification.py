import discord
import os
import sys
from discord.ext import commands

def main():
    # 從環境變數獲取 Token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ 錯誤：DISCORD_TOKEN 環境變數未設定")
        sys.exit(1)
    
    # 設定意圖
    intents = discord.Intents.default()
    intents.message_content = True
    
    # 創建 Bot 實例
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"✅ 已登入為 {bot.user}")
        
        print("\n🔄 正在檢查 Bot 加入的伺服器...")
        for guild in bot.guilds:
            print(f"📋 伺服器: {guild.name} (ID: {guild.id})")
            
            print("   📁 頻道列表:")
            for channel in guild.text_channels:
                # 檢查權限
                permissions = channel.permissions_for(guild.me)
                can_send = permissions.send_messages
                can_view = permissions.view_channel
                
                status = "✅" if can_send and can_view else "❌"
                print(f"   {status} #{channel.name} (ID: {channel.id})")
                print(f"       瀏覽權限: {can_view}, 發訊權限: {can_send}")
        
        print("\n🔍 嘗試獲取特定頻道...")
        # 使用正確的頻道 ID（從輸出中複製）
        target_channel_id = 1413105016750870631  # 這是 #一般 頻道的 ID
        channel = bot.get_channel(target_channel_id)
        
        if channel:
            print(f"✅ 找到頻道: #{channel.name}")
            
            # 檢查權限
            guild = channel.guild
            permissions = channel.permissions_for(guild.me)
            
            if not permissions.view_channel:
                print("❌ Bot 沒有查看此頻道的權限")
            elif not permissions.send_messages:
                print("❌ Bot 沒有在此頻道發訊息的權限")
            else:
                print("✅ 權限檢查通過，準備發送訊息...")
                
                # 根據命令行參數發送不同訊息
                status = sys.argv[1] if len(sys.argv) > 1 else "unknown"
                
                if status == "success":
                    message = "🎉 CI/CD 測試成功！所有檢查通過。"
                elif status == "failure":
                    message = "❌ CI/CD 測試失敗！請檢查錯誤。"
                else:
                    message = "🤖 CI/CD 流程執行完成。"
                
                try:
                    await channel.send(message)
                    print(f"✅ 已發送訊息：{message}")
                except Exception as e:
                    print(f"❌ 發送訊息時出錯：{e}")
        else:
            print(f"❌ 無法找到頻道 ID: {target_channel_id}")
        
        await bot.close()
    
    # 運行 Bot
    try:
        bot.run(token)
    except Exception as e:
        print(f"❌ Bot 運行時出錯：{e}")

if __name__ == "__main__":
    main()