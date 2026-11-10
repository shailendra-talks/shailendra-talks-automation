
import os
import time
from pathlib import Path

from google import genai
from google.genai import types


def generate_script():

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. "
            "Please check GitHub Secrets."
        )

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
        os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        "gemini-3.6-flash"
    ]

    # Remove duplicate model names
    models_to_try = list(dict.fromkeys(models_to_try))

    response = None

    for model_name in models_to_try:

        print(f"Trying Gemini model: {model_name}")

        for attempt in range(3):

            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.8,
                        max_output_tokens=900
                    )
                )

                if response and response.text:
                    print(f"Success with model: {model_name}")
                    break

                raise RuntimeError("Gemini returned an empty response.")

            except Exception as error:

                error_message = str(error)

                print(f"Attempt {attempt + 1} failed: {error_message}")

                # Try another model if this model is unavailable
                if "404" in error_message:
                    print("Model unavailable. Trying fallback model.")
                    break

                # Retry temporary server or rate-limit errors
                temporary_error = any(
                    code in error_message
                    for code in [
                        "503",
                        "UNAVAILABLE",
                        "429",
                        "RESOURCE_EXHAUSTED",
                        "500",
                        "INTERNAL"
                    ]
                )

                if not temporary_error:
                    raise

                if attempt < 2:
                    wait_time = 15 * (2 ** attempt)
                    print(
                        f"Temporary problem. "
                        f"Retrying after {wait_time} seconds..."
                    )
                    time.sleep(wait_time)

                else:
                    print(f"{model_name} failed after 3 attempts.")

        if response and response.text:
            break

    if not response or not response.text:
        raise RuntimeError(
            "All Gemini models failed. "
            "Please try the workflow again later."
        )

    script = response.text.strip()

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "short_script.txt"
    output_file.write_text(script, encoding="utf-8")

    print("\nSCRIPT GENERATED SUCCESSFULLY!\n")
    print(script)


if __name__ == "__main__":
    generate_script()
