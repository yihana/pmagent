# server/utils/llm_factory.py
from __future__ import annotations
import os
import asyncio
import logging
import json
from typing import Any, Dict, Optional

# load .env automatically if dotenv installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger("llm.factory")
logger.setLevel(os.getenv("LLM_FACTORY_LOGLEVEL", "INFO"))

# --- Environment mapping: support AOAI_* (Azure OpenAI style) and fallback OPENAI_/AZURE_ ---
# AOAI_* are the variables you provided; map them to internal names
AOAI_API_KEY = os.getenv("AOAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
AOAI_DEPLOY = os.getenv("AOAI_DEPLOY_GPT4O") or os.getenv("AOAI_DEPLOY_GPT5O") or os.getenv("AOAI_DEPLOY")
AOAI_ENDPOINT = os.getenv("AOAI_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
AOAI_API_VERSION = os.getenv("AOAI_API_VERSION") or os.getenv("AZURE_OPENAI_API_VERSION") or os.getenv("AZURE_API_VERSION")

# Standard OpenAI vars (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or os.getenv("AOAI_DEPLOY_GPT4O") or os.getenv("AOAI_DEPLOY_GPT5O") or os.getenv("AOAI_DEPLOY")

# other helpful envs
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "").lower()  # explicit override if set
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE") or 0.0)

# optional imports
_openai = None
try:
    import openai as _openai  # openai package supports Azure OpenAI if configured
except Exception:
    _openai = None

# ---- Utilities & wrappers ----
def _to_plain_text(messages_or_prompt: Any) -> str:
    if messages_or_prompt is None:
        return ""
    if isinstance(messages_or_prompt, str):
        return messages_or_prompt
    if isinstance(messages_or_prompt, (list, tuple)):
        parts = []
        for m in messages_or_prompt:
            if isinstance(m, dict):
                parts.append(str(m.get("content") or m.get("text") or ""))
            else:
                parts.append(str(m))
        return "\n".join(parts)
    try:
        return str(messages_or_prompt)
    except Exception:
        return ""

class MockLLM:
    def __init__(self, temperature: float = 0.0):
        self.temperature = temperature

    def generate(self, messages_or_prompt: Any) -> Dict[str, Any]:
        text = _to_plain_text(messages_or_prompt)
        return {"choices": [{"message": {"content": f"[MOCK] {text}"}}], "model": "mock"}

    async def agenerate(self, messages_or_prompt: Any) -> Dict[str, Any]:
        return await asyncio.to_thread(self.generate, messages_or_prompt)

    def __call__(self, prompt: Any) -> Dict[str, Any]:
        return self.generate(prompt)

class OpenAIWrapper:
    """
    Minimal wrapper for openai.ChatCompletion that supports both OpenAI and Azure OpenAI settings.
    Exposes .generate() and .agenerate() used by pipeline.
    """
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        azure: bool = False,
        azure_base: Optional[str] = None,
        deployment: Optional[str] = None,
        api_version: Optional[str] = None,
        temperature: float = 0.0,
    ):
        if _openai is None:
            raise RuntimeError("openai package not installed in environment")
        self.model = model
        self.temperature = temperature
        self.azure = azure
        self.deployment = deployment or model
        # configure openai client for azure if requested
        if api_key:
            _openai.api_key = api_key
        if azure:
            if azure_base:
                _openai.api_type = "azure"
                _openai.api_base = azure_base.rstrip("/")
            if api_version:
                _openai.api_version = api_version

    def _format_messages(self, messages_or_prompt: Any):
        if isinstance(messages_or_prompt, str):
            return [{"role": "user", "content": messages_or_prompt}]
        if isinstance(messages_or_prompt, (list, tuple)):
            out = []
            for m in messages_or_prompt:
                if isinstance(m, dict):
                    out.append({"role": m.get("role", "user"), "content": m.get("content") or m.get("text") or ""})
                else:
                    out.append({"role": "user", "content": str(m)})
            return out
        return [{"role": "user", "content": str(messages_or_prompt)}]

    def generate(self, messages_or_prompt: Any) -> Dict[str, Any]:
        msgs = self._format_messages(messages_or_prompt)
        if self.azure:
            # Azure uses engine/deployment name as 'engine' or 'deployment' depending on SDK
            # openai.ChatCompletion.create supports 'engine' for azure (older SDK); however
            # using 'deployment' key is safer for newer versions.
            resp = _openai.ChatCompletion.create(
                engine=self.deployment,
                messages=msgs,
                temperature=self.temperature,
            )
        else:
            resp = _openai.ChatCompletion.create(
                model=self.model,
                messages=msgs,
                temperature=self.temperature,
            )
        return resp

    async def agenerate(self, messages_or_prompt: Any) -> Dict[str, Any]:
        return await asyncio.to_thread(self.generate, messages_or_prompt)

    def __call__(self, prompt: Any) -> Dict[str, Any]:
        return self.generate(prompt)

# ---- Auto-detect provider logic ----
def _auto_detect_provider() -> str:
    # explicit override
    if LLM_PROVIDER:
        return LLM_PROVIDER
    # AOAI (Azure OpenAI) presence -> azure
    if AOAI_API_KEY and AOAI_ENDPOINT:
        return "azure"
    # openai api key -> openai
    if OPENAI_API_KEY:
        return "openai"
    return "mock"

def get_llm() -> Any:
    """
    Return an LLM-like object with .generate() and optional .agenerate().
    Supports AOAI_ env (preferred), OPENAI_ env, or returns MockLLM.
    """
    provider = _auto_detect_provider()
    logger.info("[LLM_FACTORY] auto provider=%s model=%s", provider, OPENAI_MODEL or AOAI_DEPLOY)

    # Azure / AOAI preferred if AOAI vars present
    if provider == "azure" and _openai is not None:
        try:
            model_name = AOAI_DEPLOY or OPENAI_MODEL or "gpt-5o"
            return OpenAIWrapper(
                model=model_name,
                api_key=AOAI_API_KEY,
                azure=True,
                azure_base=AOAI_ENDPOINT,
                deployment=AOAI_DEPLOY or model_name,
                api_version=AOAI_API_VERSION,
                temperature=LLM_TEMPERATURE,
            )
        except Exception as e:
            logger.exception("[LLM_FACTORY] azure init failed: %s", e)

    # Fallback openai
    if provider == "openai" and _openai is not None:
        try:
            model_name = OPENAI_MODEL or "gpt-5o"
            return OpenAIWrapper(
                model=model_name,
                api_key=OPENAI_API_KEY,
                azure=False,
                temperature=LLM_TEMPERATURE,
            )
        except Exception as e:
            logger.exception("[LLM_FACTORY] openai init failed: %s", e)

    logger.warning("[LLM_FACTORY] No real LLM configured - returning MockLLM")
    return MockLLM(temperature=LLM_TEMPERATURE)

# ---- small helper: normalize LLM response into string content ----
def normalize_llm_response(resp: Any) -> str:
    """
    Convert common SDK/shape responses into plain text content.
    Useful to avoid .content/.text attribute errors.
    """
    try:
        # dict-like (openai style)
        if isinstance(resp, dict):
            # openai ChatCompletion response
            choices = resp.get("choices")
            if choices and isinstance(choices, (list, tuple)) and len(choices) > 0:
                first = choices[0]
                # new shape: {'message': {'content': '...'}}
                if isinstance(first, dict) and first.get("message"):
                    content = first["message"].get("content") or first["message"].get("text")
                    if content:
                        return content
                # older openai shape: {'text': '...'}
                if isinstance(first, dict) and first.get("text"):
                    return first.get("text")
            # langchain style: {'generations': [[{'text':'...'}]]}
            gens = resp.get("generations") or resp.get("generation")
            if gens:
                try:
                    g0 = gens[0][0]
                    if isinstance(g0, dict) and g0.get("text"):
                        return g0.get("text")
                except Exception:
                    pass
            # fallback stringify
            try:
                return json.dumps(resp, ensure_ascii=False)
            except Exception:
                return str(resp)

        # object with .content or .text
        if hasattr(resp, "content"):
            try:
                return resp.content
            except Exception:
                pass
        if hasattr(resp, "text"):
            try:
                return resp.text
            except Exception:
                pass

        if isinstance(resp, str):
            return resp

        return str(resp)
    except Exception as e:
        logger.exception("[LLM_FACTORY] normalize error: %s", e)
        try:
            return str(resp)
        except Exception:
            return ""
