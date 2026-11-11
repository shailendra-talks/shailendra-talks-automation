
import os
import re
import base64
import subprocess
from pathlib import Path
import requests


OUTPUT = Path("output")
SCRIPT_FILE = OUTPUT / "short_script.txt"
PARTS_DIR = OUTPUT / "voice_parts"


def split_sentences(text):
    sentences = re.split(r'(?<=[.!?।])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    result = []
    current = ""

    for sentence in sentences:
        if len(sentence) > 2000:
            words = sentence.split()
            for word in words:
                if len(current) + len(word) + 1 > 1200:
                    if current:
                        result.append(current.strip())
                    current = word
                else:
                    current += " " + word
        elif len(current) + len(sentence) + 1 <= 1200:
            current += " " + sentence
        else:
            if current:
                result.append(current.strip())
            current = sentence

    if current:
        result.append(current.strip())

    return result


def generate_voice():
    api_key = os.getenv("SARVAM_API_KEY")

    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is missing.")

    if not SCRIPT_FILE.exists():
        raise FileNotFoundError("Script file is missing.")

    text = SCRIPT_FILE.read_text(encoding="utf-8").strip()

    if not text:
        raise RuntimeError("Script is empty.")

    sentences = split_sentences(text)

    if not sentences:
        raise RuntimeError("No sentences found.")

    PARTS_DIR.mkdir(parents=True, exist_ok=True)

    # Remove old voice parts
    for old_file in PARTS_DIR.glob("*.wav"):
        old_file.unlink()

    print(f"Generating {len(sentences)} separate voice scenes...")

    session = requests.Session()
    audio_files = []

    for index, sentence in enumerate(sentences, start=1):

        print(f"Generating voice scene {index}/{len(sentences)}")

        response = session.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={
                "api-subscription-key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "text": sentence,
                "target_language_code": "hi-IN",
                "model": "bulbul:v3",
                "speaker": "shubh",
                "output_audio_codec": "wav"
            },
            timeout=120
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Sarvam error in scene {index}: "
                f"{response.status_code} {response.text}"
            )

        data = response.json()

        if not data.get("audios"):
            raise RuntimeError(
                f"No audio received for scene {index}"
            )

        audio_bytes = base64.b64decode(data["audios"][0])

        audio_path = PARTS_DIR / f"part_{index:03d}.wav"
        audio_path.write_bytes(audio_bytes)

        audio_files.append(audio_path)

    # Create a combined voiceover for compatibility
    concat_file = OUTPUT / "voice_concat.txt"

    with open(concat_file, "w", encoding="utf-8") as f:
        for audio_path in audio_files:
            f.write(f"file '{audio_path.resolve()}'\n")

    subprocess.run([
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c:a", "pcm_s16le",
        str(OUTPUT / "voiceover.wav")
    ], check=True)

    print("\nVOICE GENERATION SUCCESSFUL!")
    print("Separate audio scenes:", len(audio_files))
    print("Combined voice:", OUTPUT / "voiceover.wav")


if __name__ == "__main__":
    generate_voice()
