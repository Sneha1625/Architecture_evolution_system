import os
from typing import Any

from groq import Groq


MODEL_NAME = "openai/gpt-oss-120b"


def _get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Set it in PowerShell before running AI analysis."
        )

    return Groq(api_key=api_key)


def analyze_architecture(
    architecture_data: dict[str, Any]
) -> str:
    """
    Analyze structured architecture information using Groq.

    The AI input is intentionally limited to concise architecture
    information so the request stays within Groq's token limit.

    architecture_data may contain:
    - components
    - relationships
    - snapshot/version information
    - architecture evolution changes
    """

    client = _get_client()

    # --------------------------------------------------------
    # EXTRACT ARCHITECTURE DATA
    # --------------------------------------------------------

    components = architecture_data.get(
        "components",
        []
    )

    relationships = architecture_data.get(
        "relationships",
        []
    )

    changes = architecture_data.get(
        "changes",
        []
    )

    # --------------------------------------------------------
    # LIMIT INPUT SIZE
    # --------------------------------------------------------

    # Keep the request comfortably below the
    # Groq tokens-per-minute limit.

    components = components[:30]

    relationships = relationships[:40]

    changes = changes[:30]

    # --------------------------------------------------------
    # CREATE COMPACT AI INPUT
    # --------------------------------------------------------

    compact_data = {
        "snapshot": architecture_data.get(
            "snapshot"
        ),
        "components": components,
        "relationships": relationships,
        "changes": changes,
    }

    # --------------------------------------------------------
    # AI PROMPT
    # --------------------------------------------------------

    prompt = f"""
You are an expert software architecture analyst.

Analyze the architecture information provided below.

IMPORTANT:
- Base factual statements only on the supplied architecture data.
- Do not invent components, relationships, files, or changes.
- Clearly distinguish observed facts from interpretations or suggestions.
- Focus on useful software architecture insights.
- Keep the response concise and practical.

Provide the analysis using these sections:

1. Architecture Summary
2. Observed Components
3. Observed Relationships
4. Architecture Changes
5. Potential Architectural Risks
6. Potential Impact
7. Suggested Investigation Areas

Architecture data:

{compact_data}
"""

    # --------------------------------------------------------
    # SEND REQUEST TO GROQ
    # --------------------------------------------------------

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a software architecture "
                    "analysis assistant. "
                    "Analyze only the architecture data "
                    "supplied by the user."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
        max_tokens=1500,
    )

    return (
        response.choices[0].message.content
        or ""
    )


# ------------------------------------------------------------
# DIRECT TEST
# ------------------------------------------------------------

if __name__ == "__main__":

    test_data = {
        "snapshot": {
            "version": "1.0",
            "commit_hash": "example",
        },
        "components": [
            "Architecture Model",
            "Analyzer",
            "Parser",
            "Dependency",
        ],
        "relationships": [
            "Analyzer -> Architecture Model",
            "Parser -> Architecture Model",
        ],
        "changes": [
            "Example architecture analysis request",
        ],
    }

    print(
        analyze_architecture(test_data)
    )