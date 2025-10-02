import os
os.environ["DISCORD_INSTANCE_NO_VOICE"] = "true"
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import requests
import json
from datetime import datetime, timedelta
import random
import asyncio
import schedule
import time
import threading
from flask import Flask
from threading import Thread

# 環境變數載入邏輯（兼容本地和 Render）
if os.path.exists('.env'):
    load_dotenv('.env')
else:
    print("ℹ️  在 Render 環境中運行，使用系統環境變數")

# 從環境變數讀取 Token
TOKEN = os.getenv("DISCORD_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
GITHUB_OWNER = "alpachen"
GITHUB_REPO = "discord-bot-devops"
CHANGELOG_CHANNEL_ID = os.getenv("CHANGELOG_CHANNEL_ID")
CONTROL_PANEL_CHANNEL_ID = os.getenv("CONTROL_PANEL_CHANNEL_ID")  # 新增：控制面板頻道ID

# 可調整的檢查頻率（單位：天）
CHECK_INTERVAL_DAYS = 7

# 設定意圖
intents = discord.Intents.default()
intents.message_content = True

# 建立 Bot 物件，設定前綴詞
bot = commands.Bot(command_prefix="!", intents=intents)

# 全局變數用於排程觸發
weekly_check_event = asyncio.Event()

# 記錄最後檢查時間（用於手動檢查功能）
last_check_time = datetime.now() - timedelta(days=CHECK_INTERVAL_DAYS)


app = Flask('')

@app.route("/health")
def health():
    return "OK", 200

@app.route('/')
def home():
    return "機器人運行中"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# 啟動機器人前先啟動 Flask 服務
keep_alive()

# 記錄控制面板訊息 ID（用於重啟時更新）
control_panel_message_id = None

class ControlPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📊 狀態監控", style=discord.ButtonStyle.primary, custom_id="status_monitor")
    async def status_monitor(self, interaction: discord.Interaction, button: discord.ui.Button):
        """狀態監控面板"""
        embed = discord.Embed(
            title="📊 DevOps 狀態監控",
            description="即時系統狀態與健康度檢查",
            color=0x3498DB
        )
        
        # 獲取即時狀態
        build_status = get_latest_build_status()
        commit_info = get_latest_commit()
        
        # 簡化狀態顯示
        embed.add_field(
            name="🔄 CI/CD 狀態",
            value="點擊下方按鈕查看詳細狀態",
            inline=False
        )
        
        embed.add_field(
            name="📝 最新提交",
            value="查看最近程式碼變更",
            inline=False
        )
        
        view = StatusMonitorView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="📝 變更管理", style=discord.ButtonStyle.success, custom_id="change_management")
    async def change_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        """變更管理面板"""
        embed = discord.Embed(
            title="📝 變更管理控制台",
            description="追蹤程式碼變更與版本發布",
            color=0x27AE60
        )
        
        embed.add_field(
            name="🔄 更新檢查",
            value="立即檢查最新合併的 PR",
            inline=True
        )
        
        embed.add_field(
            name="📈 近期活動", 
            value="查看最近開發進度",
            inline=True
        )
        
        view = ChangeManagementView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="⚙️ 排程管理", style=discord.ButtonStyle.secondary, custom_id="schedule_management")
    async def schedule_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        """排程管理面板"""
        embed = discord.Embed(
            title="⚙️ 排程任務管理",
            description="自動化任務與排程設定",
            color=0xF39C12
        )
        
        next_check = get_next_monday()
        
        embed.add_field(
            name="⏰ 下次檢查",
            value=f"{(next_check + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')} (台灣時間)",
            inline=True
        )
        
        embed.add_field(
            name="📊 排程狀態",
            value="✅ 運行中" if CHANGELOG_CHANNEL_ID else "❌ 未啟用",
            inline=True
        )
        
        view = ScheduleManagementView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="🔧 系統資訊", style=discord.ButtonStyle.gray, custom_id="system_info")
    async def system_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """系統資訊面板"""
        embed = discord.Embed(
            title="🔧 系統資訊與支援",
            description="環境設定與技術資源",
            color=0x95A5A6
        )
        
        embed.add_field(
            name="🌐 運行環境",
            value="Render" if not os.path.exists('.env') else "本地",
            inline=True
        )
        
        embed.add_field(
            name="🤖 Bot 狀態",
            value="✅ 在線",
            inline=True
        )
        
        view = SystemInfoView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# 狀態監控子面板
class StatusMonitorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="🚀 Pipeline 狀態", style=discord.ButtonStyle.primary)
    async def pipeline_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        status_message = get_workflow_status()
        await interaction.followup.send(status_message, ephemeral=True)
    
    @discord.ui.button(label="📦 建置狀態", style=discord.ButtonStyle.primary)
    async def build_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        status_message = get_latest_build_status()
        await interaction.followup.send(status_message, ephemeral=True)
    
    @discord.ui.button(label="📝 最新提交", style=discord.ButtonStyle.primary)
    async def last_commit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        commit_info = get_latest_commit()
        await interaction.followup.send(commit_info, ephemeral=True)
    
    @discord.ui.button(label="📋 Workflow 列表", style=discord.ButtonStyle.secondary)
    async def workflow_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        workflow_list = get_workflow_list()
        await interaction.followup.send(workflow_list, ephemeral=True)
    
    @discord.ui.button(label="🔙 返回主選單", style=discord.ButtonStyle.gray)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = create_main_embed()
        view = ControlPanelView()
        await interaction.response.edit_message(embed=embed, view=view)

# 變更管理子面板
class ChangeManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="🔄 立即檢查", style=discord.ButtonStyle.success)
    async def force_check(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        global last_check_time
        
        since_date = last_check_time.strftime("%Y-%m-%d")
        prs, error = get_merged_prs_since(since_date)
        
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        
        if prs:
            changelog_content = generate_changelog(prs)
            await interaction.followup.send(changelog_content, ephemeral=True)
        else:
            await interaction.followup.send("📭 沒有找到新的 PR", ephemeral=True)
        
        last_check_time = datetime.now()
    
    @discord.ui.button(label="📊 近期更新", style=discord.ButtonStyle.primary)
    async def recent_changelog(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        since_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        prs, error = get_merged_prs_since(since_date)
        
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        
        if not prs:
            await interaction.followup.send("📭 最近 7 天沒有合併的 PR", ephemeral=True)
            return
        
        detailed_changelog = f"🚀 **最近 7 天更新日誌**\n\n"
        for pr in prs:
            pr_number = pr['number']
            pr_title = pr['title']
            pr_url = pr['html_url']
            merged_at = pr['pull_request']['merged_at']
            author = pr['user']['login']
            
            merged_time = datetime.fromisoformat(merged_at.replace('Z', '+00:00'))
            formatted_time = merged_time.strftime("%m/%d %H:%M")
            
            detailed_changelog += f"**#{pr_number}** - {pr_title}\n"
            detailed_changelog += f"⏰ {formatted_time} | 👤 {author}\n"
            detailed_changelog += f"🔗 [查看PR]({pr_url})\n\n"
        
        await interaction.followup.send(detailed_changelog, ephemeral=True)
    
    @discord.ui.button(label="🔙 返回主選單", style=discord.ButtonStyle.gray)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = create_main_embed()
        view = ControlPanelView()
        await interaction.response.edit_message(embed=embed, view=view)

# 排程管理子面板
class ScheduleManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="⏰ 排程資訊", style=discord.ButtonStyle.primary)
    async def schedule_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        next_check = get_next_monday()
        
        message = (
            f"⏰ **排程設定**\n"
            f"• 檢查時間: 每週一 09:00 (台灣時間)\n"
            f"• 下次檢查: {next_check.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"• 台灣時間: {(next_check + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')}\n"
            f"• 排程狀態: {'✅ 運行中' if CHANGELOG_CHANNEL_ID else '❌ 未啟用'}\n"
            f"• 通知頻道: {f'<#{CHANGELOG_CHANNEL_ID}>' if CHANGELOG_CHANNEL_ID else '未設定'}"
        )
        
        await interaction.response.send_message(message, ephemeral=True)
    
    @discord.ui.button(label="🧪 測試排程", style=discord.ButtonStyle.success)
    async def test_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await execute_scheduled_check()
        await interaction.followup.send("✅ 排程檢查完成", ephemeral=True)
    
    @discord.ui.button(label="🔙 返回主選單", style=discord.ButtonStyle.gray)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = create_main_embed()
        view = ControlPanelView()
        await interaction.response.edit_message(embed=embed, view=view)

# 系統資訊子面板
class SystemInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="⚙️ 系統設定", style=discord.ButtonStyle.primary)
    async def system_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        next_manual_check = last_check_time + timedelta(days=CHECK_INTERVAL_DAYS)
        next_schedule_check = get_next_monday()
        
        message = (
            f"⚙️ **當前設定**\n"
            f"**手動檢查系統**\n"
            f"• 檢查頻率: 每 {CHECK_INTERVAL_DAYS} 天\n"
            f"• 最後檢查: {last_check_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"• 下次檢查: {next_manual_check.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"**排程檢查系統**\n"
            f"• 檢查時間: 每週一 09:00 (台灣時間)\n"
            f"• 下次檢查: {next_schedule_check.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"• 台灣時間: {(next_schedule_check + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')}\n\n"
            f"• 自動發送: {'✅ 已啟用' if CHANGELOG_CHANNEL_ID else '❌ 未啟用'}"
        )
        
        await interaction.response.send_message(message, ephemeral=True)
    
    @discord.ui.button(label="🔧 技術支援", style=discord.ButtonStyle.secondary)
    async def tech_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        support_message = (
            "**🔧 技術支援**\n\n"
            "**相關連結**\n"
            "📖 [教學文檔](https://github.com/alpachen/discord-bot-devops)\n"
            "🐛 [問題回報](https://github.com/alpachen/discord-bot-devops/issues)\n"
            "💻 [原始碼](https://github.com/alpachen/discord-bot-devops)\n\n"
            "💡 需要協助？請聯繫管理員或查看文檔。"
        )
        await interaction.response.send_message(support_message, ephemeral=True)
    
    @discord.ui.button(label="🔙 返回主選單", style=discord.ButtonStyle.gray)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = create_main_embed()
        view = ControlPanelView()
        await interaction.response.edit_message(embed=embed, view=view)

def create_main_embed():
    """創建主控制面板的 Embed"""
    embed = discord.Embed(
        title="🤖 DevOps 監控控制台",
        description="專案狀態監控與自動化管理",
        color=0x2C3E50,
        timestamp=datetime.utcnow()
    )
    
    # 添加狀態概覽
    embed.add_field(
        name="📊 即時狀態概覽",
        value=(
            "• GitHub Actions: ✅ 正常\n"
            "• CI/CD Pipeline: 🔄 監控中\n"
            "• 程式碼倉庫: ✅ 正常\n"
            "• 自動化排程: ✅ 運行中"
        ),
        inline=False
    )
    
    # 添加功能模組說明
    embed.add_field(
        name="🔧 功能模組",
        value=(
            "**📊 狀態監控** - Pipeline、建置狀態、Commit 資訊\n"
            "**📝 變更管理** - 更新日誌、PR 追蹤\n"
            "**⚙️ 排程管理** - 自動化任務、排程設定\n"
            "**🔧 系統資訊** - 環境狀態、技術支援"
        ),
        inline=False
    )
    
    embed.set_footer(text="點擊下方按鈕開始使用")
    
    return embed

async def send_control_panel():
    """發送控制面板到指定頻道"""
    global control_panel_message_id
    
    if not CONTROL_PANEL_CHANNEL_ID:
        print("❌ CONTROL_PANEL_CHANNEL_ID 未設定，無法自動發送控制面板")
        return
    
    try:
        channel = bot.get_channel(int(CONTROL_PANEL_CHANNEL_ID))
        if not channel:
            print(f"❌ 找不到頻道: {CONTROL_PANEL_CHANNEL_ID}")
            return
        
        # 檢查是否已經有控制面板訊息
        if control_panel_message_id:
            try:
                existing_message = await channel.fetch_message(control_panel_message_id)
                embed = create_main_embed()
                view = ControlPanelView()
                await existing_message.edit(embed=embed, view=view)
                print("✅ 已更新現有控制面板")
                return
            except discord.NotFound:
                print("📝 現有控制面板訊息不存在，將發送新的")
            except Exception as e:
                print(f"❌ 更新控制面板時出錯: {e}")
        
        # 發送新的控制面板
        embed = create_main_embed()
        view = ControlPanelView()
        
        message = await channel.send(embed=embed, view=view)
        control_panel_message_id = message.id
        
        print(f"✅ 已發送控制面板到頻道 {CONTROL_PANEL_CHANNEL_ID}")
        
    except Exception as e:
        print(f"❌ 發送控制面板時出錯: {e}")


def run_scheduler():
    """在背景執行排程（Render 環境優化版）"""
    # 清除所有現有排程
    schedule.clear()
    
    # 設定排程：每週一上午 9:00 執行（台灣時間 UTC+8）
    # Render 伺服器通常是 UTC 時間，所以換算成 UTC 時間
    schedule.every().monday.at("01:00").do(trigger_weekly_check)  # UTC 時間 01:00 = 台灣時間 09:00
    
    # 也可以添加測試排程（每小時執行一次，用於測試）
    schedule.every().hour.do(trigger_test_check)
    
    print("⏰ 排程器設定完成：每週一 01:00 UTC (09:00 UTC+8) 自動檢查")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分鐘檢查一次排程

def trigger_weekly_check():
    """觸發每周檢查（由排程器調用）"""
    print("🔔 排程器觸發每周檢查")
    weekly_check_event.set()

def trigger_test_check():
    """測試用排程（每小時執行）"""
    print("🧪 每小時測試排程執行中...")

async def execute_scheduled_check():
    """執行排程的每周檢查"""
    print(f"🔍 執行排程每周檢查...")
    
    # 檢查上週的 PR（上週一到現在）
    last_monday = datetime.utcnow() - timedelta(days=7)  # 使用 UTC 時間
    since_date = last_monday.strftime("%Y-%m-%d")
    
    prs, error = get_merged_prs_since(since_date)
    
    if error:
        error_msg = f"❌ 自動檢查失敗: {error}"
        print(error_msg)
        if CHANGELOG_CHANNEL_ID:
            await send_changelog_to_channel(error_msg)
        return
    
    if prs:
        print(f"📝 發現 {len(prs)} 個上週合併的 PR")
        
        # 計算時間範圍
        start_date = last_monday.strftime("%Y-%m-%d")
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        
        changelog_content = f"📊 **每周更新報告 ({start_date} ~ {end_date})**\n\n"
        changelog_content += f"本周共合併了 **{len(prs)}** 個 PR\n\n"
        
        for pr in prs:
            pr_number = pr['number']
            pr_title = pr['title']
            pr_url = pr['html_url']
            author = pr['user']['login']
            merged_at = pr['pull_request']['merged_at']
            
            # 格式化時間
            merged_time = datetime.fromisoformat(merged_at.replace('Z', '+00:00'))
            formatted_time = merged_time.strftime("%m/%d")
            
            changelog_content += f"• [#{pr_number}]({pr_url}) {pr_title}\n"
            changelog_content += f"  👤 {author} | 📅 {formatted_time}\n\n"
        
        if CHANGELOG_CHANNEL_ID:
            success = await send_changelog_to_channel(changelog_content)
            if success:
                print("✅ 排程每周報告發送成功")
            else:
                print("❌ 排程每周報告發送失敗")
    else:
        print("📭 上週沒有新合併的 PR")
        if CHANGELOG_CHANNEL_ID:
            await send_changelog_to_channel("📭 上週沒有新合併的 PR")

@tasks.loop(seconds=30)
async def check_scheduled_events():
    """檢查排程事件"""
    if weekly_check_event.is_set():
        weekly_check_event.clear()
        await execute_scheduled_check()

async def send_changelog_to_channel(content):
    """發送 changelog 到指定頻道"""
    try:
        if not CHANGELOG_CHANNEL_ID:
            print("❌ CHANGELOG_CHANNEL_ID 未設定")
            return False
        
        channel = bot.get_channel(int(CHANGELOG_CHANNEL_ID))
        if channel:
            # 如果內容太長，分割訊息
            if len(content) > 2000:
                parts = [content[i:i+2000] for i in range(0, len(content), 2000)]
                for part in parts:
                    await channel.send(part)
            else:
                await channel.send(content)
            print(f"✅ 已發送訊息到頻道 {CHANGELOG_CHANNEL_ID}")
            return True
        else:
            print(f"❌ 找不到頻道: {CHANGELOG_CHANNEL_ID}")
            return False
    except Exception as e:
        print(f"❌ 發送訊息失敗: {e}")
        return False

@bot.event
async def on_ready():
    print(f"✅ 已登入為 {bot.user}")
    print(f"🤖 Bot 已準備好接收指令！")
    print(f"🌐 運行環境: {'Render' if not os.path.exists('.env') else '本地'}")
    
    # 計算下次排程檢查時間
    next_check = get_next_monday()
    print(f"⏰ 下次排程檢查時間: {next_check.strftime('%Y-%m-%d %H:%M UTC')}")
    
    if CHANGELOG_CHANNEL_ID:
        print(f"📊 排程檢查已啟用，頻道: {CHANGELOG_CHANNEL_ID}")
        
        # 啟動排程器線程
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # 啟動事件檢查任務
        check_scheduled_events.start()
        
        print("✅ 排程系統已啟動")
    else:
        print("ℹ️  排程檢查未啟用（未設定 CHANGELOG_CHANNEL_ID）")

def get_next_monday():
    """獲取下週一的日期（UTC 時間）"""
    today = datetime.utcnow()  # 使用 UTC 時間
    days_ahead = 0 - today.weekday()  # 0 = Monday
    if days_ahead <= 0:  # 如果今天已經過了週一
        days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    # 設定為下週一的 01:00 UTC
    return next_monday.replace(hour=1, minute=0, second=0, microsecond=0)

# 添加排程管理指令
@bot.command()
async def schedule_info(ctx):
    """查看當前排程設定"""
    next_check = get_next_monday()
    
    message = (
        f"⏰ **排程設定**\n"
        f"• 檢查時間: 每週一 09:00 (台灣時間)\n"
        f"• 下次檢查: {next_check.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"• 台灣時間: {(next_check + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')}\n"
        f"• 排程狀態: {'✅ 運行中' if CHANGELOG_CHANNEL_ID else '❌ 未啟用'}\n"
        f"• 通知頻道: {f'<#{CHANGELOG_CHANNEL_ID}>' if CHANGELOG_CHANNEL_ID else '未設定'}"
    )
    
    await ctx.send(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def test_schedule(ctx):
    """測試排程系統（立即觸發檢查）"""
    await ctx.send("🔔 手動觸發排程檢查...")
    await execute_scheduled_check()
    await ctx.send("✅ 排程檢查完成")

# 保留您現有的所有函數（從這裡開始都是您原有的程式碼）

def get_latest_build_status():
    """獲取最近一次的建置狀態"""
    try:
        if not GH_TOKEN:
            return "❌ GitHub Token 未設定，請檢查 .env 檔案"
        
        # 設定 API 請求
        headers = {
            'Authorization': f'token {GH_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs'
        
        print(f"正在請求 GitHub API: {url}")
        
        # 發送請求
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 如果失敗會拋出異常
        
        data = response.json()
        
        if not data['workflow_runs']:
            return "📭 尚未有任何建置記錄"
        
        # 解析最新一筆執行
        latest_run = data['workflow_runs'][0]
        
        status = latest_run['conclusion']  # success, failure, cancelled
        created_at = latest_run['created_at']
        html_url = latest_run['html_url']
        workflow_name = latest_run['name']
        
        # 轉換為中文狀態
        status_map = {
            'success': '✅ 成功',
            'failure': '❌ 失敗', 
            'cancelled': '⏹️ 已取消',
            None: '🔄 執行中'
        }
        
        status_text = status_map.get(status, '❓ 未知狀態')
        
        # 格式化時間
        from datetime import datetime
        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        return (f"📊 **最近一次建置狀態**\n"
                f"**工作流程**: {workflow_name}\n"
                f"**狀態**: {status_text}\n"
                f"**時間**: {formatted_time}\n"
                f"**詳細資訊**: [查看詳情]({html_url})")
                
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return "❌ 找不到倉庫，請檢查 GITHUB_OWNER 和 GITHUB_REPO 設定"
        elif e.response.status_code == 403:
            return "❌ 權限不足，請檢查 GitHub Token 權限"
        else:
            return f"❌ HTTP 錯誤: {e.response.status_code}"
    except Exception as e:
        return f"❌ 獲取狀態時出錯: {str(e)}"
        
def get_latest_commit():
    """獲取最近一次的 commit 資訊"""
    try:
        if not GH_TOKEN:
            return "❌ GitHub Token 未設定"
        
        headers = {
            'Authorization': f'token {GH_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits'
        params = {'per_page': 1}
        
        print(f"🌐 正在請求 GitHub Commits API: {url}")
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        commits = response.json()
        
        if not commits:
            return "📭 尚未有任何 commit 記錄"
        
        commit_data = commits[0]
        return format_commit_message(commit_data)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return "❌ 找不到倉庫"
        elif e.response.status_code == 403:
            return "❌ 權限不足"
        else:
            return f"❌ HTTP 錯誤: {e.response.status_code}"
    except Exception as e:
        return f"❌ 獲取 commit 資訊時出錯: {str(e)}"

def format_commit_message(commit_data):
    """格式化 commit 訊息"""
    # 取得基本資訊
    sha_short = commit_data['sha'][:7]
    message = commit_data['commit']['message']
    author_name = commit_data['commit']['author']['name']
    commit_date = commit_data['commit']['author']['date']
    
    # 取得 GitHub 使用者名稱（安全處理）
    github_username = commit_data['author']['login'] if commit_data.get('author') else author_name
    
    # 處理 commit 訊息
    first_line = message.split('\n')[0]
    if len(first_line) > 100:
        first_line = first_line[:97] + "..."
    
    # 格式化時間
    dt = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
    formatted_time = dt.strftime("%m/%d %H:%M")
    
    # 建立 GitHub 連結
    commit_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/commit/{commit_data['sha']}"
    
    return (f"📝 **最近一次 Commit**\n"
            f"**訊息**: {first_line}\n"
            f"**作者**: {author_name} (@{github_username})\n"
            f"**時間**: {formatted_time}\n"
            f"**Commit ID**: `{sha_short}`\n"
            f"**詳細資訊**: [查看 commit]({commit_url})")

def get_workflow_status(workflow_file=None):
    """獲取 GitHub Actions workflow 狀態"""
    try:
        if not GH_TOKEN:
            return "❌ GitHub Token 未設定，請檢查 .env 檔案"
        
        headers = {
            'Authorization': f'token {GH_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # 構建 API URL
        if workflow_file:
            # 先獲取 workflow ID
            workflow_id = get_workflow_id_by_name(workflow_file)
            if workflow_id:
                url = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{workflow_id}/runs'
            else:
                # 直接使用檔案名稱嘗試
                url = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{workflow_file}/runs'
        else:
            # 獲取所有 workflow 的運行記錄
            url = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs'
        
        params = {'per_page': 5}
        
        print(f"🌐 請求 GitHub Actions API: {url}")
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('workflow_runs'):
            return "📭 尚未有任何 workflow 運行記錄"
        
        return format_workflow_runs(data['workflow_runs'], workflow_file)
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"❌ GitHub API 錯誤: {e.response.status_code}"
        if e.response.status_code == 404:
            error_msg += " - 找不到倉庫或 workflow"
            error_msg += f"\n💡 請使用 `!workflow_list` 查看正確的 workflow 檔案名稱"
        elif e.response.status_code == 403:
            error_msg += " - 權限不足，請檢查 token 權限"
        return error_msg
    except Exception as e:
        return f"❌ 獲取 workflow 狀態時出錯: {str(e)}"

def get_workflow_id_by_name(workflow_name):
    """根據顯示名稱獲取 workflow ID"""
    try:
        headers = {
            'Authorization': f'token {GH_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows'
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        for workflow in data.get('workflows', []):
            if workflow['name'].lower() == workflow_name.lower():
                return workflow['id']
        
        return None
    except:
        return None

def format_workflow_runs(workflow_runs, workflow_filter=None):
    """格式化 workflow 運行資訊"""
    if not workflow_runs:
        return "📭 沒有找到 workflow 運行記錄"
    
    message = "🚀 **GitHub Actions Pipeline 狀態**\n\n"
    
    for i, run in enumerate(workflow_runs[:3]):
        status_emoji = {
            'completed': '✅' if run['conclusion'] == 'success' else '❌',
            'in_progress': '🔄',
            'queued': '⏳',
            'pending': '⏳',
            'action_required': '⚠️',
            'cancelled': '⏹️'
        }
        
        conclusion_map = {
            'success': '成功',
            'failure': '失敗',
            'cancelled': '已取消',
            'skipped': '已跳過',
            'timed_out': '超時',
            None: '進行中'
        }
        
        emoji = status_emoji.get(run['status'], '❓')
        conclusion = conclusion_map.get(run['conclusion'], '未知')
        
        created_at = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
        formatted_time = created_at.strftime("%m/%d %H:%M")
        
        run_duration = ""
        if run['status'] == 'completed' and run['updated_at']:
            updated_at = datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00'))
            duration = updated_at - created_at
            run_duration = f"⏱️ {duration.total_seconds():.0f}秒"
        
        message += (
            f"{emoji} **{run['name']}**\n"
            f"   📋 狀態: {conclusion}\n"
            f"   🕒 時間: {formatted_time}\n"
            f"   🔢 運行ID: #{run['run_number']}\n"
            f"   🎯 分支: {run['head_branch']}\n"
            f"   📁 檔案: `{run['path'].split('/')[-1]}`\n"
            f"   {run_duration}\n"
            f"   🔗 [查看詳情]({run['html_url']})\n\n"
        )
    
    return message

def get_workflow_list():
    """獲取可用的 workflow 列表"""
    try:
        if not GH_TOKEN:
            return "❌ GitHub Token 未設定"
        
        headers = {
            'Authorization': f'token {GH_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows'
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('workflows'):
            return "📭 尚未設定任何 workflow"
        
        message = "📋 **可用的 Workflows**\n\n"
        message += "💡 **使用方式**: `!pipeline_status <檔案名稱>`\n\n"
        
        for workflow in data['workflows']:
            state_emoji = '✅' if workflow['state'] == 'active' else '⏸️'
            file_name = workflow['path'].split('/')[-1]
            message += f"{state_emoji} **{workflow['name']}**\n"
            message += f"   📁 檔案: `{file_name}`\n"
            message += f"   📊 狀態: {workflow['state']}\n\n"
        
        return message
        
    except Exception as e:
        return f"❌ 獲取 workflow 列表時出錯: {str(e)}"
       

def get_merged_prs_since(since_date):
    """獲取指定時間後合併的 PR"""
    try:
        if not GH_TOKEN:
            return None, "❌ GitHub Token 未設定"
        
        headers = {
            'Authorization': f'token {GH_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f'https://api.github.com/search/issues'
        query = f'repo:{GITHUB_OWNER}/{GITHUB_REPO} is:pr is:merged merged:>={since_date}'
        params = {'q': query, 'sort': 'updated', 'order': 'desc'}
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data.get('items', []), None
        
    except Exception as e:
        return None, f"❌ 獲取 PR 時出錯: {str(e)}"

def generate_changelog(prs):
    """生成精簡的 changelog"""
    if not prs:
        return None
    
    # 計算時間範圍
    start_date = (datetime.now() - timedelta(days=CHECK_INTERVAL_DAYS)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    changelog = f"📊 **每周更新報告 ({start_date} ~ {end_date})**\n\n"
    changelog += f"本周共合併了 **{len(prs)}** 個 PR\n\n"
    
    for pr in prs:
        pr_number = pr['number']
        pr_title = pr['title']
        pr_url = pr['html_url']
        author = pr['user']['login']
        merged_at = pr['pull_request']['merged_at']
        
        # 格式化時間
        merged_time = datetime.fromisoformat(merged_at.replace('Z', '+00:00'))
        formatted_time = merged_time.strftime("%m/%d")
        
        changelog += f"• [#{pr_number}]({pr_url}) {pr_title}\n"
        changelog += f"  👤 {author} | 📅 {formatted_time}\n\n"
    
    changelog += f"💡 使用 `!changelog {CHECK_INTERVAL_DAYS}` 查看詳細內容"
    return changelog

# 保留您原有的手動檢查任務（但排程系統會使用新的檢查邏輯）
@tasks.loop(hours=24)
async def check_new_prs_task():
    """定期檢查新合併的 PR（保留原有功能）"""
    global last_check_time
    
    try:
        # 檢查是否達到設定的間隔天數
        time_since_last_check = datetime.now() - last_check_time
        if time_since_last_check.days < CHECK_INTERVAL_DAYS:
            next_check = last_check_time + timedelta(days=CHECK_INTERVAL_DAYS)
            print(f"⏰ 下次手動檢查時間: {next_check.strftime('%Y-%m-%d %H:%M')}")
            return
        
        print(f"🔍 進行手動每周檢查（間隔: {CHECK_INTERVAL_DAYS}天）...")
        
        since_date = last_check_time.strftime("%Y-%m-%d")
        prs, error = get_merged_prs_since(since_date)
        
        if error:
            print(f"❌ 手動檢查新 PR 失敗: {error}")
            return
        
        if prs:
            print(f"📝 發現 {len(prs)} 個新合併的 PR")
            changelog_content = generate_changelog(prs)
            
            if changelog_content and CHANGELOG_CHANNEL_ID:
                success = await send_changelog_to_channel(changelog_content)
                if success:
                    print("✅ 手動每周報告發送成功")
        else:
            print("📭 本周沒有新合併的 PR")
        
        last_check_time = datetime.now()
        print(f"✅ 手動檢查完成，下次檢查在 {CHECK_INTERVAL_DAYS} 天後")
        
    except Exception as e:
        print(f"❌ 手動定期檢查任務錯誤: {str(e)}")

# 修改 on_ready 事件，同時啟動手動檢查和排程檢查
@bot.event
async def on_ready():
    print(f"✅ 已登入為 {bot.user}")
    print(f"🤖 Bot 已準備好接收指令！")
    print(f"🌐 運行環境: {'Render' if not os.path.exists('.env') else '本地'}")
    
    # 計算下次排程檢查時間
    next_schedule_check = get_next_monday()
    print(f"⏰ 下次排程檢查時間: {next_schedule_check.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"⏰ 台灣時間: {(next_schedule_check + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')}")
    
    if CHANGELOG_CHANNEL_ID:
        print(f"📊 自動檢查已啟用，頻道: {CHANGELOG_CHANNEL_ID}")
        
        # 啟動手動檢查任務（保留原有功能）
        check_new_prs_task.start()
        
        # 啟動排程器線程
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # 啟動事件檢查任務
        check_scheduled_events.start()
        
        print("✅ 雙重檢查系統已啟動（手動 + 排程）")
    else:
        print("ℹ️  自動檢查未啟用（未設定 CHANGELOG_CHANNEL_ID）")

# 保留您原有的所有指令
@bot.command()
async def check_settings(ctx):
    """查看當前檢查設定"""
    next_manual_check = last_check_time + timedelta(days=CHECK_INTERVAL_DAYS)
    next_schedule_check = get_next_monday()
    
    message = (
        f"⚙️ **當前設定**\n"
        f"**手動檢查系統**\n"
        f"• 檢查頻率: 每 {CHECK_INTERVAL_DAYS} 天\n"
        f"• 最後檢查: {last_check_time.strftime('%Y-%m-%d %H:%M')}\n"
        f"• 下次檢查: {next_manual_check.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"**排程檢查系統**\n"
        f"• 檢查時間: 每週一 09:00 (台灣時間)\n"
        f"• 下次檢查: {next_schedule_check.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"• 台灣時間: {(next_schedule_check + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')}\n\n"
        f"• 自動發送: {'✅ 已啟用' if CHANGELOG_CHANNEL_ID else '❌ 未啟用'}"
    )
    
    await ctx.send(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def force_check(ctx):
    """強制立即執行檢查"""
    global last_check_time
    
    await ctx.send("🔄 強制執行檢查中...")
    
    since_date = last_check_time.strftime("%Y-%m-%d")
    prs, error = get_merged_prs_since(since_date)
    
    if error:
        await ctx.send(error)
        return
    
    if prs:
        changelog_content = generate_changelog(prs)
        if CHANGELOG_CHANNEL_ID:
            success = await send_changelog_to_channel(changelog_content)
            if success:
                await ctx.send("✅ 強制檢查完成，報告已發送")
            else:
                await ctx.send("✅ 強制檢查完成，但發送失敗")
        else:
            await ctx.send(f"✅ 強制檢查完成，找到 {len(prs)} 個PR\n{changelog_content}")
    else:
        await ctx.send("📭 沒有找到新的 PR")
    
    last_check_time = datetime.now()

@bot.command()
async def changelog(ctx, days: int = None):
    """顯示近期更新日誌"""
    if days is None:
        days = CHECK_INTERVAL_DAYS
    
    if days > 30:
        await ctx.send("❌ 最多只能查詢 30 天內的更新")
        return
    
    wait_msg = await ctx.send(f"🔄 正在生成最近 {days} 天的更新日誌...")
    
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    prs, error = get_merged_prs_since(since_date)
    
    if error:
        await wait_msg.edit(content=error)
        return
    
    if not prs:
        await wait_msg.edit(content=f"📭 最近 {days} 天沒有合併的 PR")
        return
    
    detailed_changelog = f"🚀 **最近 {days} 天更新日誌**\n\n"
    for pr in prs:
        pr_number = pr['number']
        pr_title = pr['title']
        pr_url = pr['html_url']
        merged_at = pr['pull_request']['merged_at']
        author = pr['user']['login']
        
        merged_time = datetime.fromisoformat(merged_at.replace('Z', '+00:00'))
        formatted_time = merged_time.strftime("%m/%d %H:%M")
        
        detailed_changelog += f"**#{pr_number}** - {pr_title}\n"
        detailed_changelog += f"⏰ {formatted_time} | 👤 {author}\n"
        detailed_changelog += f"🔗 [查看PR]({pr_url})\n\n"
    
    await wait_msg.edit(content=detailed_changelog)

@bot.command()
async def hello(ctx):
    await ctx.send("哈囉！我是你的 DevOps Discord Bot 🤖")

@bot.command()
async def build_status(ctx):
    """查詢最近一次的 CI/CD 建置狀態"""
    print(f"收到 build_status 指令來自 {ctx.author}")
    wait_msg = await ctx.send("🔄 正在查詢建置狀態...")
    status_message = get_latest_build_status()
    await wait_msg.edit(content=status_message)
    print(f"已回覆建置狀態")

@bot.command()
async def last_commit(ctx):
    """查詢最近一次的 commit 訊息"""
    print(f"📨 收到 last_commit 指令來自 {ctx.author}")
    wait_msg = await ctx.send("🔄 正在查詢最新 commit...")
    commit_info = get_latest_commit()
    await wait_msg.edit(content=commit_info)
    print(f"✅ 已回覆 commit 資訊")

@bot.command()
async def pipeline_status(ctx, workflow_file=None):
    """查詢 GitHub Actions Pipeline 狀態"""
    print(f"📊 收到 pipeline_status 指令來自 {ctx.author}")
    wait_msg = await ctx.send("🔄 正在查詢 GitHub Actions 狀態...")
    
    if workflow_file and workflow_file.lower() == 'list':
        workflow_list = get_workflow_list()
        await wait_msg.edit(content=workflow_list)
    else:
        status_message = get_workflow_status(workflow_file)
        await wait_msg.edit(content=status_message)

@bot.command()
async def workflow_list(ctx):
    """顯示可用的 GitHub Actions Workflows"""
    wait_msg = await ctx.send("🔄 正在獲取 workflow 列表...")
    workflow_list = get_workflow_list()
    await wait_msg.edit(content=workflow_list)
    
@bot.command()
async def panel(ctx):
    """開啟 DevOps 控制台面板"""
    embed = create_main_embed()
    view = ControlPanelView()
    await ctx.send(embed=embed, view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def update_panel(ctx):
    """更新控制面板（管理員指令）"""
    await send_control_panel()
    await ctx.send("✅ 已更新控制面板", ephemeral=True)

# 啟動 Bot
if __name__ == "__main__":
    print("🚀 啟動 Discord Bot（排程版）...")
    print("💡 提示：Bot 需要保持運行才能執行排程任務")
    bot.run(TOKEN)