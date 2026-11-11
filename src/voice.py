
import os
import json
import base64
import subprocess
import time
from pathlib import Path

import requests

OUTPUT = Path("output")
SCENES_FILE = OUTPUT / "scenes.json"
PARTS_DIR = OUTPUT / "voice_parts"
VOICE_FILE = OUTPUT / "voiceover.wav"

API_URL = "https://api.sarvam.ai/text-to-speech"
MAX_RETRIES = 3


def generate_audio(session, api_key, text, scene_number):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.post(
                API_URL,
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

            if response.status_code == 200:
                audios = response.json().get("audios", [])
                if not audios:
                    raise RuntimeError(
                        f"No audio returned for scene {scene_number}."
                    )
                return base64.b64decode(audios[0])

            if response.status_code not in (429, 500, 502, 503, 504):
                raise RuntimeError(
                    f"Sarvam error in scene {scene_number}: "
                    f"{response.status_code} {response.text}"
                )

            print(
                f"Temporary API error. Retry {attempt}/{MAX_RETRIES}"
            )

        except requests.RequestException as error:
            print("Network error:", error)

        if attempt < MAX_RETRIES:
            time.sleep(attempt * 5)

    raise RuntimeError(
        f"Voice generation failed for scene {scene_number}."
    )


def verify_audio(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Invalid audio: {path}")

    try:
        duration = float(result.stdout.strip())
    except ValueError:
        raise RuntimeError(f"Could not read audio duration: {path}")

    if duration <= 0:
        raise RuntimeError(f"Audio is empty: {path}")


def combine_audio(files):
    concat_file = OUTPUT / "voice_concat.txt"

    with concat_file.open("w", encoding="utf-8") as file:
        for path in files:
            file.write(f"file '{path.resolve()}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:a", "pcm_s16le",
            str(VOICE_FILE)
        ],
        check=True
    )


def generate_voice():
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is missing.")

    if not SCENES_FILE.exists():
        raise FileNotFoundError("output/scenes.json is missing.")

    data = json.loads(SCENES_FILE.read_text(encoding="utf-8"))
    scenes = data.get("scenes", [])

    if not scenes:
        raise RuntimeError("No scenes found in scenes.json.")

    PARTS_DIR.mkdir(parents=True, exist_ok=True)

    # Remove old scene audio to prevent stale files.
    for old_file in PARTS_DIR.glob("*.wav"):
        old_file.unlink()

    session = requests.Session()
    audio_files = []

    for index, scene in enumerate(scenes, start=1):
        narration = str(scene.get("narration", "")).strip()

        if not narration:
            raise RuntimeError(f"Scene {index} has empty narration.")

        if len(narration) > 2000:
            raise RuntimeError(
                f"Scene {index} is too long for one voice request."
            )

        print(f"Generating voice for scene {index}/{len(scenes)}")

        audio_bytes = generate_audio(
            session, api_key, narration, index
        )

        audio_path = PARTS_DIR / f"scene_{index:03d}.wav"
        audio_path.write_bytes(audio_bytes)
        verify_audio(audio_path)

        audio_files.append(audio_path)
        print("Saved:", audio_path)

        time.sleep(1)

    if len(audio_files) != len(scenes):
        raise RuntimeError("Scene and audio counts do not match.")

    combine_audio(audio_files)

    print("VOICE GENERATION SUCCESSFUL")
    print("Scenes:", len(scenes))
    print("Audio files:", len(audio_files))
    print("Combined audio:", VOICE_FILE)


if __name__ == "__main__":
    generate_voice()
