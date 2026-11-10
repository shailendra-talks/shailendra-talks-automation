
import os
from pathlib import Path
from google import genai
from google.genai import types

def generate_script():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=api_key)

    prompt = """
    You are the original Hinglish comedy writer for Shailendra Talks,
    an Indian YouTube Shorts channel.

    Create ONE original 40-55 second YouTube Shorts script.

    Topic: Indian middle-class obsession with salary and status.

    Style:
    - Natural spoken Hinglish
    - Funny, sarcastic and relatable
    - Strong opening hook in first 3 seconds
    - Memorable punchline
    - No copied jokes or existing scripts
    - No fake statistics or fabricated facts
    - Suitable for one person speaking to camera

    Return only the spoken script.
    Do not add camera directions or explanations.
    """

    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.8,
            max_output_tokens=900
        )
    )

    script = (response.text or "").strip()

    if not script:
        raise RuntimeError("Gemini returned an empty script")

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "short_script.txt"
    output_file.write_text(script, encoding="utf-8")

    print("Script generated successfully!")
    print(script)

if __name__ == "__main__":
    generate_script()
