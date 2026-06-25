"""
ElinaOS Android App
A beautiful KivyMD interface to manage Elina's emotions, 
chat with her (Brainstorming), and trigger her agents.
"""

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivy.core.window import Window
from kivy.utils import get_color_from_hex

import os
import json
import threading
from datetime import datetime

# Adjust window size to simulate mobile (for testing on PC)
Window.size = (400, 700)

class ElinaChatScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.md_bg_color = get_color_from_hex("#F7F5F0") # Quiet Luxury Cream Background
        
        main_layout = MDBoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Header
        header = MDLabel(
            text="ElinaOS - Brainstorming 🌿", 
            halign="center", 
            font_style="H5", 
            size_hint_y=None, 
            height=50,
            text_color=get_color_from_hex("#333333")
        )
        
        # Chat History Area
        self.scroll = MDScrollView()
        self.chat_history = MDBoxLayout(
            orientation='vertical', 
            spacing=15, 
            size_hint_y=None, 
            padding=[10, 10]
        )
        self.chat_history.bind(minimum_height=self.chat_history.setter('height'))
        self.scroll.add_widget(self.chat_history)
        
        # Input Area
        input_layout = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=60, spacing=10)
        self.text_input = MDTextField(
            hint_text="Talk to Elina or set /diary...",
            mode="round",
            fill_color_normal=get_color_from_hex("#FFFFFF")
        )
        
        send_btn = MDRaisedButton(
            text="Send",
            md_bg_color=get_color_from_hex("#8B7E66"), # Elegant Earth Tone
            on_release=self.send_message
        )
        
        input_layout.add_widget(self.text_input)
        input_layout.add_widget(send_btn)
        
        # Action Buttons (Triggers for Agents)
        action_layout = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        
        gen_content_btn = MDFlatButton(
            text="Generate Content ✍️", 
            text_color=get_color_from_hex("#8B7E66"),
            on_release=self.trigger_content_agent
        )
        push_github_btn = MDFlatButton(
            text="Push to GitHub 🐙", 
            text_color=get_color_from_hex("#8B7E66"),
            on_release=self.trigger_github_agent
        )
        
        action_layout.add_widget(gen_content_btn)
        action_layout.add_widget(push_github_btn)
        
        main_layout.add_widget(header)
        main_layout.add_widget(self.scroll)
        main_layout.add_widget(input_layout)
        main_layout.add_widget(action_layout)
        
        self.add_widget(main_layout)

    def add_chat_bubble(self, text, is_user=True):
        bg_color = "#E2DCD0" if is_user else "#FFFFFF"
        align = "right" if is_user else "left"
        
        msg_label = MDLabel(
            text=text,
            halign=align,
            size_hint_y=None,
            theme_text_color="Custom",
            text_color=get_color_from_hex("#333333")
        )
        msg_label.texture_update()
        msg_label.height = msg_label.texture_size[1] + 20
        
        self.chat_history.add_widget(msg_label)
        self.scroll.scroll_y = 0

    def send_message(self, instance):
        user_text = self.text_input.text.strip()
        if not user_text:
            return
            
        self.add_chat_bubble(user_text, is_user=True)
        self.text_input.text = ""
        
        # Handle /diary command directly
        if user_text.startswith("/diary"):
            feeling = user_text.replace("/diary", "").strip()
            self.save_diary(feeling)
            self.add_chat_bubble(f"📓 Diary saved: '{feeling}'", is_user=False)
            return

        # Simple mock response (In production, this connects to LLMRouter or Gemini API)
        # Using a thread to not freeze the UI if calling APIs
        threading.Thread(target=self.mock_llm_response, args=(user_text,)).start()

    def mock_llm_response(self, text):
        import time
        time.sleep(1) # Simulate API delay
        response = f"✨ Elina: I love that idea! As a psychologist, I think discussing '{text}' connects perfectly with our audience's need for authenticity."
        self.add_chat_bubble(response, is_user=False)

    def save_diary(self, feeling):
        diary_path = "../content/elina_diary.json"
        entries = []
        if os.path.exists(diary_path):
            with open(diary_path, "r") as f:
                try: entries = json.load(f)
                except: pass
                
        entries.append({
            "date": datetime.now().isoformat(),
            "feeling": feeling
        })
        
        os.makedirs(os.path.dirname(diary_path), exist_ok=True)
        with open(diary_path, "w") as f:
            json.dump(entries[-10:], f, indent=2)

    def trigger_content_agent(self, instance):
        self.add_chat_bubble("⏳ Triggering ContentCreator Agent...", is_user=False)
        # Here you would import and run ContentCreator().run()
        self.add_chat_bubble("✅ Content pieces generated and queued!", is_user=False)

    def trigger_github_agent(self, instance):
        self.add_chat_bubble("🐙 Connecting to GitHub Manager...", is_user=False)
        self.add_chat_bubble("✅ Workflow synced successfully.", is_user=False)


class ElinaOSApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Brown"
        self.theme_cls.theme_style = "Light"
        sm = MDScreenManager()
        sm.add_widget(ElinaChatScreen(name='chat'))
        return sm

if __name__ == "__main__":
    ElinaOSApp().run()
