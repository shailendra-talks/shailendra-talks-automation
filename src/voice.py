
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
        raise FileNotFoundError("Script file not found.")

    text = script_file.read_text(encoding="utf-8").strip()

    if not text:
        raise RuntimeError("Script is empty.")

    if len(text) > 2500:
        raise RuntimeError("Script exceeds 2500 characters.")

    print("Connecting to Sarvam AI...")

    response = requests.post(
        "https://api.sarvam.ai/text-to-speech",
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "text": text,
            "target_language_code": "hi-IN",
            "model": "bulbul:v4",
            "speaker": "shubh",
            "output_audio_codec": "wav"
        },
        timeout=120
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Sarvam API Error: {response.status_code} "
            f"{response.text}"
        )

    data = response.json()

    audio = base64.b64decode(data["audios"][0])

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    audio_file = output_dir / "voiceover.wav"
    audio_file.write_bytes(audio)

    print("VOICE GENERATED SUCCESSFULLY!")
    print("Saved:", audio_file)


if __name__ == "__main__":
    generate_voice()
