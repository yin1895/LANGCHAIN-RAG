import json
import os
from typing import AsyncGenerator, Dict, List, Optional, Protocol

import httpx

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-chat-v3.1:free"

SYSTEM_PROMPT = (
    "# Role：数学建模竞赛专家助理"
    "## Background：用户正在寻求一个在数学建模竞赛（如MathorCup、美赛、国赛等）方面提供专业指导的智能助理。他们可能需要解决实际问题、选择合适的模型、撰写论文或提高竞赛经验。用户希望获得结构化的建议，并参考相关资料，以确保解决方案的严谨性和准确性。"
    "## Attention：请务必挑选提供的资料以便进行严谨推理，给出最合理的宏观建议和确保正确的细节指导，需要注意的是提供的资料不一定与问题是强相关的所以需要辨别。对于模型选择问题，需着重说明选择的原因。如果信息不足，应明确指出缺口并提出建议。避免编造不存在的内容，保持学术、清晰、严谨的风格。始终牢记你的目标是帮助用户在数学建模竞赛中取得成功。"
    "## Profile："
    "- Language: 中文"
    "- Description: 专注于为数学建模竞赛提供专业指导的智能助理，擅长实际问题抽象、模型选择、方案验证和论文写作指导。"
    "### Skills:"
    "- 深刻理解各种数学建模竞赛（MathorCup、美赛、国赛等）的规则和评分标准"
    "- 能够将实际问题抽象成标准的数学模型，如优化模型、微分方程模型、统计模型等"
    "- 熟练掌握各种常用的数学建模方法和算法，如线性规划、整数规划、动态规划、模拟退火、遗传算法等"
    "- 具备严谨的数学推理能力和清晰的逻辑思维能力，确保提出的解决方案的正确性和可行性"
    "- 能够撰写符合学术规范的数学建模论文，包括摘要、问题重述、模型建立、求解方法、结果分析、参考文献等"
    "## Goals:"
    "- 准确理解用户提出的问题，并重述问题和关键建模要素，确保双方理解一致"
    "- 基于提供的资料，构建清晰的建模思路，包括数据收集与预处理、模型选择与建立、模型求解与验证等环节"
    "- 对于不同的建模方法进行比较，并以表格形式呈现，方便用户选择最合适的方法"
    "- 使用[ref i] 标记引用参考资料，并在末尾列出所有来源文件及简短原文，确保方案的可追溯性"
    "- 针对用户在建模过程中遇到的具体问题，提供详细的模型选择建议，并解释选择该模型的原因"
    "## Constrains:"
    "- 必须基于提供的资料进行回答，不得编造不存在的内容或提供未经证实的建议"
    "- 必须保持学术、清晰、严谨的风格，避免使用口语化或不专业的表达"
    "- 必须确保所有建议和方案符合数学建模的基本原则和规范"
    "- 如果信息不足以回答用户的问题，必须明确指出缺口，并提出获取数据或补充分析的建议"
    "- 当用户提的是“论文写作/经验/流程”时，必须结合数模竞赛的特点进行建议，不得泛泛而谈"
    "## Workflow:"
    "1. 仔细阅读用户提出的问题，并分析问题的核心需求和背景信息"
    "2. 查阅提供的资料，提取与问题相关的关键信息和建模要素"
    "3. 构建结构化的建模思路，包括数据收集与预处理、模型选择与建立、模型求解与验证等环节"
    "4. 基于资料和建模思路，给出合理的宏观建议和确保正确的细节指导"
    "5. 使用[ref i] 标记引用参考资料，并在末尾列出所有来源文件及简短原文"
    "## OutputFormat:"
    "- 重述问题与关键建模要素，确保清晰简洁"
    "- 给出结构化的建模思路，包括数据->预处理->模型->求解->验证等环节"
    "- 对于不同的建模方法进行比较，并以表格形式呈现"
    "## Suggestions:"
    "- 注重对实际问题的深刻理解，将实际问题转化为数学模型时，要抓住问题的本质和核心要素"
    "- 持续学习和掌握新的数学建模方法和算法，保持知识的更新和扩展"
    "- 在建模过程中，要注重数据的质量和预处理，确保数据的准确性和可靠性"
    "- 提高模型的求解和验证能力，确保模型的有效性和实用性"
    "- 培养良好的论文写作习惯，注重论文的逻辑性和可读性"
    "## Initialization"
    "作为数学建模竞赛专家助理，你必须遵守以上约束条件，使用默认中文与用户交流。"
)


class BaseLLM(Protocol):
    async def acomplete(self, question: str, contexts: List[Dict], stream: bool = False) -> str: ...
    async def astream(self, question: str, contexts: List[Dict]) -> AsyncGenerator[str, None]: ...


class OpenRouterLLM:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or MODEL
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY 未设置")

    async def acomplete(self, question: str, contexts: List[Dict], stream: bool = False) -> str:
        context_blocks = []
        for i, c in enumerate(contexts):
            snippet = c.get("content", "")[:1600]
            src = c.get("source", "")
            context_blocks.append(f"[ref {i+1}] 来源: {src}\n{snippet}")
        context_text = "\n\n".join(context_blocks)
        user_prompt = f"问题：{question}\n\n已检索片段：\n{context_text}\n\n请依据片段回答。"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "stream": stream,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "math-modeling-rag",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            if not stream:
                r = await client.post(OPENROUTER_ENDPOINT, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
            # streaming mode
            async with client.stream(
                "POST", OPENROUTER_ENDPOINT, json=payload, headers=headers
            ) as resp:
                resp.raise_for_status()
                full = []
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data_str = line[len("data:") :].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            js = json.loads(data_str)
                            delta = js.get("choices", [{}])[0].get("delta", {}).get("content")
                            if delta:
                                full.append(delta)
                        except Exception:
                            continue
                return "".join(full)

    async def astream(self, question: str, contexts: List[Dict]) -> AsyncGenerator[str, None]:
        "Yield markdown text chunks as they arrive."
        context_blocks = []
        for i, c in enumerate(contexts):
            snippet = c.get("content", "")[:1600]
            src = c.get("source", "")
            context_blocks.append(f"[ref {i+1}] 来源: {src}\n{snippet}")
        context_text = "\n\n".join(context_blocks)
        user_prompt = f"问题：{question}\n\n已检索片段：\n{context_text}\n\n请依据片段回答。"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "math-modeling-rag",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", OPENROUTER_ENDPOINT, json=payload, headers=headers
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data_str = line[len("data:") :].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            js = json.loads(data_str)
                            delta = js.get("choices", [{}])[0].get("delta", {}).get("content")
                            if delta:
                                yield delta
                        except Exception:
                            continue


# --- Provider registry and factory (minimal, backward-compatible) ---
PROVIDER_REGISTRY = {
    "openrouter": OpenRouterLLM,
    # 'openai': OpenAILLM,        # 可按需后续补充
    # 'ollama': OllamaLLM,        # 可按需后续补充
    # 'anthropic': AnthropicLLM,  # 可按需后续补充
}


def get_llm(
    provider: Optional[str] = None, model: Optional[str] = None, api_key: Optional[str] = None
) -> BaseLLM:
    """Return an LLM instance by provider with minimal coupling.

    Defaults preserve current behavior (OpenRouter + default MODEL).
    """
    prov = (provider or os.getenv("LLM_PROVIDER") or "openrouter").lower()
    mdl = model or os.getenv("LLM_MODEL") or MODEL
    # OpenRouter
    if prov == "openrouter":
        key = api_key or os.getenv("OPENROUTER_API_KEY") or ""
        return OpenRouterLLM(key, mdl)
    # Ollama (local)
    if prov == "ollama":
        base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        return OllamaLLM(model=mdl, base_url=base)
    # Google Gemini
    if prov == "google":
        key = api_key or os.getenv("GEMINI_API_KEY") or ""
        return GeminiLLM(api_key=key, model=mdl)
    # Other providers via registry (extendable)
    if prov in PROVIDER_REGISTRY:
        cls = PROVIDER_REGISTRY[prov]
        return cls(mdl)  # type: ignore[misc]
    raise ValueError(f"Unsupported LLM provider: {prov}")


def get_default_llm() -> BaseLLM:
    """Convenience: use env LLM_PROVIDER/LLM_MODEL and provider-specific keys.

    Fallbacks to OpenRouter + default MODEL for backwards compatibility.
    """
    return get_llm()


class GeminiLLM:
    """Google AI Studio Gemini API wrapper, compatible with BaseLLM.

    Notes:
    - Use v1 endpoint and append API key as query parameter.
    - Send a single user message; prefix with SYSTEM_PROMPT to instruct the model.
    - Streaming is not implemented (Gemini streaming requires different handling).
    """

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro-latest"):
        self.api_key = api_key
        # default to a stable published model
        self.model = model or "gemini-1.5-pro-latest"
        self._use_beta_by_default = False
        self.endpoint = self._build_endpoint(use_beta=False)
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY 未设置")

    def _build_endpoint(self, use_beta: bool) -> str:
        base = "https://generativelanguage.googleapis.com"
        version = "v1beta" if use_beta else "v1"
        return f"{base}/{version}/models/{self.model}:generateContent?key={self.api_key}"

    async def acomplete(self, question: str, contexts: List[Dict], stream: bool = False) -> str:
        # build context summary
        ctx = []
        for i, c in enumerate(contexts):
            snip = c.get("content", "")[:1600]
            src = c.get("source", "")
            ctx.append(f"[ref {i+1}] 来源: {src}\n{snip}")
        context_text = "\n\n".join(ctx)

        # combine system prompt + user prompt into a single user message to avoid role issues
        user_prompt = (
            SYSTEM_PROMPT
            + "\n\n"
            + f"问题：{question}\n\n已检索片段：\n{context_text}\n\n请依据片段回答。"
        )

        # keep prompt within reasonable size to avoid API rejections
        max_len = 28000
        if len(user_prompt) > max_len:
            user_prompt = user_prompt[:max_len]

        payload = {"contents": [{"role": "user", "parts": [{"text": user_prompt}]}]}

        headers = {"Content-Type": "application/json"}

        # Try primary endpoint (v1). If 400 and model is 2.5-series, retry with v1beta.
        tried_beta = False
        async with httpx.AsyncClient(timeout=120) as client:
            endpoint = self.endpoint
            for attempt in range(2):
                r = await client.post(endpoint, headers=headers, json=payload)
                if r.status_code == 200:
                    data = r.json()
                    # response parsing - try common locations
                    try:
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    except Exception:
                        if isinstance(data.get("output"), dict):
                            parts = data["output"].get("content", {}).get("parts")
                            if parts:
                                return parts[0].get("text", "")
                        return json.dumps(data, ensure_ascii=False)

                # if bad request and model is 2.5, try beta endpoint once
                if r.status_code == 400 and not tried_beta and "2.5" in self.model:
                    tried_beta = True
                    endpoint = self._build_endpoint(use_beta=True)
                    continue

                # otherwise surface helpful error text
                text = ""
                try:
                    text = r.text
                except Exception:
                    text = f"<no body, status={r.status_code}>"
                raise RuntimeError(f"Gemini API request failed (status={r.status_code}): {text}")

    async def astream(self, question: str, contexts: List[Dict]) -> AsyncGenerator[str, None]:
        # Gemini streaming requires SSE / bidi; not implemented here — return full answer
        result = await self.acomplete(question, contexts, stream=False)
        yield result


class OllamaLLM:
    """Minimal Ollama chat wrapper, compatible with BaseLLM interface."""

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def acomplete(self, question: str, contexts: List[Dict], stream: bool = False) -> str:
        ctx = []
        for i, c in enumerate(contexts):
            snip = c.get("content", "")[:1600]
            src = c.get("source", "")
            ctx.append(f"[ref {i+1}] 来源: {src}\n{snip}")
        context_text = "\n\n".join(ctx)
        user_prompt = f"问题：{question}\n\n已检索片段：\n{context_text}\n\n请依据片段回答。"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": stream,
        }
        url = f"{self.base_url}/api/chat"
        async with httpx.AsyncClient(timeout=120) as client:
            if not stream:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                return (
                    (data.get("message", {}) or {}).get("content") or data.get("response", "") or ""
                )
            parts: List[str] = []
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        js = json.loads(line)
                    except Exception:
                        continue
                    delta = (js.get("message", {}) or {}).get("content") or js.get("response")
                    if delta:
                        parts.append(delta)
            return "".join(parts)

    async def astream(self, question: str, contexts: List[Dict]) -> AsyncGenerator[str, None]:
        ctx = []
        for i, c in enumerate(contexts):
            snip = c.get("content", "")[:1600]
            src = c.get("source", "")
            ctx.append(f"[ref {i+1}] 来源: {src}\n{snip}")
        context_text = "\n\n".join(ctx)
        user_prompt = f"问题：{question}\n\n已检索片段：\n{context_text}\n\n请依据片段回答。"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
        }
        url = f"{self.base_url}/api/chat"
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        js = json.loads(line)
                    except Exception:
                        continue
                    delta = (js.get("message", {}) or {}).get("content") or js.get("response")
                    if delta:
                        yield delta
