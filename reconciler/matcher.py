import json
import re
from openai import OpenAI

PROMPT_TEMPLATE = """あなたは災害復旧事業の書類審査の専門家です。

【基準文書】には設計変更の変更理由が記載されています。
【比較文書】に同じ変更理由が記載されているかを確認してください。

判定基準:
- 表現・順序・語句が多少異なっても、変更理由の骨子（工種・数量・理由の核心）が一致していれば「一致」とする
- 変更理由の重要な要素が欠けている、または記載が曖昧な場合は「部分一致」とする
- 変更理由が全く記載されていない、または明らかに異なる内容の場合は「不一致」とする
- 甘すぎる判定は避け、根拠が明確な場合のみ「一致」とすること

【基準文書】
{base_text}

【比較文書】
{compare_text}

必ずJSONのみで回答してください。余分な説明は不要です。
{{
  "content_similarity_score": <0.0〜1.0 変更理由の一致度>,
  "change_presence_score": <0.0〜1.0 比較文書における変更理由の記載の明確さ>,
  "combined_score": <両スコアの平均>,
  "change_classification": "一致|部分一致|不一致|判断不可",
  "requires_consultation": true,
  "key_differences": ["差異点1", "差異点2"],
  "summary": "一言で評価（日本語）"
}}"""

SUMMARY_PROMPT = """以下の文書を3〜5文で簡潔に要約してください。
「なぜ設計変更が必要か」という変更理由・根拠を最優先で残してください。工種・数量・固有名詞も保持してください。

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
