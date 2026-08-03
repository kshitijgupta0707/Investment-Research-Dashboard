"""Print the raw Gemini planning response for the acceptance queries.

Usage:
    python backend/scripts/dump_turn1.py

Sends the same model, system prompt and tool schemas `plan_query` uses, then
prints the untouched response so the wire format can be inspected. Evidence for
the claim that tool selection is decided per query by the model rather than by
routing logic -- see docs/agent-turn1-observed.md for a captured run.

Costs four live API calls.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from google.genai import types  # noqa: E402

from app.agent.client import get_client  # noqa: E402
from app.agent.planner import MAX_TOKENS, SYSTEM_PROMPT  # noqa: E402
from app.agent.tools import TOOL_SCHEMAS, as_tool  # noqa: E402
from app.utils.config import get_settings  # noqa: E402

# Four of the six acceptance queries in PROJECT_PLAN §7, chosen to cover every
# arity: one tool, one tool again with a different one, all three, and none.
QUERIES = [
    ("news only", "What's the latest news on Tesla?"),
    ("market only", "What's NVIDIA's current P/E and market cap?"),
    (
        "all three",
        "Analyze NVIDIA's Q3 earnings, compare revenue growth with AMD and Intel, "
        "summarize competitive threats and news sentiment, give a risk assessment",
    ),
    ("zero tools", "What is a P/E ratio?"),
]

# The signature is ~2 KB of opaque base64 and swamps the output.
SIGNATURE_PREVIEW = 48


def _redact(payload: dict) -> dict:
    """Shorten thought_signature so the rest of the response stays readable."""
    for candidate in payload.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            signature = part.get("thought_signature")
            if signature:
                part["thought_signature"] = f"{signature[:SIGNATURE_PREVIEW]}...<truncated>"
    return payload


async def dump(label: str, query: str) -> None:
    settings = get_settings()

    response = await get_client().aio.models.generate_content(
        model=settings.gemini_model,
        contents=query,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_TOKENS,
            tools=[as_tool(TOOL_SCHEMAS)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )

    print("\n" + "=" * 78)
    print(f"  {label.upper()}  --  {query}")
    print("=" * 78)

    payload = _redact(response.model_dump(mode="json", exclude_none=True))
    payload.pop("sdk_http_response", None)

    print("\n--- raw response ---")
    print(json.dumps(payload, indent=2))

    calls = response.function_calls or []
    print("\n--- response.function_calls ---")
    print(json.dumps([c.model_dump(mode="json", exclude_none=True) for c in calls], indent=2))

    print("\n--- what the planner derives ---")
    print(f"  tools selected: {[c.name for c in calls]}")
    usage = response.usage_metadata
    print(f"  tokens        : {getattr(usage, 'total_token_count', None)} total")


async def main() -> int:
    if not get_settings().gemini_api_key:
        print("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return 1

    for label, query in QUERIES:
        try:
            await dump(label, query)
        except Exception as exc:
            print(f"\n!! {label} failed: {type(exc).__name__}: {exc}")
        # The free tier is rate limited per minute.
        await asyncio.sleep(4)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
