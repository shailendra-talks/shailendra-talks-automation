
import os
import json
import re
from pathlib import Path
from groq import Groq

OUTPUT = Path("output")
SCENES_FILE = OUTPUT / "scenes.json"
SCRIPT_FILE = OUTPUT / "short_script.txt"

MODEL = "openai/gpt-oss-20b"


def clean_text(text):
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "")
    return text.strip()


def generate_script():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing.")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    client = Groq(api_key=api_key)

    prompt = """
Create one original YouTube Short for the Indian channel Shailendra Talks.

STYLE:
- Hinglish in natural spoken Hindi, using Devanagari Hindi mixed with common English words where natural.
- Funny, sharp, sarcastic, relatable Indian social commentary.
- Intelligent, bold, entertaining, not abusive.
- Around 45 to 60 seconds when spoken.
- Start with a powerful spoken hook.
- No fake facts, fabricated statistics, defamatory allegations or unsupported claims.
- Do not imitate any specific creator.

IMPORTANT:
Return ONLY valid JSON. No markdown, no introduction, no explanation.

The JSON must follow this exact structure:
{
  "title": "short video title",
  "description": "one short description",
  "scenes": [
    {
      "narration": "Only the exact words the narrator must speak.",
      "visual_query": "Short English Pixabay search phrase describing footage for this dialogue."
    }
  ]
}

RULES:
- Create 6 to 8 scenes.
- Every narration field must contain spoken dialogue only.
- Never put labels like Scene 1, Hook, Intro, Voiceover, Narrator, Visual, B-roll, Camera, Pause or timestamps in narration.
- Never put instructions in narration.
- Never use emojis, hashtags, bullet points or decorative symbols in narration.
- Do not write numbers as digit-only standalone narration.
- Each scene should contain one or two natural spoken sentences.
- Visual queries must be in English and describe real footage, not text or graphics.
- The scenes together must form one continuous, coherent script.
- End with a memorable punchline or thought.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a professional Indian Hinglish YouTube Shorts scriptwriter. Follow the JSON format exactly."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.8,
        max_completion_tokens=1800,
        response_format={"type": "json_object"}
    )

    raw = clean_text(response.choices[0].message.content or "")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Groq returned invalid JSON: {error}\n{raw[:1000]}")

    scenes = data.get("scenes", [])
    if not isinstance(scenes, list) or len(scenes) < 4:
        raise RuntimeError("AI did not return enough valid scenes.")

    cleaned_scenes = []

    for scene in scenes:
        if not isinstance(scene, dict):
            continue

        narration = str(scene.get("narration", "")).strip()
        visual_query = str(scene.get("visual_query", "")).strip()

        narration = re.sub(r"\s+", " ", narration)
        narration = re.sub(r"^[\s\-–—•]+", "", narration)

        # Reject empty or instruction-like dialogue.
        if not narration or len(narration) < 8:
            continue

        if re.search(
            r"\b(scene\s*\d*|hook|visual direction|voiceover|narrator|b-roll|camera angle)\b",
            narration,
            flags=re.IGNORECASE
        ):
            raise RuntimeError(
                "AI placed a production instruction inside narration. "
                "Please run the workflow again."
            )

        cleaned_scenes.append({
            "narration": narration,
            "visual_query": visual_query or "Indian city daily life"
        })

    if not 4 <= len(cleaned_scenes) <= 8:
        raise RuntimeError(
            f"Expected 4 to 8 clean scenes, got {len(cleaned_scenes)}."
        )

    data["scenes"] = cleaned_scenes

    SCENES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    full_script = "\n".join(
        scene["narration"] for scene in cleaned_scenes
    )

    SCRIPT_FILE.write_text(
        full_script,
        encoding="utf-8"
    )

    print("SCRIPT GENERATION SUCCESSFUL")
    print("Title:", data.get("title", "Shailendra Talks"))
    print("Number of scenes:", len(cleaned_scenes))
    print("Clean dialogue saved:", SCRIPT_FILE)
    print("Scene data saved:", SCENES_FILE)


if __name__ == "__main__":
    generate_script()
