import streamlit as st
import os
import json
import glob
from datetime import datetime

# Configure the Streamlit Page
st.set_page_config(
    page_title="ElinaOS Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Quiet Luxury Aesthetic
st.markdown("""
<style>
    .reportview-container {
        background-color: #F7F5F0;
    }
    .main {
        background-color: #F7F5F0;
    }
    h1, h2, h3 {
        color: #333333;
        font-family: 'Helvetica Neue', sans-serif;
    }
    .stButton>button {
        color: white;
        background-color: #8B7E66;
        border-radius: 5px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #6d6350;
    }
    .metric-box {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR -----------------
st.sidebar.title("ElinaOS 🌿")
st.sidebar.markdown("### Control Panel")
page = st.sidebar.radio("Navigate", ["Home", "Chat with Elina", "AI Developer (Coder)", "Strategy Editor", "Diary & Emotions", "Content Manager", "Media Generator", "System Status"])

# ----------------- UTILS -----------------
# To allow imports from the parent directory
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def load_diary():
    path = "content/elina_diary.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            try: return json.load(f)
            except: return []
    return []

def save_diary(feeling):
    path = "content/elina_diary.json"
    entries = load_diary()
    entries.append({"date": datetime.now().isoformat(), "feeling": feeling})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(entries[-10:], f, indent=2)

def load_queue():
    queue_files = sorted(glob.glob("content/queue/*.json"))
    pieces = []
    for fp in queue_files:
        with open(fp) as f:
            try: pieces.extend(json.load(f))
            except: pass
    return pieces

# ----------------- PAGES -----------------

if page == "Home":
    st.title("Welcome to ElinaOS 🤍")
    st.markdown("Your central hub for managing the Elina Radman AI Influencer brand.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="metric-box"><h3>📝 Content Queue</h3><p>Manage pending and approved posts.</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-box"><h3>🎭 Emotional State</h3><p>Currently feeling: <b>' + (load_diary()[-1]["feeling"] if load_diary() else "Neutral") + '</b></p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-box"><h3>💰 Monetization</h3><p>Active Links: LTK, Amazon, Pietra.</p></div>', unsafe_allow_html=True)

elif page == "Chat with Elina":
    st.title("💬 Chat with Elina")
    st.markdown("Have a natural conversation with Elina to brainstorm ideas or ask about her day.")
    
    if "elina_chat_history" not in st.session_state:
        st.session_state.elina_chat_history = []
        
    for msg in st.session_state.elina_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    user_input = st.chat_input("Talk to Elina...")
    if user_input:
        st.session_state.elina_chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        with st.chat_message("assistant"):
            with st.spinner("Elina is typing..."):
                try:
                    from agents.llm_router import LLMRouter
                    router = LLMRouter()
                    system_prompt = (
                        "You are Elina Radman, a 24yo Iranian fashion influencer, clinical psychologist, "
                        "horticulturist, and social activist. You are petite, confident, vulnerable, and courageous. "
                        "Your user is your manager/friend. Reply in Persian, warm, emotional, and relatable."
                    )
                    # We use 'creative_writing' to route to OpenRouter/Claude or 'general' to route to GitHub/Gemini
                    response_data = router.smart_generate(user_input, task_type="general", system_prompt=system_prompt)
                    bot_reply = response_data.get("response", "من اینجام 🤍 مشکلی در ارتباط پیش اومد.")
                    st.markdown(bot_reply)
                    st.session_state.elina_chat_history.append({"role": "assistant", "content": bot_reply})
                except Exception as e:
                    st.error(f"Error connecting to LLM: {e}")

elif page == "AI Developer (Coder)":
    st.title("💻 AI Developer & GitHub Manager")
    st.markdown("Ask the AI Coder to write new agents, update code, or fix bugs, and push directly to GitHub.")
    
    if "coder_chat_history" not in st.session_state:
        st.session_state.coder_chat_history = []
        
    for msg in st.session_state.coder_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    coder_input = st.chat_input("Tell the developer what to code...")
    if coder_input:
        st.session_state.coder_chat_history.append({"role": "user", "content": coder_input})
        with st.chat_message("user"):
            st.markdown(coder_input)
            
        with st.chat_message("assistant"):
            with st.spinner("Developer is thinking..."):
                try:
                    from agents.llm_router import LLMRouter
                    from agents.github_manager import GitHubManager
                    router = LLMRouter()
                    gh = GitHubManager()
                    
                    system_prompt = (
                        "You are an expert Senior Python Developer. The user is asking you to write or update code for the ElinaOS project. "
                        "Only reply with the requested Python code or Markdown text. Do NOT include markdown code blocks (```python) in your final output if the user wants to save it as a file directly, "
                        "or provide instructions if they just want advice."
                    )
                    # We use 'coding' task type to route to DeepSeek (if available) or fallback to Gemini
                    response_data = router.smart_generate(coder_input, task_type="coding", system_prompt=system_prompt)
                    code_reply = response_data.get("response", "Error generating code.")
                    
                    st.markdown("### Generated Response/Code:")
                    st.code(code_reply)
                    st.session_state.coder_chat_history.append({"role": "assistant", "content": code_reply})
                    
                    # Store in session so user can review and push
                    st.session_state.last_generated_code = code_reply
                    
                except Exception as e:
                    st.error(f"Error: {e}")
                    
        # Option to push the code
        if "last_generated_code" in st.session_state:
            st.markdown("---")
            file_path = st.text_input("File path to save/update in GitHub (e.g., agents/new_agent.py):")
            commit_msg = st.text_input("Commit message:", value="feat: Add AI Developer generated code")
            if st.button("Push to GitHub 🐙"):
                with st.spinner("Pushing to GitHub..."):
                    gh = GitHubManager()
                    res = gh.update_file(file_path, st.session_state.last_generated_code, commit_msg)
                    if "error" in res:
                        st.error(f"Failed to push: {res}")
                    else:
                        st.success(f"Successfully pushed to {file_path}!")

elif page == "Strategy Editor":
    st.title("📈 Strategy & Documentation Editor")
    st.markdown("Directly edit Elina's core philosophy and monetization strategies.")
    
    file_to_edit = st.selectbox("Select file to edit:", ["docs/CHARACTER.md", "docs/BUSINESS-PLAN.md"])
    
    try:
        from agents.github_manager import GitHubManager
        gh = GitHubManager()
        
        # Load file content
        if "current_file_content" not in st.session_state or st.session_state.get("current_file_name") != file_to_edit:
            res = gh.get_file(file_to_edit)
            if "content" in res:
                st.session_state.current_file_content = res["content"]
                st.session_state.current_file_name = file_to_edit
            else:
                st.session_state.current_file_content = f"Could not load {file_to_edit}. Make sure GH_PAT is set."
                
        new_content = st.text_area("File Content:", value=st.session_state.current_file_content, height=400)
        
        if st.button("Save Changes to GitHub"):
            with st.spinner("Saving..."):
                res = gh.update_file(file_to_edit, new_content, f"docs: Update {file_to_edit} via Dashboard")
                if "error" in res:
                    st.error(f"Failed: {res}")
                else:
                    st.success("Successfully updated!")
                    st.session_state.current_file_content = new_content
                    
    except Exception as e:
        st.error(f"GitHub Error: {e}. Check if GH_PAT is set correctly in secrets.")

elif page == "Diary & Emotions":
    st.title("🎭 Diary & Emotional State")
    st.markdown("Set Elina's current feelings. This will directly affect how her ContentCreator agent writes captions.")
    
    new_feeling = st.text_area("How is Elina feeling today?", placeholder="E.g., Feeling calm and inspired by the autumn leaves...")
    if st.button("Save Entry"):
        if new_feeling:
            save_diary(new_feeling)
            st.success("Diary entry saved successfully! The Content Creator will use this state.")
        else:
            st.warning("Please write something before saving.")
            
    st.markdown("### Recent Entries")
    entries = load_diary()
    for e in reversed(entries):
        st.info(f"**{e['date'][:10]}**: {e['feeling']}")

elif page == "Content Manager":
    st.title("📝 Content Manager")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Generate New Content (Run ContentCreator)"):
            st.info("Triggering ContentCreator...")
            try:
                from agents.content_creator import ContentCreator
                cc = ContentCreator()
                pieces = cc.run(count=3)
                st.success(f"Generated {len(pieces)} new pieces!")
            except Exception as e:
                st.error(f"Error: {e}")
                st.info("Make sure your API keys (e.g., GEMINI_API_KEY) are set in your environment.")

    st.markdown("### Queue")
    pieces = load_queue()
    if not pieces:
        st.write("No content in queue.")
    else:
        for p in pieces:
            status_color = "green" if p.get("status") == "approved" else "orange" if p.get("status") == "pending_approval" else "red"
            with st.expander(f"[{p.get('status', 'unknown')}] {p.get('pillar', 'General')} - {p.get('id', '')}"):
                st.write(p.get("caption", ""))
                st.write(f"**Platforms:** {', '.join(p.get('platforms', []))}")
                st.write(f"**Hashtags:** {p.get('hashtags', '')}")

elif page == "Media Generator":
    st.title("📸 Media & Studio")
    st.markdown("Trigger image and video generation using Free Cloud GPUs (Hugging Face / Tencent).")
    
    tab1, tab2 = st.tabs(["🖼️ Image Studio", "🎬 Video Studio"])
    
    with tab1:
        st.markdown("### Generate Consistent Face Photo")
        img_prompt = st.text_input("Describe the scene (e.g., 'wearing a tailored camel blazer, sitting in a Parisian cafe'):", key="img_prompt")
        
        if st.button("Generate Image (InstantID)"):
            if not img_prompt:
                st.warning("Please enter a prompt.")
            else:
                with st.spinner("Requesting Cloud GPU (Takes ~20 seconds)..."):
                    try:
                        from agents.platform_managers import VisualCreatorAgent
                        agent = VisualCreatorAgent()
                        path = agent.generate_consistent_character(img_prompt)
                        st.success(f"Media generated: {path}")
                        st.image(path)
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab2:
        st.markdown("### Generate Video (HunyuanVideo)")
        st.markdown("Creates High-Quality videos without needing local GPUs. You can specify the style, background music, and Elina's language.")
        
        # New Video Customization Options
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            vid_style = st.selectbox("Video Style:", ["OPG (Organic Photorealistic)", "Cinematic (Standard)", "CGV (Computer Generated Vision/3D)"])
            vid_language = st.selectbox("Elina's Language:", ["Persian (فارسی)", "English", "German (Deutsch)", "Turkish (Türkçe)", "Arabic (العربية)"])
        with col_v2:
            vid_music = st.selectbox("Background Music Vibe:", ["Lo-Fi / Chillhop (Therapeutic)", "Acoustic Pop", "Cinematic Ambient", "Trending TikTok Beat", "None"])
            vid_camera = st.text_input("Camera Angle:", value="Medium Close-up, tracking shot")
            
        vid_lighting = st.text_input("Lighting:", value="Golden hour, cinematic lighting")
        vid_action = st.text_area("Action/Scene Description:", value="Elina walking gracefully down the street, looking at the camera, wearing neutral tones.")
        vid_voiceover = st.text_area("Voiceover Text (What Elina says):", value="سلام دخترا🤍 امروز درباره قدرت سکوت حرف می‌زنیم.")
        
        if st.button("Auto-Pilot 🤖 (Let Elina Decide)"):
            st.info("Letting the AI Director choose the best style, music, and shot based on current trends...")
            try:
                from agents.video_generator import DirectorAgent
                agent = DirectorAgent()
                # Run the full automated pipeline
                final_path = agent.run(topic="Psychology of minimal fashion", format_type="shorts")
                st.success(f"Auto-pilot video ready: {final_path}")
                if os.path.exists(final_path):
                    st.video(final_path)
            except Exception as e:
                st.error(f"Auto-Pilot Error: {e}")

        if st.button("Action! 🎬 (Custom Generate)"):
            with st.spinner(f"Rendering {vid_style} video with {vid_language} voiceover and {vid_music} music (This may take several minutes)..."):
                try:
                    from agents.video_generator import DirectorAgent
                    agent = DirectorAgent()
                    
                    scene = {
                        "camera": vid_camera,
                        "lighting": vid_lighting,
                        "action": vid_action,
                        "dialogue": vid_voiceover,
                        "language": vid_language,
                        "music": vid_music
                    }
                    
                    # 1. Generate Video
                    st.toast("Generating visual frames...")
                    video_raw_path = agent.generate_video_shot(scene, index=99, video_style=vid_style.split(" ")[0])
                    
                    # 2. Generate Voiceover
                    st.toast(f"Generating {vid_language} voiceover...")
                    audio_path = agent.generate_voiceover(scene["dialogue"], index=99)
                    
                    # 3. Compile (Sync video, voice, and BG music)
                    st.toast("Compiling Final Cut (Adding Music & Subtitles)...")
                    final_path = agent.compile_final_cut([{"audio": audio_path, "video": video_raw_path}])
                    
                    st.success(f"Video saved to: {final_path}")
                    if os.path.exists(final_path):
                        st.video(final_path)
                except Exception as e:
                    st.error(f"Error generating video: {e}")

elif page == "System Status":
    st.title("⚙️ System Status")
    
    st.write("**Environment Variables:**")
    env_vars = ["HF_TOKEN", "GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "BUFFER_API_TOKEN"]
    for var in env_vars:
        status = "✅ Set" if os.environ.get(var) else "❌ Missing"
        st.write(f"- `{var}`: {status}")
        
    st.markdown("---")
    st.markdown("### Start Web Dashboard Command")
    st.code("streamlit run dashboard/app.py", language="bash")
