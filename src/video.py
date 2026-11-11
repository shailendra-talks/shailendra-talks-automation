
import os
import math
import subprocess
from pathlib import Path

import requests

OUTPUT = Path("output")
CLIPS = OUTPUT / "clips"

WIDTH = 1080
HEIGHT = 1920
FPS = 30

PEXELS_API = "https://api.pexels.com/v1/videos/search"


def run_command(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Video rendering failed:\n"
            + result.stderr[-5000:]
        )


def check_tools():
    for tool in ["ffmpeg", "ffprobe"]:
        result = subprocess.run(
            ["which", tool],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"{tool} is not installed.")


def get_search_queries(script):
    text = script.lower()

    if any(word in text for word in [
        "salary", "paisa", "paise", "money",
        "middle class", " EMI", "income"
    ]):
        return [
            "office worker working",
            "counting money calculator",
            "family at home"
        ]

    if any(word in text for word in [
        "student", "college", "education", "exam"
    ]):
        return [
            "college students studying",
            "student studying books",
            "university campus"
        ]

    if any(word in text for word in [
        "social media", "instagram", "phone",
        "internet", "online"
    ]):
        return [
            "person using smartphone",
            "people using computers",
            "busy city people"
        ]

    if any(word in text for word in [
        "politics", "government", "election",
        "leader", "system"
    ]):
        return [
            "Indian city traffic",
            "people walking city",
            "government building"
        ]

    return [
        "people working office",
        "Indian city street",
        "family at home"
    ]


def search_pexels(api_key, query):
    print("Searching stock footage:", query)

    response = requests.get(
        PEXELS_API,
        headers={"Authorization": api_key},
        params={
            "query": query,
            "orientation": "portrait",
            "per_page": 10
        },
        timeout=40
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Pexels API error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    return response.json().get("videos", [])


def choose_video_file(video):
    files = [
        item for item in video.get("video_files", [])
        if item.get("file_type") == "video/mp4"
        and item.get("link")
        and item.get("width")
        and item.get("height")
    ]

    if not files:
        return None

    # Prefer portrait footage, then the best available resolution.
    files.sort(
        key=lambda item: (
            abs(
                item["width"] / item["height"]
                - (9 / 16)
            ),
            -min(item["height"], 1920)
        )
    )

    return files[0]


def download_video(url, destination):
    response = requests.get(
        url,
        stream=True,
        timeout=120
    )

    response.raise_for_status()

    with open(destination, "wb") as file:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                file.write(chunk)

    if not destination.exists() or destination.stat().st_size < 10000:
        raise RuntimeError("Downloaded stock video is invalid.")


def collect_clips(api_key, queries):
    CLIPS.mkdir(parents=True, exist_ok=True)

    selected = []
    seen = set()

    for query in queries:
        videos = search_pexels(api_key, query)

        for video in videos:
            if video["id"] in seen:
                continue

            video_file = choose_video_file(video)

            if not video_file:
                continue

            seen.add(video["id"])

            selected.append({
                "id": video["id"],
                "url": video_file["link"],
                "photographer": video.get(
                    "user", {}
                ).get("name", "Pexels contributor")
            })

            if len(selected) >= 6:
                break

        if len(selected) >= 6:
            break

    if not selected:
        raise RuntimeError(
            "No suitable Pexels videos found. "
            "Try another search or check your API key."
        )

    downloaded = []

    for index, item in enumerate(selected):
        destination = CLIPS / f"clip_{index}.mp4"

        print("Downloading stock video", index + 1)

        download_video(
            item["url"],
            destination
        )

        downloaded.append({
            "path": destination,
            "photographer": item["photographer"]
        })

    return downloaded


def get_audio_duration(audio_file):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_file)
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return float(result.stdout.strip())


def render_scene(clip, destination, duration):
    print("Rendering scene:", destination.name)

    run_command([
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",
        "-i", str(clip),
        "-t", f"{duration:.3f}",
        "-vf",
        (
            "scale=1080:1920:"
            "force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "setsar=1,"
            "fps=30,"
            "eq=contrast=1.08:saturation=1.12"
        ),
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        str(destination)
    ])


def format_time(seconds):
    milliseconds = int(round(seconds * 1000))

    hours = milliseconds // 3600000
    milliseconds %= 3600000

    minutes = milliseconds // 60000
    milliseconds %= 60000

    secs = milliseconds // 1000
    milliseconds %= 1000

    return (
        f"{hours:02}:{minutes:02}:{secs:02},"
        f"{milliseconds:03}"
    )


def create_subtitles(script, duration):
    words = script.split()

    if not words:
        raise RuntimeError("Script is empty.")

    chunks = [
        " ".join(words[i:i + 5])
        for i in range(0, len(words), 5)
    ]

    total_words = len(words)
    current_time = 0.0
    entries = []

    for index, chunk in enumerate(chunks, start=1):
        count = len(chunk.split())
        segment_duration = duration * count / total_words

        start = current_time
        end = min(
            duration,
            current_time + segment_duration
        )

        entries.append(
            f"{index}\n"
            f"{format_time(start)} --> {format_time(end)}\n"
            f"{chunk}\n"
        )

        current_time = end

    subtitle_file = OUTPUT / "captions.srt"

    subtitle_file.write_text(
        "\n".join(entries),
        encoding="utf-8"
    )

    return subtitle_file


def create_video():
    api_key = os.getenv("PEXELS_API_KEY")

    if not api_key:
        raise RuntimeError(
            "PEXELS_API_KEY is missing. "
            "Add it to GitHub Secrets."
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)

    audio_file = OUTPUT / "voiceover.wav"
    script_file = OUTPUT / "short_script.txt"

    if not audio_file.exists():
        raise FileNotFoundError("Voiceover file is missing.")

    if not script_file.exists():
        raise FileNotFoundError("Script file is missing.")

    check_tools()

    script = script_file.read_text(
        encoding="utf-8"
    ).strip()

    duration = get_audio_duration(audio_file)

    print("Video duration:", duration)

    print("Finding relevant stock footage...")
    queries = get_search_queries(script)

    clips = collect_clips(
        api_key,
        queries
    )

    # Create a cinematic montage with scene changes.
    scene_count = min(
        6,
        max(3, math.ceil(duration / 7))
    )

    scene_duration = duration / scene_count

    scene_files = []

    for index in range(scene_count):
        clip = clips[index % len(clips)]["path"]

        scene_file = OUTPUT / f"scene_{index}.mp4"

        render_scene(
            clip,
            scene_file,
            scene_duration
        )

        scene_files.append(scene_file)

    # Join all scenes.
    concat_file = OUTPUT / "concat.txt"

    concat_file.write_text(
        "".join(
            f"file '{scene.resolve()}'\n"
            for scene in scene_files
        ),
        encoding="utf-8"
    )

    joined_file = OUTPUT / "joined_video.mp4"

    run_command([
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(joined_file)
    ])

    # Create subtitles.
    subtitle_file = create_subtitles(
        script,
        duration
    )

    # Credit the stock footage and its contributors.
    photographers = list(dict.fromkeys(
        item["photographer"] for item in clips
    ))

    credits = (
        "Stock footage: Pexels.com | "
        "Video contributors: "
        + ", ".join(photographers)
    )

    credit_file = OUTPUT / "stock_credits.txt"

    credit_file.write_text(
        credits,
        encoding="utf-8"
    )

    # Burn subtitles and Pexels attribution into the video.
    video_filter = (
        "subtitles=output/captions.srt:"
        "force_style='FontName=DejaVu Sans,"
        "FontSize=52,"
        "Bold=1,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00101010,"
        "BackColour=&H90000000,"
        "BorderStyle=3,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginV=260',"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/"
        "DejaVuSans.ttf:"
        "textfile=output/stock_credits.txt:"
        "fontsize=20:"
        "fontcolor=white@0.85:"
        "box=1:"
        "boxcolor=black@0.45:"
        "boxborderw=8:"
        "x=(w-text_w)/2:"
        "y=h-100"
    )

    music_file = Path("assets/background_music.mp3")
    final_file = OUTPUT / "short_video.mp4"

    if music_file.exists():
        print("Adding background music...")

        run_command([
            "ffmpeg",
            "-y",
            "-i", str(joined_file),
            "-i", str(audio_file),
            "-stream_loop", "-1",
            "-i", str(music_file),
            "-filter_complex",
            (
                "[1:a]volume=1.0[voice];"
                "[2:a]volume=0.12,"
                f"atrim=duration={duration:.3f}[music];"
                "[voice][music]amix=inputs=2:"
                "duration=first:"
                "dropout_transition=2[aout]"
            ),
            "-map", "0:v:0",
            "-map", "[aout]",
            "-vf", video_filter,
            "-t", f"{duration:.3f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(final_file)
        ])

    else:
        print(
            "No background music found. "
            "Using voiceover only."
        )

        run_command([
            "ffmpeg",
            "-y",
            "-i", str(joined_file),
            "-i", str(audio_file),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", video_filter,
            "-t", f"{duration:.3f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(final_file)
        ])

    print("\nCINEMATIC SHORT GENERATED SUCCESSFULLY!")
    print("Final video:", final_file)


if __name__ == "__main__":
    create_video()
