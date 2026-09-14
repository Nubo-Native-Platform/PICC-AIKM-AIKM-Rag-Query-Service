from typing import Any
import requests
from src.core.config import settings
from openai import OpenAI, OpenAIError
from string import Formatter

_NO_IMAGE_LINKS_IN_ANSWER = (
    "Do not include markdown image syntax, image URLs, placeholder URLs, or "
    "invented links in the answer. If a relevant image exists, the API returns "
    "it separately in the images array; answer with text only."
)


def format_rag_results(results: list[dict[str, Any]]) -> str:
    chunks = [
        str(result.get("text", "")).strip()
        for result in results
        if result.get("text")
    ]
    return "\n\n".join(chunks)


def summarise_rag_output(
    rag_text: str,
    max_words: int | None = None,
    question: str | None = None,
    extend_public_info: bool = True,
    model_type: str = "public",
    model_name: str | None = None,
    api_key: str | None = None,
) -> str:
    """
    Summarise RAG output using an optional request-selected model.
    """
    text = rag_text.strip()
    if not text and not extend_public_info:
        return "No relevant information found."

    word_limit = max_words or settings.RAG_SUMMARY_MAX_WORDS

    if text and extend_public_info:
        print(f"Information will contain: RAG result + General knowledge")
        system_prompt = _render_system_prompt(
            settings.RAG_WITH_PUBLIC_INFO_SYSTEM_PROMPT,
            word_limit,
        )
        user_prompt = (
            f"Question:\n{(question or '').strip()}\n\n"
            f"RAG context:\n{text}"
        )
    elif text:
        print(f"Information will contain: RAG result only")
        system_prompt = _render_system_prompt(
            settings.RAG_ONLY_SYSTEM_PROMPT,
            word_limit,
        )
        user_prompt = (
            f"Question:\n{(question or '').strip()}\n\n"
            f"RAG context:\n{text}"
        )
    else:
        print(f"Information contains: General knowledge only")
        system_prompt = _render_system_prompt(
            settings.PUBLIC_INFO_ONLY_SYSTEM_PROMPT,
            word_limit,
        )
        user_prompt = (question or "").strip()
        if not user_prompt:
            return "No relevant information found."
        print("NO RAG data found. Public response will be provided.")

    messages = [
        {"role": "system", "content": f"{system_prompt}\n\n{_NO_IMAGE_LINKS_IN_ANSWER}"},
        {"role": "user", "content": user_prompt},
    ]

    try:
        selected_model = (model_name or "").strip().lower()
        if model_type == "local":
            summary = _generate_summary_local_llm(
                selected_model or settings.RAG_SUMMARIZER_LOCAL_LLM,
                messages,
            )
        else:
            summary = _generate_summary_public_llm(
                selected_model or settings.RAG_SUMMARIZER_PUBLIC_LLM,
                messages,
                api_key=api_key,
            )
    except (requests.RequestException, OpenAIError, ValueError) as exc:
        print(f"[Error] getting response from LLM: {exc}")
        return ""

    if not summary:
        if not text:
            return "No relevant information found."
        return ''

    return summary


def _render_system_prompt(
    template: str,
    max_words: int,
) -> str:
    default_prompt = "You are a good assistant, answer the questions efficiently in {max_words}"
    selected_template = template.strip()
    try:
        fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(selected_template)
            if field_name is not None
        }
        if fields - {"max_words"}:
            default_prompt.format(max_words=max_words)
        return selected_template.format(max_words=max_words)
    except (KeyError, ValueError):
        print("[Warning] Invalid system prompt template; using the default prompt.")
        return default_prompt.format(max_words=max_words)


def _generate_summary_public_llm(
    model_name: str,
    messages: list[dict[str, str]],
    api_key: str | None = None,
) -> str:
    print(f"🤖 Public LLM to be used: {model_name}")
    selected_api_key = (api_key or settings.OPENAI_API_KEY or "").strip()
    if not selected_api_key:
        raise ValueError(f"API key is missing for public model: {model_name}")

    client = OpenAI(
        api_key=selected_api_key,
        timeout=settings.GET_SUMMARY_TIMEOUT_LOCAL,
    )
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
    )
    if not response.choices:
        return ""
    return (response.choices[0].message.content or "").strip()


def _generate_summary_local_llm(
    model_name: str,
    messages: list[dict[str, str]],
) -> str:
    print(f"🤖 Local LLM to be used: {model_name}")
    ollama_chat_url = (
        settings.OLLAMA_BASE_URL.rstrip("/").removesuffix("/v1") + "/api/chat"
    )
    headers = {"Content-Type": "application/json"}

    response = requests.post(
        ollama_chat_url,
        headers=headers,
        json={
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2},
        },
        timeout=settings.GET_SUMMARY_TIMEOUT_LOCAL,
    )
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "")
    return content.strip() if isinstance(content, str) else ""
