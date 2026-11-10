
import os
import base64
from pathlib import Path
import requests


def generate_voice():

    # 1. Check API key
    api_key = os.getenv("SARVAM_API_KEY")

    if not api_key:
        raise RuntimeError(
            "SARVAM_API_KEY is missing. "
            "Please check GitHub Secrets."
        )

    # 2. Read generated script
    script_file = Path("output/short_script.txt")

    if not script_file.exists():
        raise FileNotFoundError(
            "Script file not found: output/short_script.txt"
        )

    text = script_file.read_text(
        encoding="utf-8"
    ).strip()

    if not text:
        raise RuntimeError("Script is empty.")

    if len(text) > 2500:
        raise RuntimeError(
            "Script exceeds 2500 characters."
        )

    print("Connecting to Sarvam AI...")
    print("Generating Hindi AI voice...")

    # 3. Send request to Sarvam AI
    response = requests.post(
        "https://api.sarvam.ai/text-to-speech",

        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json"
        },

        json={
            "text": text,
            "target_language_code": "hi-IN",
            "model": "bulbul:v3",
            "speaker": "shubh",
            "output_audio_codec": "wav"
        },

        timeout=120
    )

    # 4. Handle API errors
    if response.status_code != 200:
        raise RuntimeError(
            f"Sarvam API Error: {response.status_code}\n"
            f"{response.text}"
        )

    # 5. Decode generated audio
    data = response.json()

    if not data.get("audios"):
        raise RuntimeError(
            "Sarvam returned no audio data."
        )

    audio_data = base64.b64decode(
        data["audios"][0]
    )

    # 6. Save voiceover
    output_dir = Path("output")
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    audio_file = output_dir / "voiceover.wav"

    audio_file.write_bytes(audio_data)

    print("\nVOICE GENERATED SUCCESSFULLY!")
    print("Audio saved at:", audio_file)


if __name__ == "__main__":
    generate_voice()
