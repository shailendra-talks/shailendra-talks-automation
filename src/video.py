
import os
import json
import random
import subprocess
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


# =====================================================
# CONFIGURATION
# =====================================================

OUTPUT = Path("output")
SCENES_FILE = OUTPUT / "scenes.json"

PARTS_DIR = OUTPUT / "voice_parts"
FOOTAGE_DIR = OUTPUT / "footage"
SEGMENTS_DIR = OUTPUT / "segments"

FINAL_VIDEO = OUTPUT / "short_video.mp4"
SUBTITLE_FILE = OUTPUT / "captions.srt"

WIDTH = 720
HEIGHT = 1280
FPS = 25

PIXABAY_URL = "https://pixabay.com/api/videos/"

USED_VIDEO_IDS = set()


# =====================================================
# GENERAL UTILITIES
# =====================================================

def run(command):
    subprocess.run(command, check=True)


def get_duration(audio_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ],
        capture_output=True,
        text=True,
        check=True
    )

    duration = float(result.stdout.strip())

    if duration <= 0:
        raise RuntimeError(
            f"Invalid audio duration: {audio_path}"
        )

    return duration


def get_font(size, bold=False):

    if bold:
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]

    for font_path in candidates:
        if Path(font_path).exists():
            try:
                return ImageFont.truetype(
                    font_path,
                    size=size,
                    layout_engine=ImageFont.Layout.RAQM
                )
            except Exception:
                return ImageFont.truetype(font_path, size=size)

    raise RuntimeError(
        "No suitable font found. Check fonts-noto-core installation."
    )


# =====================================================
# PIXABAY FOOTAGE
# =====================================================

def download_footage(query, scene_number, api_key):

    if not api_key:
        print("Pixabay API key missing. Using fallback background.")
        return None

    try:
        response = requests.get(
            PIXABAY_URL,
            params={
                "key": api_key,
                "q": query,
                "per_page": 20,
                "safesearch": "true"
            },
            timeout=30
        )

        response.raise_for_status()

        hits = response.json().get("hits", [])
        random.shuffle(hits)

        for hit in hits:

            video_id = hit.get("id")

            if video_id in USED_VIDEO_IDS:
                continue

            videos = hit.get("videos", {})

            video_data = (
                videos.get("large")
                or videos.get("medium")
                or videos.get("small")
            )

            if not video_data:
                continue

            video_url = video_data.get("url")

            if not video_url:
                continue

            download = requests.get(
                video_url,
                timeout=90
            )

            download.raise_for_status()

            if len(download.content) < 10000:
                continue

            footage_path = (
                FOOTAGE_DIR /
                f"scene_{scene_number:03d}.mp4"
            )

            footage_path.write_bytes(download.content)

            USED_VIDEO_IDS.add(video_id)

            print(
                f"Footage downloaded for scene {scene_number}: "
                f"{query}"
            )

            return footage_path

    except Exception as error:
        print(
            f"Pixabay error in scene {scene_number}: {error}"
        )

    print(
        f"No suitable footage found for scene {scene_number}."
    )

    return None


# =====================================================
# FALLBACK BACKGROUND
# =====================================================

def create_background(scene_number):

    random.seed(scene_number)

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT)
    )

    draw = ImageDraw.Draw(image)

    top = (
        random.randint(10, 35),
        random.randint(15, 45),
        random.randint(35, 75)
    )

    bottom = (
        random.randint(35, 80),
        random.randint(15, 35),
        random.randint(25, 60)
    )

    for y in range(HEIGHT):

        ratio = y / HEIGHT

        color = tuple(
            int(
                top[i] * (1 - ratio)
                + bottom[i] * ratio
            )
            for i in range(3)
        )

        draw.line(
            (0, y, WIDTH, y),
            fill=color
        )

    for _ in range(10):

        x = random.randint(-100, WIDTH)
        y = random.randint(-100, HEIGHT)
        radius = random.randint(50, 170)

        draw.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius
            ),
            outline=(100, 110, 140),
            width=2
        )

    path = (
        FOOTAGE_DIR /
        f"background_{scene_number:03d}.jpg"
    )

    image.save(path, quality=90)

    return path


# =====================================================
# CAPTION GENERATION
# =====================================================

def wrap_text(text, font, draw, max_width):

    words = text.split()
    lines = []
    current_line = ""

    for word in words:

        test_line = (
            current_line + " " + word
        ).strip()

        bbox = draw.textbbox(
            (0, 0),
            test_line,
            font=font
        )

        text_width = bbox[2] - bbox[0]

        if text_width <= max_width:
            current_line = test_line

        else:
            if current_line:
                lines.append(current_line)

            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def create_caption(scene_number, narration):

    image = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(image)

    brand_font = get_font(25, bold=True)
    caption_font = get_font(39, bold=True)

    # Channel branding
    draw.rounded_rectangle(
        (35, 55, 365, 110),
        radius=18,
        fill=(0, 0, 0, 185)
    )

    draw.text(
        (52, 65),
        "SHAILENDRA TALKS",
        font=brand_font,
        fill=(255, 220, 80, 255)
    )

    # Captions contain only spoken narration.
    lines = wrap_text(
        narration,
        caption_font,
        draw,
        620
    )

    if len(lines) > 4:
        raise RuntimeError(
            f"Scene {scene_number} caption is too long. "
            "Split the narration into shorter scenes."
        )

    line_height = 57
    panel_height = len(lines) * line_height + 45

    panel_top = HEIGHT - panel_height - 105

    draw.rounded_rectangle(
        (
            25,
            panel_top,
            WIDTH - 25,
            HEIGHT - 80
        ),
        radius=22,
        fill=(0, 0, 0, 210)
    )

    y = panel_top + 20

    for line in lines:

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=caption_font
        )

        text_width = bbox[2] - bbox[0]
        x = (WIDTH - text_width) // 2

        draw.text(
            (x + 2, y + 3),
            line,
            font=caption_font,
            fill=(0, 0, 0, 255)
        )

        draw.text(
            (x, y),
            line,
            font=caption_font,
            fill=(255, 255, 255, 255),
            stroke_width=1,
            stroke_fill=(0, 0, 0, 255)
        )

        y += line_height

    caption_path = (
        OUTPUT /
        f"caption_{scene_number:03d}.png"
    )

    image.save(caption_path)

    return caption_path


# =====================================================
# SRT SUBTITLES
# =====================================================

def format_timestamp(seconds):

    milliseconds = int(
        round(seconds * 1000)
    )

    hours = milliseconds // 3600000
    milliseconds %= 3600000

    minutes = milliseconds // 60000
    milliseconds %= 60000

    secs = milliseconds // 1000
    milliseconds %= 1000

    return (
        f"{hours:02}:"
        f"{minutes:02}:"
        f"{secs:02},"
        f"{milliseconds:03}"
    )


def create_srt(scenes, durations):

    current_time = 0
    entries = []

    for index, scene in enumerate(scenes):

        narration = scene["narration"].strip()
        duration = durations[index]

        start = current_time
        end = current_time + duration

        entries.append(
            f"{index + 1}\n"
            f"{format_timestamp(start)} --> "
            f"{format_timestamp(end)}\n"
            f"{narration}\n"
        )

        current_time = end

    SUBTITLE_FILE.write_text(
        "\n".join(entries),
        encoding="utf-8"
    )


# =====================================================
# SCENE VIDEO GENERATION
# =====================================================

def create_scene_video(
    scene_number,
    footage_path,
    audio_path,
    caption_path
):

    duration = get_duration(audio_path)

    segment_path = (
        SEGMENTS_DIR /
        f"segment_{scene_number:03d}.mp4"
    )

    if footage_path.suffix.lower() in (
        ".jpg",
        ".jpeg",
        ".png"
    ):

        video_input = [
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", str(footage_path)
        ]

    else:

        video_input = [
            "-stream_loop", "-1",
            "-i", str(footage_path)
        ]

    command = [
        "ffmpeg",
        "-y",
        *video_input,

        "-i", str(audio_path),

        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(caption_path),

        "-filter_complex",
        (
            "[0:v]"
            "scale=720:1280:"
            "force_original_aspect_ratio=increase,"
            "crop=720:1280,"
            "setsar=1,"
            "fps=25"
            "[base];"
            "[2:v]"
            "format=rgba"
            "[caption];"
            "[base][caption]"
            "overlay=0:0:shortest=1,"
            "format=yuv420p"
            "[outv]"
        ),

        "-map", "[outv]",
        "-map", "1:a",

        "-t", f"{duration:.3f}",

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",

        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",

        "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",

        str(segment_path)
    ]

    run(command)

    return segment_path


# =====================================================
# FINAL VIDEO
# =====================================================

def combine_segments(segments):

    concat_file = OUTPUT / "segments_concat.txt"

    with concat_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        for segment in segments:
            file.write(
                f"file '{segment.resolve()}'\n"
            )

    run([
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",

        "-c:a", "aac",
        "-b:a", "128k",

        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-movflags", "+faststart",

        str(FINAL_VIDEO)
    ])


# =====================================================
# MAIN VIDEO GENERATOR
# =====================================================

def generate_video():

    print("\nSTARTING VIDEO GENERATION\n")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    FOOTAGE_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    if not SCENES_FILE.exists():
        raise FileNotFoundError(
            "output/scenes.json is missing. "
            "Run scripts.py first."
        )

    data = json.loads(
        SCENES_FILE.read_text(
            encoding="utf-8"
        )
    )

    scenes = data.get("scenes", [])

    if not scenes:
        raise RuntimeError(
            "No scenes found in scenes.json."
        )

    # Important: match the exact filenames created by voice.py.
    audio_files = []

    for index in range(1, len(scenes) + 1):

        audio_path = (
            PARTS_DIR /
            f"scene_{index:03d}.wav"
        )

        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio missing: {audio_path}. "
                "Run python -m src.voice successfully first."
            )

        audio_files.append(audio_path)

    print("Scenes found:", len(scenes))
    print("Matching audio files:", len(audio_files))

    # Remove old generated segments.
    for old_file in SEGMENTS_DIR.glob("*.mp4"):
        old_file.unlink()

    for old_file in OUTPUT.glob("caption_*.png"):
        old_file.unlink()

    api_key = os.getenv("PIXABAY_API_KEY")

    segments = []
    durations = []

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        narration = str(
            scene.get("narration", "")
        ).strip()

        visual_query = str(
            scene.get("visual_query", "")
        ).strip()

        if not narration:
            raise RuntimeError(
                f"Scene {index} has empty narration."
            )

        audio_path = audio_files[index - 1]

        print(
            f"\nCreating scene {index}/{len(scenes)}"
        )

        print("Visual query:", visual_query)

        footage_path = download_footage(
            visual_query or "Indian daily life",
            index,
            api_key
        )

        if footage_path is None:
            footage_path = create_background(index)

        caption_path = create_caption(
            index,
            narration
        )

        duration = get_duration(audio_path)
        durations.append(duration)

        segment = create_scene_video(
            index,
            footage_path,
            audio_path,
            caption_path
        )

        segments.append(segment)

        print("Scene completed:", index)

    if len(segments) != len(scenes):
        raise RuntimeError(
            "Final scene count does not match."
        )

    combine_segments(segments)

    create_srt(scenes, durations)

    if not FINAL_VIDEO.exists() or FINAL_VIDEO.stat().st_size == 0:
        raise RuntimeError(
            "Final video was not created correctly."
        )

    print("\n================================")
    print("VIDEO GENERATION SUCCESSFUL")
    print("================================")
    print("Scenes:", len(scenes))
    print("Audio parts:", len(audio_files))
    print("Final video:", FINAL_VIDEO)
    print("Subtitles:", SUBTITLE_FILE)
    print("================================")


if __name__ == "__main__":
    generate_video()
