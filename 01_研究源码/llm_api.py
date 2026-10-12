"""llm_api.py — LLM API 调用（Claude 已修复：无 extended thinking）"""
import json
import re
import time
import requests
from config import LLM_PROVIDERS


def _classify_error(status_code=None, exception=None):
    if status_code in (401, 402, 403):
        return "authentication" if status_code != 402 else "billing", False
    if status_code == 429:
        return "rate_limit", True
    if status_code is not None and status_code >= 500:
        return "server", True
    if isinstance(exception, (TimeoutError, ConnectionError)):
        return "transport", True
    if exception is not None:
        name = type(exception).__name__.lower()
        if any(token in name for token in ("timeout", "connection", "incomplete", "disconnect")):
            return "transport", True
    return "api", False


def _err(msg, *, error_type="api", retryable=False, secret=None):
    safe = str(msg)
    if secret:
        safe = safe.replace(str(secret), "***")
    return {
        "reasoning": "",
        "answer": "",
        "usage": {},
        "error": safe,
        "error_type": error_type,
        "retryable": bool(retryable),
    }


def _ok(*, reasoning="", answer="", usage=None, model=None, finish_reason=None, request_mode=None):
    return {
        "reasoning": reasoning,
        "answer": answer,
        "usage": usage or {},
        "model": model,
        "finish_reason": finish_reason,
        "request_mode": request_mode,
        "error": None,
        "error_type": None,
        "retryable": False,
    }


def call_llm(provider, api_key, model, messages,
             session=None, temperature=0.1, reasoning_effort=None):
    if provider not in LLM_PROVIDERS:
        return _err("Unknown API provider", error_type="configuration")
    cfg = LLM_PROVIDERS[provider]
    base = cfg["base"]
    sess = session or requests.Session()

    if provider == "Google Gemini":
        return _call_gemini(api_key, model, messages, sess, temperature)
    if provider == "Anthropic Claude":
        return _call_claude(api_key, model, messages, sess, temperature)
    if provider == "MiniMax":
        return _call_minimax(api_key, model, messages, sess, temperature)

    # ── OpenAI 兼容（Poe / DeepSeek / OpenAI / Qwen / Doubao）──
    try:
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": temperature,
            "stream": False,
        }
        request_mode = "provider_default"
        if provider == "DeepSeek":
            # A decision needs a short JSON answer, not a reasoning-token budget.
            body["thinking"] = {"type": "disabled"}
            body["response_format"] = {"type": "json_object"}
            request_mode = "non_thinking_json"
        if provider == "Poe" and any(
                kw in model.lower() for kw in ["claude-opus", "claude-sonnet", "claude-haiku"]
        ):
            body["thinking"] = {"type": "disabled"}

        resp = sess.post(
            f"{base}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json=body, timeout=60,
        )
        raw = resp.text
        try:
            data = resp.json()
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    error_type, retryable = _classify_error(resp.status_code)
                    return _err(
                        f"JSON解析失败(HTTP {resp.status_code}): {raw[:300]}",
                        error_type=error_type, retryable=retryable, secret=api_key,
                    )
            else:
                error_type, retryable = _classify_error(resp.status_code)
                return _err(
                    f"非JSON响应(HTTP {resp.status_code}): {raw[:300]}",
                    error_type=error_type, retryable=retryable, secret=api_key,
                )

        if resp.status_code >= 400 or (isinstance(data, dict) and "error" in data):
            error_type, retryable = _classify_error(resp.status_code)
            return _err(
                str(data), error_type=error_type,
                retryable=retryable, secret=api_key,
            )

        choice = data["choices"][0]["message"]
        rf = cfg.get("reasoning_field")
        reasoning = (choice.get(rf, "") or "") if rf else ""
        answer = choice.get("content", "") or ""
        return _ok(
            reasoning=reasoning,
            answer=answer,
            usage=data.get("usage", {}),
            model=data.get("model", model),
            finish_reason=data["choices"][0].get("finish_reason"),
            request_mode=request_mode,
        )
    except Exception as e:
        error_type, retryable = _classify_error(exception=e)
        return _err(
            str(e), error_type=error_type, retryable=retryable, secret=api_key
        )


# ─────────────────────────────────────────
# Anthropic Claude（已修复：不发 thinking）
# ─────────────────────────────────────────
def _call_claude(api_key, model, messages, sess, temperature=0.1):
    try:
        sys_txt, conv = "", []
        for m in messages:
            if m["role"] == "system":
                sys_txt = m["content"]
            else:
                conv.append({"role": m["role"], "content": m["content"]})

        body = {
            "model": model,
            "max_tokens": 5000,
            "messages": conv,
            "temperature": temperature,
        }
        if sys_txt:
            body["system"] = sys_txt

        resp = sess.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body, timeout=120,
        )
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            error_type, retryable = _classify_error(resp.status_code)
            return _err(str(data), error_type=error_type,
                        retryable=retryable, secret=api_key)

        answer = ""
        for blk in data.get("content", []):
            if blk.get("type") == "text":
                answer += blk.get("text", "")
        return _ok(answer=answer.strip(), usage=data.get("usage", {}), model=model)
    except Exception as e:
        error_type, retryable = _classify_error(exception=e)
        return _err(str(e), error_type=error_type,
                    retryable=retryable, secret=api_key)


# ─────────────────────────────────────────
# Google Gemini
# ─────────────────────────────────────────
def _call_gemini(api_key, model, messages, sess, temperature=0.1):
    try:
        cfg = LLM_PROVIDERS["Google Gemini"]
        is_thinking = model in cfg.get("thinking_models", set())

        sys_text, contents = "", []
        for m in messages:
            if m["role"] == "system":
                sys_text = m["content"]
            else:
                role = "user" if m["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m["content"]}]})

        gen_cfg = {"temperature": temperature, "maxOutputTokens": 800}
        if is_thinking:
            gen_cfg["thinkingConfig"] = {"thinkingBudget": 2048}

        body = {"contents": contents, "generationConfig": gen_cfg}
        if sys_text:
            body["systemInstruction"] = {"parts": [{"text": sys_text}]}

        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{model}:generateContent?key={api_key}")
        resp = sess.post(url, json=body, timeout=120,
                         headers={"Content-Type": "application/json"})
        data = resp.json()

        if resp.status_code >= 400 or "error" in data:
            error_type, retryable = _classify_error(resp.status_code)
            return _err(str(data), error_type=error_type,
                        retryable=retryable, secret=api_key)

        candidates = data.get("candidates", [])
        if not candidates:
            return _err("Gemini 无候选结果")

        parts = candidates[0].get("content", {}).get("parts", [])
        reasoning, answer = "", ""
        for part in parts:
            if part.get("thought"):
                reasoning += part.get("text", "")
            else:
                answer += part.get("text", "")

        usage = data.get("usageMetadata", {})
        return _ok(
            reasoning=reasoning.strip(), answer=answer.strip(),
            usage=usage, model=model,
        )
    except Exception as e:
        error_type, retryable = _classify_error(exception=e)
        return _err(str(e), error_type=error_type,
                    retryable=retryable, secret=api_key)


# ─────────────────────────────────────────
# MiniMax
# ─────────────────────────────────────────
def _call_minimax(api_key, model, messages, sess, temperature=0.1):
    try:
        resp = sess.post(
            "https://api.minimax.chat/v1/text/chatcompletion_v2",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": model, "messages": messages,
                  "max_tokens": 800, "temperature": temperature},
            timeout=60,
        )
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            error_type, retryable = _classify_error(resp.status_code)
            return _err(str(data), error_type=error_type,
                        retryable=retryable, secret=api_key)
        if data.get("base_resp", {}).get("status_code", 0) != 0:
            return _err(data.get("base_resp", {}).get("status_msg", "Unknown"),
                        secret=api_key)
        answer = (data.get("choices", [{}])[0]
                  .get("message", {}).get("content", ""))
        return _ok(answer=answer, usage=data.get("usage", {}), model=model)
    except Exception as e:
        error_type, retryable = _classify_error(exception=e)
        return _err(str(e), error_type=error_type,
                    retryable=retryable, secret=api_key)


# ─────────────────────────────────────────
# 连接预检
# ─────────────────────────────────────────
def test_api_connection(provider, api_key, model, session=None):
    if not api_key or not api_key.strip():
        return False, "未提供 API Key", 0
    messages = [{"role": "user", "content": "Reply with exactly one word: OK"}]
    t0 = time.time()
    result = call_llm(provider, api_key, model, messages, session, temperature=0.0)
    latency = int((time.time() - t0) * 1000)
    if result["error"]:
        return False, f"{result['error']}", latency
    if result["answer"] and len(result["answer"].strip()) > 0:
        short = result["answer"].strip()[:40]
        return True, f"模型响应: \"{short}\" ({latency}ms)", latency
    return False, "API 无响应内容", latency
