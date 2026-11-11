
import os
import re
import json
import time
import subprocess
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path("output")
SCRIPT_FILE = OUTPUT / "short_script.txt"
PARTS_DIR = OUTPUT / "voice_parts"
SCENES_DIR = OUTPUT / "scenes"
SEGMENTS_DIR = OUTPUT / "segments"

CACHE_FILE = OUTPUT / "pixabay_cache.json"

WIDTH = 720
HEIGHT = 1280
FPS = 25

PALETTES = [
    ((8, 20, 42), (20, 65, 105), (0, 210, 190)),
    ((28, 12, 48), (83, 32, 105), (255, 180, 65)),
    ((12, 35, 32), (20, 100, 78), (150, 230, 120)),
    ((45, 17, 20), (120, 38, 48), (255, 190, 110)),
    ((15, 25, 55), (45, 65, 130), (120, 190, 255)),
]


def run_command(command):
    subprocess.run(command, check=True)


def split_sentences(text):
    # Keep the same sentence splitting method as voice.py.
    sentences = re.split(r'(?<=[.!?।])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def get_duration(audio_path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ],
        capture_output=True,
        text=True,
        check=True
    )
    return float(result.stdout.strip())


def get_font(size):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]

    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def query_for_sentence(sentence, index):
    text = sentence.lower()

    topics = [
        (
            ["parliament", "politics", "political", "election",
             "government", "leader", "minister", "sarkar",
             "neta", "chunav", "राजनीति", "सरकार", "चुनाव"],
            [
                "india parliament political",
                "indian election campaign crowd",
                "government building india",
                "politician public speech"
            ]
        ),
        (
            ["education", "school", "college", "student",
             "teacher", "शिक्षा", "स्कूल", "कॉलेज", "छात्र"],
            [
                "students classroom education",
                "college students studying",
                "school classroom india",
                "university campus students"
            ]
        ),
        (
            ["police", "crime", "court", "justice", "law",
             "अदालत", "न्याय", "कानून", "अपराध"],
            [
                "police officer india",
                "courthouse justice law",
                "courtroom legal system",
                "police investigation crime"
            ]
        ),
        (
            ["money", "finance", "business", "economy",
             "paisa", "महंगाई", "पैसा", "बैंक", "व्यापार"],
            [
                "money finance business",
                "indian market shopping",
                "business office finance",
                "counting money cash"
            ]
        ),
        (
            ["social media", "internet", "mobile", "phone",
             "instagram", "youtube", "सोशल मीडिया", "मोबाइल"],
            [
                "smartphone social media",
                "person using mobile phone",
                "social media technology",
                "digital technology internet"
            ]
        ),
        (
            ["traffic", "road", "city", "transport",
             "सड़क", "शहर", "ट्रैफिक"],
            [
                "india city traffic street",
                "busy indian road traffic",
                "urban city street people",
                "vehicles traffic city"
            ]
        ),
        (
            ["hospital", "doctor", "health", "medical",
             "अस्पताल", "डॉक्टर", "स्वास्थ्य"],
            [
                "hospital doctor healthcare",
                "medical hospital corridor",
                "doctor patient consultation",
                "healthcare medical team"
            ]
        ),
        (
            ["environment", "pollution", "climate", "nature",
             "प्रदूषण", "पर्यावरण", "पेड़"],
            [
                "environment pollution city",
                "air pollution urban city",
                "forest nature environment",
                "climate change environment"
            ]
        ),
        (
            ["protest", "public", "crowd", "people",
             "जनता", "प्रदर्शन", "आंदोलन"],
            [
                "people crowd public protest",
                "public gathering crowd",
                "people walking city",
                "large crowd demonstration"
            ]
        ),
        (
            ["family", "middle class", "ghar", "परिवार",
             "मध्यम वर्ग", "घर"],
            [
                "indian family daily life",
                "family sitting living room",
                "middle class family home",
                "indian household daily life"
            ]
        )
    ]

    for keywords, queries in topics:
        if any(word in text for word in keywords):
            return queries[index % len(queries)]

    general_queries = [
        "indian city documentary people",
        "people walking urban street",
        "indian lifestyle documentary",
        "busy city life india"
    ]

    return general_queries[index % len(general_queries)]


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(
                CACHE_FILE.read_text(encoding="utf-8")
            )
        except Exception:
            pass

    return {}


def save_cache(cache):
    OUTPUT.mkdir(parents=True, exist_ok=True)

    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def search_pixabay(query, api_key, cache):
    now = time.time()
    cached = cache.get(query)

    if cached and now - cached.get("time", 0) < 86400:
        return cached.get("hits", [])

    response = requests.get(
        "https://pixabay.com/api/videos/",
        params={
            "key": api_key,
            "q": query,
            "per_page": 20,
            "safesearch": "true"
        },
        timeout=45
    )

    response.raise_for_status()
    hits = response.json().get("hits", [])

    cache[query] = {
        "time": now,
        "hits": hits
    }

    save_cache(cache)
    return hits


def download_footage(
    sentence, index, api_key, cache, used_ids, credits
):
    query = query_for_sentence(sentence, index)

    print(f"Searching visual for scene {index + 1}: {query}")

    try:
        hits = search_pixabay(query, api_key, cache)

        # Never reuse an already-used video.
        available = [
            hit for hit in hits
            if hit.get("id") not in used_ids
            and hit.get("videos", {}).get("medium", {}).get("url")
        ]

        if not available:
            print("No new unique Pixabay footage found.")
            return None

        hit = available[0]
        video_id = hit.get("id")

        video_url = hit["videos"]["medium"]["url"]
        video_path = SCENES_DIR / f"footage_{index + 1:03d}.mp4"

        response = requests.get(
            video_url,
            timeout=120,
            stream=True
        )
        response.raise_for_status()

        with open(video_path, "wb") as file:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    file.write(chunk)

        used_ids.add(video_id)

        credits.append(
            f"Scene {index + 1}: "
            f"{hit.get('user', 'Pixabay contributor')} - "
            f"{hit.get('pageURL', 'Pixabay')}"
        )

        print(f"Downloaded unique footage ID: {video_id}")

        return video_path

    except Exception as error:
        print("Pixabay error:", error)
        return None


def create_fallback_background(index):
    top, bottom, accent = PALETTES[index % len(PALETTES)]

    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()

    for y in range(HEIGHT):
        ratio = y / HEIGHT

        color = tuple(
            int(top[c] * (1 - ratio) + bottom[c] * ratio)
            for c in range(3)
        )

        for x in range(WIDTH):
            pixels[x, y] = color

    draw = ImageDraw.Draw(image)

    pattern = index % 5

    if pattern == 0:
        draw.ellipse(
            (350, 150, 850, 650),
            outline=accent,
            width=10
        )

    elif pattern == 1:
        for x in range(-300, WIDTH, 90):
            draw.line(
                (x, 0, x + 500, HEIGHT),
                fill=accent,
                width=4
            )

    elif pattern == 2:
        draw.rectangle(
            (70, 250, 650, 260),
            fill=accent
        )
        draw.ellipse(
            (100, 700, 600, 1200),
            outline=accent,
            width=8
        )

    elif pattern == 3:
        for y in range(200, 1100, 130):
            draw.rounded_rectangle(
                (70, y, 650, y + 35),
                radius=15,
                fill=accent
            )

    else:
        draw.polygon(
            [(360, 200), (650, 650), (360, 1100), (70, 650)],
            outline=accent,
            width=10
        )

    path = SCENES_DIR / f"fallback_{index + 1:03d}.png"
    image.save(path)

    return path


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), test, font=font)

        if box[2] - box[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


def create_overlay(sentence, index, is_pixabay):
    _, _, accent = PALETTES[index % len(PALETTES)]

    overlay = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(overlay)

    # Top branding
    draw.rounded_rectangle(
        (35, 55, 390, 120),
        radius=18,
        fill=(0, 0, 0, 175)
    )

    draw.text(
        (55, 72),
        "SHAILENDRA TALKS",
        font=get_font(25),
        fill=(255, 255, 255, 255)
    )

    draw.rounded_rectangle(
        (35, 145, 200, 153),
        radius=4,
        fill=(*accent, 255)
    )

    # Subtitle panel
    draw.rounded_rectangle(
        (28, 935, 692, 1195),
        radius=25,
        fill=(0, 0, 0, 215),
        outline=(*accent, 255),
        width=3
    )

    font_size = 38
    lines = []

    while font_size >= 22:
        font = get_font(font_size)
        lines = wrap_text(draw, sentence, font, 590)

        if len(lines) <= 3:
            break

        font_size -= 2

    font = get_font(font_size)

    # Keep the full sentence readable.
    line_height = font_size + 18
    total_height = len(lines) * line_height
    y = 1065 - total_height // 2

    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        line_width = box[2] - box[0]
        x = (WIDTH - line_width) // 2

        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 255, 255, 255)
        )

        y += line_height

    source_text = "PIXABAY FOOTAGE" if is_pixabay else "ANIMATED SCENE"

    draw.text(
        (465, 1210),
        source_text,
        font=get_font(16),
        fill=(255, 255, 255, 220)
    )

    path = SCENES_DIR / f"overlay_{index + 1:03d}.png"
    overlay.save(path)

    return path


def format_srt_time(seconds):
    milliseconds = round(seconds * 1000)

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


def create_segment(
    background, audio, overlay, duration, output_path
):
    is_video = background.suffix.lower() == ".mp4"

    command = ["ffmpeg", "-y"]

    if is_video:
        command += [
            "-stream_loop", "-1",
            "-i", str(background)
        ]
    else:
        command += [
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", str(background)
        ]

    command += [
        "-i", str(audio),
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(overlay),
        "-filter_complex",
        (
            "[0:v]"
            "scale=720:1280:force_original_aspect_ratio=increase,"
            "crop=720:1280,"
            "fps=25,"
            "setsar=1[bg];"
            "[2:v]format=rgba[ov];"
            "[bg][ov]overlay=0:0:format=auto,"
            "format=yuv420p[v]"
        ),
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-t", str(duration),
        "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path)
    ]

    run_command(command)


def generate_video():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("PIXABAY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "PIXABAY_API_KEY is missing in GitHub Secrets."
        )

    if not SCRIPT_FILE.exists():
        raise FileNotFoundError("Script file not found.")

    script = SCRIPT_FILE.read_text(
        encoding="utf-8"
    ).strip()

    sentences = split_sentences(script)

    audio_files = sorted(
        PARTS_DIR.glob("part_*.wav")
    )

    if not sentences:
        raise RuntimeError("No sentences found in script.")

    if len(sentences) != len(audio_files):
        raise RuntimeError(
            f"Audio/script mismatch: {len(sentences)} sentences "
            f"but {len(audio_files)} audio parts. "
            "Check the sentence splitting in voice.py."
        )

    # Clean old generated scenes and segments.
    for folder in [SCENES_DIR, SEGMENTS_DIR]:
        for old_file in folder.iterdir():
            if old_file.is_file():
                old_file.unlink()

    cache = load_cache()
    used_ids = set()
    credits = []

    subtitles = []
    segment_files = []

    current_time = 0.0

    print(f"Total sentences: {len(sentences)}")
    print(f"Total audio parts: {len(audio_files)}")

    for index, (sentence, audio_path) in enumerate(
        zip(sentences, audio_files)
    ):
        print(
            f"\nCreating scene {index + 1}/{len(sentences)}"
        )

        duration = get_duration(audio_path)

        if duration <= 0:
            raise RuntimeError(
                f"Invalid audio duration: {audio_path}"
            )

        footage = download_footage(
            sentence,
            index,
            api_key,
            cache,
            used_ids,
            credits
        )

        is_pixabay = footage is not None

        if footage is None:
            print("Creating a different animated fallback scene.")
            footage = create_fallback_background(index)

        overlay = create_overlay(
            sentence,
            index,
            is_pixabay
        )

        segment_path = (
            SEGMENTS_DIR /
            f"segment_{index + 1:03d}.mp4"
        )

        create_segment(
            footage,
            audio_path,
            overlay,
            duration,
            segment_path
        )

        segment_files.append(segment_path)

        start = current_time
        end = current_time + duration

        subtitles.append(
            f"{index + 1}\n"
            f"{format_srt_time(start)} --> "
            f"{format_srt_time(end)}\n"
            f"{sentence}\n"
        )

        current_time = end

    # Save subtitles with separate timing for every sentence.
    (OUTPUT / "captions.srt").write_text(
        "\n".join(subtitles),
        encoding="utf-8"
    )

    # Save footage credits.
    (OUTPUT / "pixabay_credits.txt").write_text(
        "\n".join(credits)
        if credits
        else "No Pixabay footage was downloaded.",
        encoding="utf-8"
    )

    save_cache(cache)

    # Create concat list.
    concat_path = OUTPUT / "video_concat.txt"

    with open(
        concat_path, "w", encoding="utf-8"
    ) as file:
        for segment in segment_files:
            safe_path = str(segment.resolve()).replace(
                "'", "'\\''"
            )
            file.write(f"file '{safe_path}'\n")

    final_video = OUTPUT / "short_video.mp4"

    # Re-encode final output to avoid timestamp/stream-copy issues.
    run_command(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_path),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-r", str(FPS),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(final_video)
        ]
    )

    print("\nVIDEO GENERATION SUCCESSFUL")
    print("Scenes created:", len(segment_files))
    print("Unique Pixabay videos:", len(used_ids))
    print("Final video:", final_video)
    print("Captions:", OUTPUT / "captions.srt")
    print("Credits:", OUTPUT / "pixabay_credits.txt")


if __name__ == "__main__":
    generate_video()
