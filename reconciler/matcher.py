import json
import re
from openai import OpenAI

PROMPT_TEMPLATE = """あなたは災害復旧事業の書類審査の専門家です。
以下の2文書を比較し、必ずJSONのみで回答してください。余分な説明は不要です。

【基準文書】
{base_text}

【比較文書】
{compare_text}

回答形式（このJSONのみ出力）:
{{
  "content_similarity_score": <0.0〜1.0 全体内容の一致度>,
  "change_presence_score": <0.0〜1.0 変更の有無・理由の整合度>,
  "combined_score": <両スコアの平均>,
  "change_classification": "重要変更|軽微変更|変更なし|判断不可",
  "requires_consultation": true,
  "key_differences": ["差異1", "差異2"],
  "summary": "一言で評価（日本語）"
}}"""

SUMMARY_PROMPT = """以下の文書を3〜5文で簡潔に要約してください。重要な数値・固有名詞・変更内容を優先して残してください。

{text}

要約:"""


def _truncate_or_summarize(client, model: str, text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    prompt = SUMMARY_PROMPT.format(text=text[:max_chars * 2])
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    result = resp.choices[0].message.content.strip()
    return result[:max_chars]


def _parse_json(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"JSON not found in response: {raw[:200]}")


def compare(
    base_text: str,
    compare_text: str,
    config: dict,
) -> dict:
    client = OpenAI(
        base_url=config["lm_studio_url"],
        api_key=config.get("lm_studio_api_key", "lm-studio"),
    )
    model = config["lm_studio_model"]
    max_chars = config.get("max_chars_per_doc", 1500)

    base_text = _truncate_or_summarize(client, model, base_text, max_chars)
    compare_text = _truncate_or_summarize(client, model, compare_text, max_chars)

    prompt = PROMPT_TEMPLATE.format(base_text=base_text, compare_text=compare_text)
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(2):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        try:
            return _parse_json(raw)
        except (ValueError, json.JSONDecodeError):
            if attempt == 0:
                continue
            return {
                "content_similarity_score": None,
                "change_presence_score": None,
                "combined_score": None,
                "change_classification": "判断不可",
                "requires_consultation": True,
                "key_differences": [],
                "summary": "JSON解析失敗",
                "_raw_response": raw,
            }
