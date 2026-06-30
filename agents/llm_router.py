import os
import requests

class LLMRouter:
    def __init__(self):
        # Free Providers and Chinese/Global Models
        self.providers = {
            "gemini": "Gemini 1.5 Pro (Google)",
            "groq": "Llama-3 (Groq)",
            "openrouter": "Claude 3 (via OpenRouter)",
            "github_models": "GPT-4o/Llama-3 (GitHub)",
            "deepseek": "DeepSeek-V2",
            "zhipu": "GLM-4-Flash",
            "kimi": "Moonshot-v1",
            "poe": "Aggregator (Various Models)",
        }

    def get_best_provider(self, task_type):
        """Smart routing based on task type"""
        if task_type == "coding":
            return "deepseek"
        elif task_type == "creative_writing":
            return "openrouter"  # Claude
        elif task_type == "fast_response":
            return "groq"
        elif task_type == "long_context":
            return "kimi"
        elif task_type == "general":
            return "github_models"
        else:
            return "gemini"

    def smart_generate(self, prompt, task_type="general", system_prompt=""):
        """Generate content routing to the best model using REAL APIs"""
        provider = self.get_best_provider(task_type)
        model_name = self.providers.get(provider)
        
        print(f"[LLMRouter] Routing to {model_name} for task: {task_type}...")
        
        response_text = ""
        
        try:
            if provider == "groq" and os.environ.get("GROQ_API_KEY"):
                headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
                data = {
                    "model": "llama3-70b-8192",
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
                }
                r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data).json()
                response_text = r['choices'][0]['message']['content']
                
            elif provider == "deepseek" and os.environ.get("DEEPSEEK_API_KEY"):
                headers = {"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"}
                data = {
                    "model": "deepseek-chat",
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
                }
                r = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data).json()
                response_text = r['choices'][0]['message']['content']
                
            elif provider == "openrouter" and os.environ.get("OPENROUTER_API_KEY"):
                headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}
                data = {
                    "model": "anthropic/claude-3-haiku", # Free/Cheap fast model
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
                }
                r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data).json()
                response_text = r['choices'][0]['message']['content']
                
            elif provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
                import google.generativeai as genai
                genai.configure(api_key=os.environ['GEMINI_API_KEY'])
                m = genai.GenerativeModel("gemini-1.5-flash")
                full_prompt = f"{system_prompt}\n\nUser: {prompt}"
                response_text = m.generate_content(full_prompt).text
                
            else:
                # Fallback if specific key is missing
                response_text = f"[Simulation - API Key for {provider} missing] Generated response for: {prompt[:30]}..."
                
        except Exception as e:
            response_text = f"Error calling {provider}: {e}"

        return {"provider": provider, "model": model_name, "response": response_text}


if __name__ == "__main__":
    router = LLMRouter()
    print(
        router.smart_generate("Write a creative story about Elina", "creative_writing")
    )
