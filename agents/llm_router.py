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

    # Which env var holds each provider's API key.
    _PROVIDER_KEYS = {
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }

    # Preferred provider per task type (first choice), best-quality first.
    _TASK_PREFERENCE = {
        "coding": ["deepseek", "gemini", "openrouter", "groq"],
        "creative_writing": ["openrouter", "gemini", "groq", "deepseek"],
        "fast_response": ["groq", "gemini", "openrouter", "deepseek"],
        "long_context": ["gemini", "openrouter", "groq", "deepseek"],
        "general": ["gemini", "openrouter", "groq", "deepseek"],
    }

    def get_best_provider(self, task_type):
        """Route to the best provider WHOSE API KEY IS ACTUALLY CONFIGURED.

        The old version always sent creative_writing to OpenRouter/Claude, so a
        user who only set GEMINI_API_KEY got the simulation stub (and captions
        fell back to templates). Now we pick the first preferred provider that
        has a key set, defaulting to Gemini.
        """
        prefs = self._TASK_PREFERENCE.get(task_type, ["gemini", "openrouter", "groq", "deepseek"])
        for provider in prefs:
            key_env = self._PROVIDER_KEYS.get(provider)
            if key_env and os.environ.get(key_env):
                return provider
        # Nothing configured -> Gemini (its branch will simulate if key missing)
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
                # Model is configurable via OPENROUTER_MODEL so you can switch to
                # a free model (e.g. "meta-llama/llama-3.1-8b-instruct:free") to
                # stay $0, or a stronger paid Claude model for best captions.
                model = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3-haiku")
                data = {
                    "model": model,
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
                }
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers, json=data, timeout=30,
                ).json()
                if "choices" in r:
                    response_text = r["choices"][0]["message"]["content"]
                else:
                    # Surface the API error (e.g. no credits) instead of crashing
                    err = r.get("error", {})
                    msg = err.get("message", str(r)[:150]) if isinstance(err, dict) else str(err)[:150]
                    response_text = f"Error calling openrouter: {msg}"
                
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
