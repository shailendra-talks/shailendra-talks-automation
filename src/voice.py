
import os
import re
import base64
import subprocess
import time
from pathlib import Path

import requests


OUTPUT = Path("output")
SCRIPT_FILE = OUTPUT / "short_script.txt"
PARTS_DIR = OUTPUT / "voice_parts"

API_URL = "https://api.sarvam.ai/text-to-speech"

MAX_SENTENCE_LENGTH = 2000
MAX_RETRIES = 3


def split_sentences(text):
    """
    Split script into speakable sentences.
    Skip empty text and symbols-only sentences.
    """

    raw_sentences = re.split(
        r'(?<=[.!?।])\s+',
        text.strip()
    )

    sentences = []

    for sentence in raw_sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        # Keep only sentences containing Hindi or English letters.
        if not re.search(
            r'[A-Za-z\u0900-\u097F]',
            sentence
        ):
            continue

        # Remove emojis and unsupported decorative symbols.
        sentence = re.sub(
            r'[^\w\s\u0900-\u097F.,!?;:\'"()\-/।]',
            '',
            sentence,
            flags=re.UNICODE
        ).strip()

        if sentence and re.search(
            r'[A-Za-z\u0900-\u097F]',
            sentence
        ):
            sentences.append(sentence)

    return sentences


def save_clean_script(sentences):
    """
    Save exactly the sentences used for voice generation.
    video.py reads this same script.
    """

    clean_text = " ".join(sentences)

    SCRIPT_FILE.write_text(
        clean_text,
        encoding="utf-8"
    )


def request_voice(session, api_key, sentence, index):

    for attempt in range(1, MAX_RETRIES + 1):

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
                data = response.json()

                audios = data.get("audios", [])

                if not audios:
                    raise RuntimeError(
                        f"No audio returned for sentence {index}"
                    )

                audio_bytes = base64.b64decode(audios[0])

                if not audio_bytes:
                    raise RuntimeError(
                        f"Empty audio returned for sentence {index}"
                    )

                return audio_bytes

            if response.status_code not in (
                429, 500, 502, 503, 504
            ):
                raise RuntimeError(
                    f"Sarvam API error in sentence {index}: "
                    f"{response.status_code} {response.text}"
                )

            print(
                f"Temporary Sarvam error. "
                f"Retry {attempt}/{MAX_RETRIES}"
            )

        except requests.RequestException as error:

            print(
                f"Network error in sentence {index}: {error}"
            )

        if attempt < MAX_RETRIES:
            time.sleep(attempt * 5)

    raise RuntimeError(
        f"Sarvam failed after {MAX_RETRIES} attempts "
        f"for sentence {index}."
    )


def verify_audio(audio_path):

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Invalid audio file: {audio_path}\n"
            f"{result.stderr}"
        )

    try:
        duration = float(result.stdout.strip())
    except ValueError:
        raise RuntimeError(
            f"Could not read audio duration: {audio_path}"
        )

    if duration <= 0:
        raise RuntimeError(
            f"Audio duration is zero: {audio_path}"
        )


def combine_audio(audio_files):

    concat_file = OUTPUT / "voice_concat.txt"
    combined_file = OUTPUT / "voiceover.wav"

    with open(
        concat_file,
        "w",
        encoding="utf-8"
    ) as file:

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
            str(combined_file)
        ],
        check=True
    )

    print("Combined voice created:", combined_file)


def generate_voice():

    print("\nSTARTING SHAILENDRA TALKS VOICE GENERATOR\n")

    api_key = os.getenv("SARVAM_API_KEY")

    if not api_key:
        raise RuntimeError(
            "SARVAM_API_KEY is missing from GitHub Secrets."
        )

    if not SCRIPT_FILE.exists():
        raise FileNotFoundError(
            "output/short_script.txt does not exist."
        )

    original_text = SCRIPT_FILE.read_text(
        encoding="utf-8"
    ).strip()

    if not original_text:
        raise RuntimeError(
            "Generated script is empty."
        )

    # Create the canonical sentence list.
    sentences = split_sentences(original_text)

    if not sentences:
        raise RuntimeError(
            "No supported Hindi or English sentences found."
        )

    # Check sentence length before API calls.
    for index, sentence in enumerate(sentences, start=1):

        if len(sentence) > MAX_SENTENCE_LENGTH:
            raise RuntimeError(
                f"Sentence {index} contains "
                f"{len(sentence)} characters. "
                "Please shorten the script sentence."
            )

    # Update script to match exactly the spoken sentences.
    save_clean_script(sentences)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    PARTS_DIR.mkdir(parents=True, exist_ok=True)

    # Remove old audio files.
    for old_file in PARTS_DIR.glob("*.wav"):
        old_file.unlink()

    print("Total speakable sentences:", len(sentences))

    session = requests.Session()

    audio_files = []

    for index, sentence in enumerate(
        sentences,
        start=1
    ):

        print(
            f"\nGenerating voice "
            f"{index}/{len(sentences)}"
        )

        print("Text:", sentence)

        audio_bytes = request_voice(
            session,
            api_key,
            sentence,
            index
        )

        audio_path = (
            PARTS_DIR /
            f"part_{index:03d}.wav"
        )

        audio_path.write_bytes(audio_bytes)

        verify_audio(audio_path)

        audio_files.append(audio_path)

        print("Saved:", audio_path)

        # Small delay between API requests.
        time.sleep(1)

    # Final consistency check.
    if len(audio_files) != len(sentences):
        raise RuntimeError(
            f"Mismatch: {len(sentences)} sentences, "
            f"{len(audio_files)} audio files."
        )

    combine_audio(audio_files)

    print("\n================================")
    print("VOICE GENERATION SUCCESSFUL")
    print("================================")
    print("Script sentences:", len(sentences))
    print("Audio files:", len(audio_files))
    print("Combined voice: output/voiceover.wav")
    print("================================\n")


if __name__ == "__main__":
    generate_voice()
