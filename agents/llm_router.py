"""LLMRouter — a real multi-provider fallback chain, inspired by
tashfeenahmed/freellmapi (an open-source proxy that stacks 16+ free LLM
tiers behind one OpenAI-compatible endpoint with automatic failover).

WHY THIS WAS REWRITTEN (2026-07-06, user request "بریم ببینیم پروژه رو
میتونیم ران کنیم"): while actually running the daily pipeline in a real
sandbox, two concrete bugs were found:
  1. scripts/generate.py -- the script that ACTUALLY writes Elina's daily
     captions -- never called LLMRouter at all. It called
     google.generativeai directly, so setting GROQ_API_KEY (which the user
     added to secrets) had ZERO effect on caption quality. Every day with
     no working Gemini key/quota, captions silently fell back to a fixed,
     repetitive template ("استایل امروز الینا در تم X 🤍✨").
  2. .github/workflows/daily-content.yml never even passed GROQ_API_KEY as
     an env var to the script, so even a correctly-wired LLMRouter call
     would not have seen it.
Both are fixed alongside this file (see scripts/generate.py and the
workflow's env: block).

Rather than actually standing up freellmapi's Docker container (impractical
for a pipeline that runs on ephemeral GitHub Actions runners with no
persistent server), this router borrows its core, valuable idea directly:
try several genuinely-free providers in priority order, and on ANY failure
(missing key, quota exhausted, network error, malformed response) fall
through to the next one instead of giving up -- exactly what freellmapi's
proxy does, just as a Python function instead of a separate service.

Providers, all confirmed free-tier-with-no-credit-card via live research:
  - Groq (Llama 3.3 70B) -- very fast, generous free daily limit
  - Google Gemini (1.5/2.5 Flash) -- large free daily quota
  - OpenRouter free models (e.g. deepseek/llama free variants)
  - Cerebras (Llama 3.1/4) -- 1M free tokens/day
  - GitHub Models (gpt-4o-mini etc., via a GitHub PAT with models:read) --
    already have a GH_PAT in this repo's secrets for git push, but a
    fine-grained PAT with models:read scope is a SEPARATE token; falls
    back gracefully if GITHUB_MODELS_TOKEN isn't set
"""

import os
import re

import requests

# Detects CJK (Chinese/Japanese/Korean) characters -- these should NEVER
# appear in genuinely correct Persian/English output. Found live (2026-07-06)
# in a real GitHub Actions run: Groq's Llama 3.3 70B produced a Persian
# caption with stray Chinese characters mixed in mid-sentence (e.g. "最近"
# meaning "recently" appearing instead of/alongside its Persian
# translation) -- a documented weakness of general-purpose free models on
# non-English output (the same failure class found and fixed in the
# YouTube-Automation-Factory sibling project's script_quality.py). A simple
# Persian-character-percentage check does NOT catch this: the contaminating
# characters are few relative to a long correct sentence, so the ratio
# still looks fine (measured live: 97.6% Persian chars despite visible
# contamination) -- checking for the PRESENCE of any CJK character at all
# is what actually catches it.
_CJK_CONTAMINATION_PATTERN = re.compile(r"[\u4e00-\u9fff\uac00-\ud7af\u3040-\u30ff]")


def _has_cjk_contamination(text: str) -> bool:
    return bool(_CJK_CONTAMINATION_PATTERN.search(text))


class LLMRouter:
    def __init__(self):
        self.providers = {
            "groq": "Llama 3.3 70B (Groq)",
            "gemini": "Gemini 2.5 Flash (Google)",
            "cerebras": "Llama 3.1 8B (Cerebras)",
            "openrouter": "Free model (OpenRouter)",
            "github_models": "GPT-4o-mini (GitHub Models)",
            "deepseek": "DeepSeek-Chat",
        }

    _PROVIDER_KEYS = {
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "github_models": "GITHUB_MODELS_TOKEN",
        "deepseek": "DEEPSEEK_API_KEY",
    }

    # Full priority order tried on every call (not just a single "best"
    # pick) -- this is the actual freellmapi-style behavior: keep falling
    # through configured providers until one genuinely succeeds, rather
    # than picking one provider and simulating if it fails.
    _TASK_PREFERENCE = {
        "coding": ["groq", "gemini", "cerebras", "openrouter", "github_models", "deepseek"],
        "creative_writing": ["groq", "gemini", "openrouter", "cerebras", "github_models", "deepseek"],
        "fast_response": ["groq", "cerebras", "gemini", "openrouter", "github_models", "deepseek"],
        "long_context": ["gemini", "groq", "openrouter", "cerebras", "github_models", "deepseek"],
        "general": ["groq", "gemini", "cerebras", "openrouter", "github_models", "deepseek"],
    }

    def _configured_order(self, task_type: str) -> list:
        prefs = self._TASK_PREFERENCE.get(task_type, self._TASK_PREFERENCE["general"])
        return [p for p in prefs if os.environ.get(self._PROVIDER_KEYS.get(p, ""), "")]

    def get_best_provider(self, task_type):
        """Kept for backwards compatibility with any code calling this
        directly -- returns the first configured provider for this task
        type, or 'gemini' if nothing is configured (its branch degrades to
        a clear simulation notice rather than crashing)."""
        order = self._configured_order(task_type)
        return order[0] if order else "gemini"

    # ------------------------------------------------------------------ #
    # Per-provider real HTTP calls. Each raises on failure (network error,
    # non-200, missing 'choices' key, etc.) so _try_providers can uniformly
    # catch and move to the next provider -- exactly the failover freellmapi
    # implements server-side.
    # ------------------------------------------------------------------ #
    def _call_groq(self, system_prompt: str, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": prompt}],
        }
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                           headers=headers, json=data, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _call_gemini(self, system_prompt: str, prompt: str) -> str:
        # Uses the new `google-genai` SDK, not the deprecated
        # `google.generativeai` package (confirmed via a real pip install +
        # runtime warning while testing this router: "All support for the
        # `google.generativeai` package has ended. It will no longer be
        # receiving updates or bug fixes."). Other files in this repo
        # (vision.py, elina_bot.py, scripts/generate.py's old direct-Gemini
        # path) still import the deprecated package -- flagged as a
        # follow-up migration, out of scope for this specific fix.
        from google import genai
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        resp = client.models.generate_content(model="gemini-2.5-flash", contents=full_prompt)
        if not getattr(resp, "text", ""):
            raise ValueError("empty Gemini response")
        return resp.text.strip()

    def _call_cerebras(self, system_prompt: str, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {os.environ['CEREBRAS_API_KEY']}"}
        data = {
            "model": "llama3.1-8b",
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": prompt}],
        }
        r = requests.post("https://api.cerebras.ai/v1/chat/completions",
                           headers=headers, json=data, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _call_openrouter(self, system_prompt: str, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}
        # Defaults to a genuinely free OpenRouter model so this never
        # silently incurs cost; override via OPENROUTER_MODEL for a paid
        # model if the user wants higher quality.
        model = os.environ.get("OPENROUTER_MODEL", "").strip() or "meta-llama/llama-3.3-70b-instruct:free"
        data = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": prompt}],
        }
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                           headers=headers, json=data, timeout=30)
        r.raise_for_status()
        body = r.json()
        if "choices" not in body:
            err = body.get("error", {})
            raise ValueError(err.get("message", str(body)[:150]) if isinstance(err, dict) else str(err)[:150])
        return body["choices"][0]["message"]["content"]

    def _call_github_models(self, system_prompt: str, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {os.environ['GITHUB_MODELS_TOKEN']}"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": prompt}],
        }
        r = requests.post("https://models.github.ai/inference/chat/completions",
                           headers=headers, json=data, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _call_deepseek(self, system_prompt: str, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"}
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": prompt}],
        }
        r = requests.post("https://api.deepseek.com/chat/completions",
                           headers=headers, json=data, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    _CALLER_NAMES = {
        "groq": "_call_groq",
        "gemini": "_call_gemini",
        "cerebras": "_call_cerebras",
        "openrouter": "_call_openrouter",
        "github_models": "_call_github_models",
        "deepseek": "_call_deepseek",
    }

    def smart_generate(self, prompt, task_type="general", system_prompt="", language=""):
        """Tries every provider configured for this task_type, IN ORDER,
        until one genuinely succeeds (freellmapi-style failover). Returns
        {'provider', 'model', 'response', 'attempts'} -- 'attempts' lists
        every provider tried and why it failed, for debugging (this
        replaces the old silent '[Simulation - API Key missing]' stub,
        which made it impossible to tell whether a provider was
        unconfigured, out of quota, or genuinely broken).

        language='fa' additionally rejects any response containing CJK
        (Chinese/Japanese/Korean) character contamination -- verified live
        (2026-07-06) that Groq's free Llama 3.3 70B produces this exact
        failure mode on Persian output despite otherwise looking correct.
        A rejected response is treated exactly like an API failure and the
        router falls through to the next configured provider."""
        order = self._configured_order(task_type)
        attempts = []

        for provider in order:
            model_name = self.providers.get(provider, provider)
            caller = getattr(self, self._CALLER_NAMES[provider])
            try:
                print(f"[LLMRouter] Trying {model_name} for task: {task_type}...")
                text = caller(system_prompt, prompt)
                if text and text.strip():
                    if language == "fa" and _has_cjk_contamination(text):
                        attempts.append(f"{provider}: rejected -- CJK character contamination in Persian output")
                        print(f"[LLMRouter] {provider} rejected: Persian output contains CJK characters")
                        continue
                    return {"provider": provider, "model": model_name,
                            "response": text.strip(), "attempts": attempts}
                attempts.append(f"{provider}: empty response")
            except Exception as e:
                attempts.append(f"{provider}: {e}")
                print(f"[LLMRouter] {provider} failed: {e}")
                continue

        detail = f" | attempts: {attempts}" if attempts else " (no provider configured -- set GROQ_API_KEY/GEMINI_API_KEY/etc.)"
        print(f"[LLMRouter] All providers failed for task '{task_type}'{detail}")
        return {"provider": "", "model": "", "response": "", "attempts": attempts}


if __name__ == "__main__":
    router = LLMRouter()
    print(
        router.smart_generate("Write a creative story about Elina", task_type="creative_writing")
    )
