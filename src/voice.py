
import os
import re
import base64
import subprocess
from pathlib import Path

import requests


OUTPUT = Path("output")
SCRIPT_FILE = OUTPUT / "short_script.txt"
PARTS_DIR = OUTPUT / "voice_parts"

API_URL = "https://api.sarvam.ai/text-to-speech"


def split_sentences(text):
    """
    IMPORTANT:
    This function must remain identical to video.py.
    One sentence = one audio file = one video scene.
    """
    sentences = re.split(r'(?<=[.!?।])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


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

    # Sarvam text length safety check.
    for index, sentence in enumerate(sentences, start=1):
        if len(sentence) > 2000:
            raise RuntimeError(
                f"Sentence {index} has {len(sentence)} characters. "
                "Please shorten this sentence in the generated script."
            )

    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Remove all old audio files to avoid stale parts.
    for old_file in PARTS_DIR.glob("*.wav"):
        old_file.unlink()

    print(f"Total script sentences: {len(sentences)}")

    session = requests.Session()
    audio_files = []

    for index, sentence in enumerate(sentences, start=1):
        print(
            f"\nGenerating audio {index}/{len(sentences)}"
        )

        response = None

        # Retry temporary network/server failures.
        for attempt in range(1, 4):
            try:
                response = session.post(
                    API_URL,
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

                if response.status_code == 200:
                    break

                if response.status_code not in (429, 500, 502, 503, 504):
                    raise RuntimeError(
                        f"Sarvam error in sentence {index}: "
                        f"{response.status_code} {response.text}"
                    )

                print(
                    f"Temporary API error. Attempt {attempt}/3"
                )

            except requests.RequestException as error:
                print(f"Network error: {error}")

            if attempt < 3:
                import time
                time.sleep(attempt * 5)

        if response is None or response.status_code != 200:
            details = (
                response.text[:1000]
                if response is not None
                else "No response received"
            )

            raise RuntimeError(
                f"Voice generation failed for sentence {index}: "
                f"{details}"
            )

        data = response.json()
        audios = data.get("audios", [])

        if not audios:
            raise RuntimeError(
                f"No audio received for sentence {index}"
            )

        audio_bytes = base64.b64decode(audios[0])

        if not audio_bytes:
            raise RuntimeError(
                f"Empty audio received for sentence {index}"
            )

        audio_path = (
            PARTS_DIR / f"part_{index:03d}.wav"
        )

        audio_path.write_bytes(audio_bytes)

        # Verify that the generated audio is readable.
        subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ],
            check=True,
            capture_output=True,
            text=True
        )

        audio_files.append(audio_path)

        print("Saved:", audio_path)

    # Verify exact one-to-one mapping.
    if len(audio_files) != len(sentences):
        raise RuntimeError(
            f"Expected {len(sentences)} audio files, "
            f"but generated {len(audio_files)}."
        )

    # Create combined voiceover.
    concat_file = OUTPUT / "voice_concat.txt"

    with open(concat_file, "w", encoding="utf-8") as file:
        for audio_path in audio_files:
            file.write(
                f"file '{audio_path.resolve()}'\n"
            )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:a", "pcm_s16le",
            str(OUTPUT / "voiceover.wav")
        ],
        check=True
    )

    print("\nVOICE GENERATION SUCCESSFUL!")
    print("Script sentences:", len(sentences))
    print("Separate audio files:", len(audio_files))
    print("Combined voice:", OUTPUT / "voiceover.wav")


if __name__ == "__main__":
    generate_voice()
