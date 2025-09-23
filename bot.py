import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import requests
import json
from datetime import datetime, timedelta
import random
import asyncio

# 修改環境變數載入邏輯，兼容 Railway 和本地開發
if os.path.exists('.env'):
    load_dotenv('.env')
else:
    # 在 Railway 上直接使用環境變數
    print("ℹ️  在 Railway 環境中運行，使用系統環境變數")


# 從環境變數讀取 Token
TOKEN = os.getenv("DISCORD_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
GITHUB_OWNER = "alpachen"
GITHUB_REPO = "discord-bot-devops"
CHANGELOG_CHANNEL_ID = os.getenv("CHANGELOG_CHANNEL_ID")

# 可調整的檢查頻率（單位：天）
CHECK_INTERVAL_DAYS = 7  # 預設一周一次，您可以隨時修改這個數字


# 設定意圖
intents = discord.Intents.default()
intents.message_content = True

# 建立 Bot 物件，設定前綴詞
bot = commands.Bot(command_prefix="!", intents=intents)

# 記錄最後檢查時間
last_check_time = datetime.now() - timedelta(days=CHECK_INTERVAL_DAYS)

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
    
# 自動檢查任務 - 改為每周檢查一次
@tasks.loop(hours=24)  # 每天檢查一次，但實際根據間隔判斷
async def check_new_prs_task():
    """定期檢查新合併的 PR"""
    global last_check_time
    
    try:
        # 檢查是否達到設定的間隔天數
        time_since_last_check = datetime.now() - last_check_time
        if time_since_last_check.days < CHECK_INTERVAL_DAYS:
            # 還沒到檢查時間
            next_check = last_check_time + timedelta(days=CHECK_INTERVAL_DAYS)
            print(f"⏰ 下次檢查時間: {next_check.strftime('%Y-%m-%d %H:%M')}")
            return
        
        print(f"🔍 進行每周檢查（間隔: {CHECK_INTERVAL_DAYS}天）...")
        
        # 獲取上次檢查後的 PRs
        since_date = last_check_time.strftime("%Y-%m-%d")
        prs, error = get_merged_prs_since(since_date)
        
        if error:
            print(f"❌ 檢查新 PR 失敗: {error}")
            return
        
        if prs:
            print(f"📝 發現 {len(prs)} 個新合併的 PR")
            changelog_content = generate_changelog(prs)
            
            if changelog_content:
                success = await send_changelog_to_channel(changelog_content)
                if success:
                    print("✅ 每周報告發送成功")
        else:
            print("📭 本周沒有新合併的 PR")
        
        # 更新最後檢查時間
        last_check_time = datetime.now()
        print(f"✅ 檢查完成，下次檢查在 {CHECK_INTERVAL_DAYS} 天後")
        
    except Exception as e:
        print(f"❌ 定期檢查任務錯誤: {str(e)}")

@bot.event
async def on_ready():
    print(f"✅ 已登入為 {bot.user}")
    print(f"🤖 Bot 已準備好接收指令！")
    print(f"📅 自動檢查頻率: 每 {CHECK_INTERVAL_DAYS} 天一次")
    
    # 計算下次檢查時間
    next_check = last_check_time + timedelta(days=CHECK_INTERVAL_DAYS)
    print(f"⏰ 下次自動檢查時間: {next_check.strftime('%Y-%m-%d %H:%M')}")
    
    if CHANGELOG_CHANNEL_ID:
        print(f"📊 自動檢查已啟用，頻道: {CHANGELOG_CHANNEL_ID}")
        check_new_prs_task.start()
    else:
        print("ℹ️  自動檢查未啟用（未設定 CHANGELOG_CHANNEL_ID）")
        
# 查看當前設定的指令
@bot.command()
async def check_settings(ctx):
    """查看當前檢查設定"""
    next_check = last_check_time + timedelta(days=CHECK_INTERVAL_DAYS)
    
    message = (
        f"⚙️ **當前設定**\n"
        f"• 檢查頻率: 每 {CHECK_INTERVAL_DAYS} 天\n"
        f"• 最後檢查: {last_check_time.strftime('%Y-%m-%d %H:%M')}\n"
        f"• 下次檢查: {next_check.strftime('%Y-%m-%d %H:%M')}\n"
        f"• 自動發送: {'✅ 已啟用' if CHANGELOG_CHANNEL_ID else '❌ 未啟用'}"
    )
    
    await ctx.send(message)
    
# 手動立即檢查指令（管理員用）
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
    
    # 更新檢查時間
    last_check_time = datetime.now()

# 完整的 changelog 指令（手動）
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
    
    # 生成詳細 changelog
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

# 基本指令
@bot.command()
async def hello(ctx):
    await ctx.send("哈囉！我是你的 DevOps Discord Bot 🤖")

# 建置狀態指令
@bot.command()
async def build_status(ctx):
    """查詢最近一次的 CI/CD 建置狀態"""
    print(f"收到 build_status 指令來自 {ctx.author}")
    
    # 顯示等待訊息
    wait_msg = await ctx.send("🔄 正在查詢建置狀態...")
    
    # 獲取狀態
    status_message = get_latest_build_status()
    
    # 編輯訊息而不是發送新訊息
    await wait_msg.edit(content=status_message)
    print(f"已回覆建置狀態")
    
# 新增：查詢最近 commit 指令
@bot.command()
async def last_commit(ctx):
    """查詢最近一次的 commit 訊息"""
    print(f"📨 收到 last_commit 指令來自 {ctx.author}")
    wait_msg = await ctx.send("🔄 正在查詢最新 commit...")
    commit_info = get_latest_commit()
    await wait_msg.edit(content=commit_info)
    print(f"✅ 已回覆 commit 資訊")

# 修正：Pipeline 狀態指令
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

# Workflow 列表指令
@bot.command()
async def workflow_list(ctx):
    """顯示可用的 GitHub Actions Workflows"""
    wait_msg = await ctx.send("🔄 正在獲取 workflow 列表...")
    workflow_list = get_workflow_list()
    await wait_msg.edit(content=workflow_list)

# 啟動 Bot
if __name__ == "__main__":
    print("🚀 啟動 Discord Bot...")
    bot.run(TOKEN)