
import os
from pathlib import Path
from groq import Groq


def generate_script():

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Check GitHub Secrets."
        )

    client = Groq(
        api_key=api_key,
        timeout=60.0,
        max_retries=3
    )

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
    - Original jokes only
    - No fake statistics or fabricated facts
    - Suitable for one person speaking to camera
    - Write in natural Roman Hindi and English

    Return only the spoken script.
    Do not add camera directions or explanations.
    """

    print("Connecting to Groq AI...")

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a creative Indian Hinglish "
                    "YouTube Shorts scriptwriter."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.8,
        max_completion_tokens=1200
    )

    script = response.choices[0].message.content

    if not script or not script.strip():
        raise RuntimeError("Groq returned an empty script.")

    script = script.strip()

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "short_script.txt"

    output_file.write_text(
        script,
        encoding="utf-8"
    )

    print("\nSCRIPT GENERATED SUCCESSFULLY!")
    print("\n" + script)
    print("\nSaved to:", output_file)


if __name__ == "__main__":
    generate_script()
