
import os
import json
import re
from pathlib import Path

from groq import Groq


# =====================================================
# CONFIGURATION
# =====================================================

OUTPUT = Path("output")
SCENES_FILE = OUTPUT / "scenes.json"
SCRIPT_FILE = OUTPUT / "short_script.txt"

MODEL = "llama-3.3-70b-versatile"

NUMBER_OF_SCENES = 7


# =====================================================
# TOPIC AND SCRIPT GENERATION
# =====================================================

def extract_json(text):

    text = text.strip()

    # Remove Markdown code fences if the model adds them.
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    # Find the JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            "Groq did not return a valid JSON object.\n"
            f"Response received:\n{text[:1500]}"
        )

    json_text = text[start:end + 1]

    try:
        return json.loads(json_text)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON returned by Groq: {error}\n"
            f"Response received:\n{json_text[:1500]}"
        )


def validate_script(data):

    if not isinstance(data, dict):
        raise ValueError("Script response must be a JSON object.")

    title = data.get("title")
    description = data.get("description")
    scenes = data.get("scenes")

    if not isinstance(title, str) or not title.strip():
        raise ValueError("Script title is missing.")

    if not isinstance(description, str):
        raise ValueError("Script description is missing.")

    if not isinstance(scenes, list):
        raise ValueError("Scenes must be a list.")

    if len(scenes) < 5 or len(scenes) > 9:
        raise ValueError(
            f"Expected 5 to 9 scenes, received {len(scenes)}."
        )

    clean_scenes = []

    for index, scene in enumerate(scenes, start=1):

        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index} is not an object.")

        narration = str(
            scene.get("narration", "")
        ).strip()

        visual_query = str(
            scene.get("visual_query", "")
        ).strip()

        if not narration:
            raise ValueError(
                f"Scene {index} has empty narration."
            )

        if not visual_query:
            visual_query = "Indian people daily life documentary"

        clean_scenes.append({
            "narration": narration,
            "visual_query": visual_query
        })

    return {
        "title": title.strip(),
        "description": description.strip(),
        "scenes": clean_scenes
    }


# =====================================================
# MAIN GENERATOR
# =====================================================

def generate_script():

    print("\nSHAILENDRA TALKS SCRIPT GENERATOR")
    print("--------------------------------")

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing from GitHub Secrets."
        )

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    client = Groq(api_key=api_key)

    prompt = f"""
You are the professional Hindi-Hinglish scriptwriter
for an Indian YouTube Shorts channel called SHAILENDRA TALKS.

Create one original YouTube Short.

CONTENT STYLE:
- Hinglish language.
- Natural Indian spoken language.
- Funny, sarcastic, intelligent and relatable.
- Social observations and uncomfortable truths.
- Strong opening hook.
- Sharp ending with a memorable punchline.
- Suitable for a general Indian audience.
- No abusive language.
- No hate speech.
- No fabricated facts or statistics.
- No defamatory allegations.
- Do not imitate any specific creator.

VIDEO REQUIREMENTS:
- Approximately 45 to 60 seconds.
- Create exactly {NUMBER_OF_SCENES} scenes.
- Every scene should contain short spoken narration.
- Each scene should take approximately 5 to 9 seconds.
- Scene 1 must have a powerful hook.
- Final scene must have a strong conclusion.
- Narration must contain ONLY words that the voice should speak.
- Never include instructions such as:
  "Scene 1", "Hook", "Pause", "Visual",
  "Background music", "First 3 seconds".
- Do not include camera directions in narration.
- Do not include stage directions in narration.

VISUAL REQUIREMENTS:
- Each visual_query must be a short English search phrase.
- Search phrases should describe real footage suitable for Pixabay.
- Prefer Indian streets, offices, families, students,
  markets, workplaces and everyday life where relevant.
- Do not put visual instructions inside narration.

OUTPUT REQUIREMENTS:
Return ONLY one valid JSON object.
Do not use Markdown.
Do not write any introduction or explanation.

Use this exact structure:

{{
  "title": "Short video title",
  "description": "Short YouTube description with relevant hashtags",
  "scenes": [
    {{
      "narration": "Spoken Hinglish dialogue only.",
      "visual_query": "Indian office workers working"
    }}
  ]
}}
"""

    print("Requesting script from Groq...")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert Indian YouTube Shorts "
                    "scriptwriter. Follow the user's format exactly. "
                    "Return valid JSON only."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.8,
        max_tokens=2200
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    print("Response received. Validating JSON...")

    data = extract_json(content)
    data = validate_script(data)

    # Save structured scene data.
    SCENES_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    # Save narration-only script.
    narration_text = "\n\n".join(
        scene["narration"]
        for scene in data["scenes"]
    )

    SCRIPT_FILE.write_text(
        narration_text,
        encoding="utf-8"
    )

    print("\nSCRIPT GENERATED SUCCESSFULLY")
    print("--------------------------------")
    print("Title:", data["title"])
    print("Scenes:", len(data["scenes"]))
    print("Script:", SCRIPT_FILE)
    print("Scene data:", SCENES_FILE)
    print("--------------------------------")


if __name__ == "__main__":
    generate_script()
