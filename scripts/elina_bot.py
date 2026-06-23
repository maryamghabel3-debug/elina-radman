#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  ELINA OS — Telegram Management Bot                    ║
║  Full agent control + GitHub management + Chat         ║
║  Cost: $0/month                                        ║
╚══════════════════════════════════════════════════════════╝

COMMANDS:
  /status     — System overview
  /content    — Generate new content
  /publish    — Publish approved content
  /list       — List queued content
  /approve ID — Approve & publish content
  /reject ID  — Reject content
  /trends     — Latest fashion trends
  /agents     — List all agents
  /agent NAME — Agent details
  /addagent   — Add a new agent
  /delagent   — Remove an agent
  /github     — GitHub repo status
  /ghfile PATH — View a file from repo
  /ghedit PATH TEXT — Edit a file in repo
  /help       — Show all commands
"""
import os, sys, json, time, glob
from datetime import datetime, timedelta
import requests

# ═══ CONFIG ═══
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN","")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID","")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY","")
BUFFER_KEY = os.environ.get("BUFFER_API_TOKEN","")
GH_PAT = os.environ.get("GH_PAT","")
GH_OWNER = os.environ.get("GITHUB_REPO_OWNER","")
GH_REPO = os.environ.get("GITHUB_REPO_NAME","elina-radman")

BASE = f"https://api.telegram.org/bot{TOKEN}"
GH_API = "https://api.github.com"

# ═══ HELPERS ═══
def send(msg, parse="Markdown"):
    requests.post(f"{BASE}/sendMessage",
        json={"chat_id":CHAT_ID,"text":msg,"parse_mode":parse},timeout=10)

def reply(chat_id, msg, parse="Markdown"):
    requests.post(f"{BASE}/sendMessage",
        json={"chat_id":chat_id,"text":msg,"parse_mode":parse},timeout=10)

# ═══ COMMAND HANDLERS ═══

def cmd_status(chat_id, args):
    """System status overview"""
    # Count content
    q = len(glob.glob("content/queue/*.json"))
    # Count agents
    agent_files = glob.glob("agents/*.py")
    agents = [f.split("/")[-1].replace(".py","") for f in agent_files 
              if not f.endswith("__init__.py") and not f.endswith("base.py")]
    
    msg = f"""🕊️ *ELINA OS STATUS*

📊 *Content*
• Queue: {q} files
• Status: {'🟢 Active' if q > 0 else '🟡 Empty'}

🤖 *Agents* ({len(agents)})
{chr(10).join(f'• {a}' for a in agents)}

🔗 *Connections*
• Gemini: {'✅' if GEMINI_KEY else '❌'}
• Buffer: {'✅' if BUFFER_KEY else '❌'}
• GitHub: {'✅' if GH_PAT else '❌'}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} Tehran
"""
    reply(chat_id, msg)

def cmd_content(chat_id, args):
    """Generate new content"""
    reply(chat_id, "🎨 *Generating content...*\nPlease wait ~10 seconds")
    
    try:
        from agents.content_creator import ContentCreator
        cc = ContentCreator()
        pieces = cc.run(count=3)
        
        msg = f"✅ *{len(pieces)} pieces created!*\n\n"
        for p in pieces:
            msg += f"🆔 `{p['id']}`\n"
            msg += f"🏷 {p['pillar']}\n"
            msg += f"📝 {p['caption'][:100]}...\n\n"
        msg += "Approve with: `/approve ID`"
        reply(chat_id, msg)
    except Exception as e:
        reply(chat_id, f"❌ Error: {e}")

def cmd_publish(chat_id, args):
    """Publish approved content"""
    reply(chat_id, "📤 *Publishing...*")
    try:
        from agents.publisher import Publisher
        p = Publisher()
        result = p.run()
        if "error" in result:
            reply(chat_id, f"❌ {result['error']}")
        else:
            n = len(result.get("published",[]))
            reply(chat_id, f"✅ Published {n} items!")
    except Exception as e:
        reply(chat_id, f"❌ {e}")

def cmd_list(chat_id, args):
    """List queued content"""
    files = sorted(glob.glob("content/queue/*.json"))
    if not files:
        reply(chat_id, "📭 Queue is empty. Use /content to generate.")
        return
    
    msg = "📋 *Content Queue*\n\n"
    for fp in files[-5:]:
        with open(fp) as f:
            pieces = json.load(f)
        for p in pieces:
            icon = {"pending_approval":"⏳","approved":"✅","rejected":"❌","published":"📤"}
            s = icon.get(p.get("status",""),"❓")
            msg += f"{s} `{p['id']}` — {p['pillar']}\n"
            msg += f"   {p['caption'][:80]}...\n\n"
    
    reply(chat_id, msg)

def cmd_approve(chat_id, args):
    """Approve content by ID"""
    if not args:
        reply(chat_id, "Usage: `/approve CONTENT_ID`")
        return
    
    cid = args[0]
    found = False
    for fp in sorted(glob.glob("content/queue/*.json")):
        with open(fp) as f:
            pieces = json.load(f)
        for p in pieces:
            if p.get("id") == cid:
                p["status"] = "approved"
                p["approved_at"] = datetime.now().isoformat()
                found = True
        with open(fp,"w") as f:
            json.dump(pieces, f, indent=2)
        if found: break
    
    if found:
        reply(chat_id, f"✅ Approved: `{cid}`\nPublishing now...")
        cmd_publish(chat_id, [])
    else:
        reply(chat_id, f"❌ Content `{cid}` not found")

def cmd_reject(chat_id, args):
    """Reject content"""
    if not args:
        reply(chat_id, "Usage: `/reject CONTENT_ID`")
        return
    cid = args[0]
    for fp in sorted(glob.glob("content/queue/*.json")):
        with open(fp) as f:
            pieces = json.load(f)
        for p in pieces:
            if p.get("id") == cid:
                p["status"] = "rejected"
        with open(fp,"w") as f:
            json.dump(pieces, f, indent=2)
    reply(chat_id, f"❌ Rejected: `{cid}`")

def cmd_trends(chat_id, args):
    """Show latest trends"""
    try:
        from agents.trend_hunter import TrendHunter
        th = TrendHunter()
        trends = th.run()
        msg = "🔥 *Latest Trends*\n\n"
        for t in trends[:5]:
            msg += f"• *{t['name']}*\n"
            msg += f"  {t['platform']} | {t['format']} | effort: {t['effort']}\n\n"
        reply(chat_id, msg)
    except Exception as e:
        reply(chat_id, f"❌ {e}")

def cmd_agents(chat_id, args):
    """List all agents"""
    files = sorted(glob.glob("agents/*.py"))
    agents = [f.split("/")[-1].replace(".py","") for f in files
              if not f.endswith("__init__.py") and not f.endswith("base.py")]
    
    msg = f"🤖 *Agent Roster* ({len(agents)})\n\n"
    for a in agents:
        msg += f"• *{a}* — `/agent {a}` for details\n"
    msg += "\n➕ `/addagent` | ➖ `/delagent NAME`"
    reply(chat_id, msg)

def cmd_agent(chat_id, args):
    """Agent details"""
    if not args:
        reply(chat_id, "Usage: `/agent AGENT_NAME`")
        return
    name = args[0]
    fp = f"agents/{name}.py"
    if not os.path.exists(fp):
        reply(chat_id, f"❌ Agent `{name}` not found")
        return
    with open(fp) as f:
        content = f.read()
    # Extract docstring
    lines = content.split("\n")
    doc = ""
    in_doc = False
    for l in lines:
        if '"""' in l:
            if in_doc: break
            in_doc = True
            continue
        if in_doc:
            doc += l + "\n"
    
    size = len(content)
    reply(chat_id, f"🤖 *Agent: {name}*\n\n{doc}\n📏 {size} bytes\n📁 `{fp}`")

def cmd_addagent(chat_id, args):
    """Add a new agent via GitHub"""
    if not GH_PAT:
        reply(chat_id, "❌ GitHub PAT not configured. Set GH_PAT secret.")
        return
    reply(chat_id, "➕ *Add Agent*\n\nSend in format:\n`/addagent_done NAME | DESCRIPTION | CODE`\n\nExample:\n`/addagent_done engagement | replies to comments | pass`")

def cmd_addagent_done(chat_id, args):
    """Process add agent request"""
    if not args:
        reply(chat_id, "Send: `/addagent_done NAME | DESC | CODE`")
        return
    text = " ".join(args)
    parts = text.split("|",2)
    if len(parts) < 2:
        reply(chat_id, "Format: `/addagent_done NAME | DESCRIPTION | CODE`")
        return
    name = parts[0].strip()
    desc = parts[1].strip() if len(parts) > 1 else ""
    code = parts[2].strip() if len(parts) > 2 else "pass"
    
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        result = gm.add_agent(name, desc, code)
        if "error" in result:
            reply(chat_id, f"❌ {result}")
        else:
            reply(chat_id, f"✅ Agent *{name}* added!\n📁 `{result['path']}`\n\nRedeploy to activate.")
    except Exception as e:
        reply(chat_id, f"❌ {e}")

def cmd_delagent(chat_id, args):
    """Delete an agent"""
    if not args:
        reply(chat_id, "Usage: `/delagent AGENT_NAME`\nProtected: base, __init__, github_manager")
        return
    name = args[0]
    if name in ["base","__init__","github_manager"]:
        reply(chat_id, f"🔒 Agent `{name}` is protected")
        return
    
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        result = gm.remove_agent(name)
        if "error" in result:
            reply(chat_id, f"❌ {result}")
        else:
            reply(chat_id, f"➖ Agent *{name}* removed!")
    except Exception as e:
        reply(chat_id, f"❌ {e}")

def cmd_github(chat_id, args):
    """GitHub repo status"""
    if not GH_PAT:
        reply(chat_id, "❌ No GH_PAT. Set it in GitHub Secrets.")
        return
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        status = gm.repo_status()
        agents_list = gm.list_agents()
        
        msg = f"🐙 *GitHub Repo*\n\n"
        msg += f"📦 {status.get('name','?')}\n"
        msg += f"⭐ {status.get('stars','?')} stars\n"
        msg += f"🕐 Updated: {status.get('updated','?')[:10]}\n"
        msg += f"🤖 Agents: {agents_list.get('count','?')}\n"
        msg += f"🔗 {status.get('url','')}"
        reply(chat_id, msg)
    except Exception as e:
        reply(chat_id, f"❌ {e}")

def cmd_ghfile(chat_id, args):
    """View a file from GitHub repo"""
    if not args:
        reply(chat_id, "Usage: `/ghfile PATH`\nExample: `/ghfile agents/publisher.py`")
        return
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        result = gm.get_file(args[0])
        if "error" in result:
            reply(chat_id, f"❌ Error {result['error']}")
        else:
            content = result['content'][:3500]
            reply(chat_id, f"📄 *{args[0]}*\n\n```python\n{content}\n```")
    except Exception as e:
        reply(chat_id, f"❌ {e}")

def cmd_ghedit(chat_id, args):
    """Edit a file on GitHub — needs full new content"""
    if not args or len(args) < 2:
        reply(chat_id, "Usage: `/ghedit PATH | NEW_CONTENT`\nOr send file content after the path.")
        return
    text = " ".join(args)
    parts = text.split("|",1)
    if len(parts) < 2:
        reply(chat_id, "Format: `/ghedit agents/my_agent.py | new python code here...`")
        return
    path = parts[0].strip()
    content = parts[1].strip()
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        result = gm.update_file(path, content, f"✏️ Edit {path} via Telegram")
        if "error" in result:
            reply(chat_id, f"❌ {result}")
        else:
            reply(chat_id, f"✅ *{path}* updated!")
    except Exception as e:
        reply(chat_id, f"❌ {e}")

def cmd_help(chat_id, args):
    msg = """🕊️ *ELINA OS — Commands*

📊 */status* — System overview
🎨 */content* — Generate new posts
📤 */publish* — Publish approved
📋 */list* — Show content queue
✅ */approve ID* — Approve & post
❌ */reject ID* — Reject content
🔥 */trends* — Fashion trends

🤖 */agents* — List all agents
🔍 */agent NAME* — Agent details
➕ */addagent* — Add new agent
➖ */delagent NAME* — Remove agent

🐙 */github* — Repo status
📄 */ghfile PATH* — View file
✏️ */ghedit PATH | CODE* — Edit file

Any message ≠ command → I'll chat back! 💬"""
    reply(chat_id, msg)

# ═══ AI CHAT ═══
def chat_reply(chat_id, text):
    """Reply to non-command messages using Gemini"""
    if not GEMINI_KEY:
        reply(chat_id, "👋 I'm ElinaOS! Type /help for commands.")
        return
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""You are ElinaOS, the AI assistant for Elina Radman (fashion influencer, Petite Quiet Luxury, 4'11", 150cm, 43kg).

Elina's brand info:
- Niche: Petite Quiet Luxury fashion
- Audience: women 18-35, petite frames
- Platforms: Instagram, TikTok, YouTube, Pinterest
- Style: minimal, neutral colors, capsule wardrobes
- Tone: warm, sophisticated, relatable

Current user message: {text}

Reply helpfully in the same language as the user. Be warm and supportive.
Keep it under 500 chars unless asked for more detail."""
        
        response = model.generate_content(prompt)
        reply(chat_id, response.text.strip())
    except Exception as e:
        reply(chat_id, f"💬 *ElinaOS here!*\n\nI can manage your content, agents, and GitHub.\nType /help for commands.\n\n(API chat unavailable: {str(e)[:100]})")

# ═══ MAIN POLLING LOOP ═══
COMMANDS = {
    "status": cmd_status, "content": cmd_content, "publish": cmd_publish,
    "list": cmd_list, "approve": cmd_approve, "reject": cmd_reject,
    "trends": cmd_trends, "agents": cmd_agents, "agent": cmd_agent,
    "addagent": cmd_addagent, "addagent_done": cmd_addagent_done,
    "delagent": cmd_delagent, "github": cmd_github, "ghfile": cmd_ghfile,
    "ghedit": cmd_ghedit, "help": cmd_help, "start": cmd_help,
}

def process_message(msg):
    """Process a single Telegram message"""
    text = msg.get("text","")
    chat_id = msg.get("chat",{}).get("id","")
    username = msg.get("from",{}).get("username","")
    
    print(f"📩 [{username}] {text[:80]}")
    
    if text.startswith("/"):
        parts = text[1:].split()
        cmd = parts[0].split("@")[0]  # Remove @botname if present
        args = parts[1:] if len(parts) > 1 else []
        
        handler = COMMANDS.get(cmd)
        if handler:
            handler(str(chat_id), args)
        else:
            reply(chat_id, f"❓ Unknown: /{cmd}\nType /help")
    else:
        chat_reply(str(chat_id), text)

def main():
    print("🕊️ ELINA OS Bot starting...")
    print(f"   Token: {'✅' if TOKEN else '❌'}")
    print(f"   Chat ID: {CHAT_ID}")
    print(f"   Gemini: {'✅' if GEMINI_KEY else '❌'}")
    print(f"   Buffer: {'✅' if BUFFER_KEY else '❌'}")
    print(f"   GitHub PAT: {'✅' if GH_PAT else '❌'}")
    
    if not TOKEN:
        print("❌ No TELEGRAM_BOT_TOKEN — cannot start")
        return
    
    # Check for pending commands (GitHub Actions mode)
    if os.environ.get("RUN_MODE") == "ACTION":
        print("📋 Running in GitHub Actions mode — checking for commands...")
        # Process any pending commands from a queue file
        cmd_file = "content/queue/pending_commands.json"
        if os.path.exists(cmd_file):
            with open(cmd_file) as f:
                commands = json.load(f)
            for cmd in commands:
                print(f"   Running: {cmd}")
                process_message(cmd.get("message",{}))
            os.remove(cmd_file)
        return
    
    # Polling mode — runs for 5 minutes (GitHub Actions limit per run)
    print("📡 Polling for messages...")
    offset = 0
    start = time.time()
    
    while time.time() - start < 300:  # 5 minute window
        try:
            url = f"{BASE}/getUpdates?offset={offset}&timeout=30"
            r = requests.get(url, timeout=35)
            updates = r.json().get("result",[])
            
            for u in updates:
                offset = u["update_id"] + 1
                msg = u.get("message")
                if msg:
                    process_message(msg)
        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(5)
    
    print("⏹ Bot session ended (5 min limit)")

if __name__ == "__main__":
    main()
