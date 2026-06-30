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
page = st.sidebar.radio("Navigate", ["Home", "Diary & Emotions", "Content Manager", "Media Generator", "System Status"])

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
    st.markdown("Trigger image and video generation using Hugging Face Cloud GPUs.")
    
    if st.button("Generate Consistent Image (InstantID)"):
        st.info("Requesting Cloud GPU... (Requires HF_TOKEN)")
        try:
            from agents.platform_managers import VisualCreatorAgent
            agent = VisualCreatorAgent()
            path = agent.generate_consistent_character("wearing a cozy beige sweater, drinking tea")
            st.success(f"Media generated: {path}")
        except Exception as e:
            st.error(f"Error: {e}")

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
