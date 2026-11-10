
import os
import base64
from pathlib import Path
import requests


def generate_voice():
    api_key = os.getenv("SARVAM_API_KEY")

    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is missing.")

    script_file = Path("output/short_script.txt")

    if not script_file.exists():
        raise FileNotFoundError("Generated script not found.")

    text = script_file.read_text(encoding="utf-8").strip()

    if not text:
        raise RuntimeError("Script is empty.")

    if len(text) > 2500:
        raise RuntimeError("Script exceeds Sarvam's 2500-character limit.")

    response = requests.post(
        "https://api.sarvam.ai/text-to-speech",
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "text": text,
            "language_code": "hi-IN",
            "model": "bulbul:v4-flash",
            "output_audio_codec": "wav"
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()
    audio_data = data["audios"][0]

    audio_bytes = base64.b64decode(audio_data)

    output_file = Path("output/voiceover.wav")
    output_file.write_bytes(audio_bytes)

    print("VOICE GENERATED SUCCESSFULLY!")
    print("Saved to:", output_file)


if __name__ == "__main__":
    generate_voice()
