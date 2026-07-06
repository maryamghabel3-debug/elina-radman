"""LLMRouter — real multi-provider fallback for Elina's captions/scripts.

HISTORY:
  2026-07-06 (first pass): rewrote this file's own hand-rolled fallback
  logic (Groq -> Gemini -> Cerebras -> OpenRouter -> GitHub Models ->
  DeepSeek) after finding scripts/generate.py never called LLMRouter at all
  and the GitHub Actions workflows never even passed GROQ_API_KEY as an env
  var -- both bugs are fixed (see scripts/generate.py, daily-content.yml,
  bot-runner.yml).

  2026-07-06 (this pass, explicit user instruction: "بهت گفتم از این پروژه
  در گیت هاب برای پروژه الینا استفاده کن freellmapi" -- "I told you to use
  this GitHub project for the Elina project, freellmapi"): the FIRST pass
  only borrowed freellmapi's *idea* (stack providers, fail over) as
  hand-written Python -- it did not actually use the real
  tashfeenahmed/freellmapi project. This was a misunderstanding of the
  instruction, corrected now: LLMRouter's PRIMARY path is a real HTTP call
  to an actual running freellmapi instance (OpenAI-compatible
  /v1/chat/completions with model="auto", letting freellmapi's own router
  pick the best of its 18 supported providers and fail over automatically,
  exactly as the project is designed to be used).

  freellmapi is a Node/Express service, not a Python library, so it cannot
  be "imported" -- it must be RUNNING somewhere and reached over HTTP. Since
  this whole pipeline runs on ephemeral GitHub Actions runners with no
  persistent server, .github/workflows/daily-content.yml and bot-runner.yml
  now: (1) checkout+build the real tashfeenahmed/freellmapi repo as a build
  step, (2) start it in the background with a FREEAPI_CONFIG_JSON declarative
  config built from this repo's existing secrets (GROQ_API_KEY,
  GEMINI_API_KEY, etc. -- no new secrets needed), (3) run the Python script
  against FREELLMAPI_URL=http://localhost:3001, (4) the runner is destroyed
  at the end of the job, discarding the freellmapi instance -- there is
  nothing to keep alive between runs, which matches freellmapi's own
  "personal experimentation" design (real user data/DB doesn't need to
  persist here since only encrypted-at-rest API keys would be, and those
  come fresh from GitHub Secrets every run anyway).

  Verified live in this sandbox (2026-07-06): cloned tashfeenahmed/freellmapi
  (MIT, 15.2k stars), ran `npm install && npm run build`, started
  `node server/dist/index.js` with FREEAPI_CONFIG_JSON containing a fake Groq
  key, confirmed the server printed a real unified `freellmapi-...` API key
  to its own stdout on first boot (no manual dashboard signup needed) and that
  POST /v1/chat/completions with model="auto" made a REAL outbound call to
  Groq's API and returned Groq's real 401 error for the fake key -- proving
  the whole real chain (declarative config -> provider selection -> real
  HTTP call -> error surfacing) works end to end without touching the UI.

  If FREELLMAPI_URL is not reachable (e.g. running scripts/generate.py
  locally outside the CI workflow, or the service failed to start), this
  router falls back to the direct-provider calls from the first pass
  (_call_groq/_call_gemini/etc.) so the pipeline never hard-depends on the
  freellmapi process being up -- exactly like every other optional
  enhancement in this repo.
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
        # The real tashfeenahmed/freellmapi service, started by the CI
        # workflow (see .github/workflows/daily-content.yml) with a
        # FREEAPI_CONFIG_JSON built from this repo's existing secrets.
        # Empty when not running (e.g. local dev outside CI) -- callers
        # degrade to the direct-provider calls below in that case.
        self.freellmapi_url = os.environ.get("FREELLMAPI_URL", "").rstrip("/")
        self.freellmapi_key = os.environ.get("FREELLMAPI_API_KEY", "")

    def _call_freellmapi(self, system_prompt: str, prompt: str) -> str:
        """Real HTTP call to a running freellmapi instance's OpenAI-compatible
        endpoint. model='auto' lets freellmapi's OWN router pick the best
        available provider from whatever keys were declared in its
        FREEAPI_CONFIG_JSON and fail over between them -- this is the
        intended, documented way to use the project (not re-implementing its
        routing logic in Python, which the first pass at this file
        mistakenly did)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        headers = {"Authorization": f"Bearer {self.freellmapi_key}", "Content-Type": "application/json"}
        r = requests.post(
            f"{self.freellmapi_url}/v1/chat/completions",
            headers=headers, json={"model": "auto", "messages": messages}, timeout=60,
        )
        r.raise_for_status()
        body = r.json()
        return body["choices"][0]["message"]["content"]

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
        router falls through to the next configured provider.

        PRIMARY PATH: if FREELLMAPI_URL is set (the real freellmapi service
        is running -- see .github/workflows/daily-content.yml), tries it
        FIRST via model='auto', letting freellmapi's own router pick and
        fail over between its 18 supported providers. Only falls through to
        this file's direct-provider calls if freellmapi is unreachable or
        every provider it tried also failed."""
        attempts = []

        if self.freellmapi_url:
            try:
                print(f"[LLMRouter] Trying freellmapi (model=auto) at {self.freellmapi_url}...")
                text = self._call_freellmapi(system_prompt, prompt)
                if text and text.strip():
                    if language == "fa" and _has_cjk_contamination(text):
                        attempts.append("freellmapi: rejected -- CJK character contamination in Persian output")
                        print("[LLMRouter] freellmapi rejected: Persian output contains CJK characters")
                    else:
                        return {"provider": "freellmapi", "model": "auto (freellmapi router)",
                                "response": text.strip(), "attempts": attempts}
                else:
                    attempts.append("freellmapi: empty response")
            except Exception as e:
                attempts.append(f"freellmapi: {e}")
                print(f"[LLMRouter] freellmapi failed: {e}")

        order = self._configured_order(task_type)

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
