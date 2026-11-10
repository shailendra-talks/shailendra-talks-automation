
import os
from pathlib import Path

from google import genai
from google.genai import types


def extract_script(response):
    """Extract text even if response.text is unavailable."""

    text = getattr(response, "text", None)

    if text and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None) or []

    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []

        for part in parts:
            part_text = getattr(part, "text", None)

            if part_text and part_text.strip():
                return part_text.strip()

    return None


def generate_script():

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    client = genai.Client(api_key=api_key)

    prompt = """
    You are the original Hinglish comedy writer for
    Shailendra Talks, an Indian YouTube Shorts channel.

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

    models_to_try = [
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.8-flash"
    ]

    script = None

    for model_name in models_to_try:

        print(f"\nTrying model: {model_name}")

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.8,
                    max_output_tokens=900
                )
            )

            script = extract_script(response)

            if script:
                print(f"SUCCESS: {model_name}")
                break

            print("Model returned no usable text.")
            print("Prompt feedback:", getattr(
                response, "prompt_feedback", None
            ))

            candidates = getattr(response, "candidates", None) or []

            for candidate in candidates:
                print(
                    "Finish reason:",
                    getattr(candidate, "finish_reason", None)
                )
                print(
                    "Safety ratings:",
                    getattr(candidate, "safety_ratings", None)
                )

            print("Trying next model...")

        except Exception as error:

            print(f"Model failed: {model_name}")
            print("Error:", str(error))
            print("Trying next model...")

            continue

    if not script:
        raise RuntimeError(
            "All Gemini models failed to generate a usable script. "
            "Check the logs for the actual errors."
        )

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "short_script.txt"

    output_file.write_text(
        script,
        encoding="utf-8"
    )

    print("\nSCRIPT GENERATED SUCCESSFULLY!")
    print("\n", script)
    print("\nSaved at:", output_file)


if __name__ == "__main__":
    generate_script()
