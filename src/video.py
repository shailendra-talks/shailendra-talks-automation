
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
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]

    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def query_for_sentence(sentence):
    text = sentence.lower()

    topics = [
        (["parliament", "politics", "political", "election",
          "government", "leader", "minister", "sarkar",
          "neta", "chunav", "राजनीति", "सरकार", "चुनाव"],
         "india parliament political speech"),

        (["education", "school", "college", "student",
          "teacher", "शिक्षा", "स्कूल", "कॉलेज", "छात्र"],
         "students classroom education"),

        (["police", "crime", "court", "justice", "law",
          "police", "अदालत", "न्याय", "कानून", "अपराध"],
         "police justice courthouse"),

        (["money", "finance", "business", "economy",
          "paisa", "महंगाई", "पैसा", "बैंक", "व्यापार"],
         "money business finance"),

        (["social media", "internet", "mobile", "phone",
          "instagram", "youtube", "सोशल मीडिया", "मोबाइल"],
         "smartphone social media technology"),

        (["traffic", "road", "city", "transport",
          "सड़क", "शहर", "ट्रैफिक"],
         "india city traffic street"),

        (["hospital", "doctor", "health", "medical",
          "अस्पताल", "डॉक्टर", "स्वास्थ्य"],
         "hospital doctor healthcare"),

        (["environment", "pollution", "climate", "nature",
          "प्रदूषण", "पर्यावरण", "पेड़"],
         "environment pollution city"),

        (["protest", "public", "crowd", "people",
          "जनता", "प्रदर्शन", "आंदोलन"],
         "people crowd public protest"),

        (["family", "middle class", "ghar", "परिवार",
          "मध्यम वर्ग", "घर"],
         "indian family daily life"),
    ]

    for keywords, query in topics:
        if any(word in text for word in keywords):
            return query

    return "people walking city street documentary"


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {}


def save_cache(cache):
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def search_pixabay(query, api_key, cache):
    now = time.time()
    cached = cache.get(query)

    # Reuse cached results for 24 hours
    if cached and now - cached.get("time", 0) < 86400:
        return cached.get("hits", [])

    response = requests.get(
        "https://pixabay.com/api/videos/",
        params={
            "key": api_key,
            "q": query,
            "per_page": 10,
            "safesearch": "true",
            "video_type": "film"
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


def download_footage(sentence, index, api_key, cache, used_ids, credits):
    query = query_for_sentence(sentence)

    print(f"Searching Pixabay: {query}")

    try:
        hits = search_pixabay(query, api_key, cache)

        available = [
            hit for hit in hits
            if hit.get("id") not in used_ids
            and hit.get("videos", {}).get("medium", {}).get("url")
        ]

        if not available:
            available = [
                hit for hit in hits
                if hit.get("videos", {}).get("medium", {}).get("url")
            ]

        if not available:
            return None

        hit = available[0]
        used_ids.add(hit.get("id"))

        video_url = hit["videos"]["medium"]["url"]

        video_path = SCENES_DIR / f"footage_{index + 1:03d}.mp4"

        video_response = requests.get(
            video_url,
            timeout=120,
            stream=True
        )
        video_response.raise_for_status()

        with open(video_path, "wb") as file:
            for chunk in video_response.iter_content(1024 * 1024):
                if chunk:
                    file.write(chunk)

        credits.append(
            f"Scene {index + 1}: "
            f"{hit.get('user', 'Pixabay contributor')} - "
            f"{hit.get('pageURL', 'Pixabay')}"
        )

        print("Downloaded footage:", hit.get("id"))
        return video_path

    except Exception as error:
        print("Pixabay footage unavailable:", error)
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

    if index % 3 == 0:
        draw.ellipse((400, 150, 900, 650), outline=accent, width=8)
    elif index % 3 == 1:
        for x in range(0, WIDTH, 80):
            draw.line((x, 0, x + 200, HEIGHT), fill=accent, width=3)
    else:
        draw.rectangle((70, 250, 650, 260), fill=accent)
        draw.ellipse((100, 700, 600, 1200), outline=accent, width=7)

    path = SCENES_DIR / f"fallback_{index + 1:03d}.png"
    image.save(path)
    return path


def create_overlay(sentence, index):
    _, _, accent = PALETTES[index % len(PALETTES)]

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Top branding
    draw.rounded_rectangle(
        (35, 55, 360, 120),
        radius=18,
        fill=(0, 0, 0, 150)
    )

    draw.text(
        (55, 72),
        "SHAILENDRA TALKS",
        font=get_font(25),
        fill=(255, 255, 255, 255)
    )

    # Small accent line
    draw.rounded_rectangle(
        (35, 145, 200, 153),
        radius=4,
        fill=(*accent, 255)
    )

    # Bottom subtitles panel
    draw.rounded_rectangle(
        (28, 955, 692, 1195),
        radius=25,
        fill=(0, 0, 0, 205),
        outline=(*accent, 230),
        width=3
    )

    words = sentence.split()
    font_size = 38
    lines = []

    # Keep subtitles within two lines
    while font_size >= 22:
        font = get_font(font_size)
        lines = []
        current = ""

        for word in words:
            test = f"{current} {word}".strip()
            width = draw.textbbox((0, 0), test, font=font)[2]

            if width <= 600:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

        if len(lines) <= 2:
            break

        font_size -= 2

    if len(lines) > 2:
        midpoint = len(words) // 2
        lines = [
            " ".join(words[:midpoint]),
            " ".join(words[midpoint:])
        ]

    font = get_font(font_size)
    line_height = font_size + 18
    total_height = len(lines) * line_height

    y = 1075 - total_height // 2

    for line in lines:
        draw.text(
            (60, y),
            line,
            font=font,
            fill=(255, 255, 255, 255)
        )
        y += line_height

    # Small source label
    draw.text(
        (500, 1210),
        "FOOTAGE: PIXABAY",
        font=get_font(16),
        fill=(255, 255, 255, 210)
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


def create_segment(background, audio, overlay, duration, output_path):
    is_video = background.suffix.lower() == ".mp4"

    command = ["ffmpeg", "-y"]

    if is_video:
        command += ["-stream_loop", "-1", "-i", str(background)]
    else:
        command += ["-loop", "1", "-framerate", str(FPS), "-i", str(background)]

    command += [
        "-i", str(audio),
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(overlay),
        "-filter_complex",
        (
            "[0:v]scale=720:1280:"
            "force_original_aspect_ratio=increase,"
            "crop=720:1280,fps=25[bg];"
            "[2:v]format=rgba[ov];"
            "[bg][ov]overlay=0:0:shortest=1,"
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
        "-movflags", "+faststart",
        str(output_path)
    ]

    subprocess.run(command, check=True)


def generate_video():
    api_key = os.getenv("PIXABAY_API_KEY")

    if not api_key:
        raise RuntimeError("PIXABAY_API_KEY is missing in GitHub Secrets.")

    if not SCRIPT_FILE.exists():
        raise FileNotFoundError("Script file not found.")

    script = SCRIPT_FILE.read_text(encoding="utf-8").strip()
    sentences = split_sentences(script)

    audio_files = sorted(PARTS_DIR.glob("part_*.wav"))

    if len(sentences) != len(audio_files):
        raise RuntimeError(
            f"Mismatch: {len(sentences)} sentences and "
            f"{len(audio_files)} audio parts."
        )

    for folder in [SCENES_DIR, SEGMENTS_DIR]:
        folder.mkdir(parents=True, exist_ok=True)

        for old_file in folder.iterdir():
            if old_file.is_file():
                old_file.unlink()

    cache = load_cache()
    used_ids = set()
    credits = []

    subtitles = []
    segment_files = []
    current_time = 0.0

    print(f"Creating {len(sentences)} hybrid documentary scenes...")

    for index, (sentence, audio_path) in enumerate(
        zip(sentences, audio_files)
    ):

        print(f"\nScene {index + 1}/{len(sentences)}")

        duration = get_duration(audio_path)

        if duration <= 0:
            raise RuntimeError("Invalid audio duration.")

        footage = download_footage(
            sentence,
            index,
            api_key,
            cache,
            used_ids,
            credits
        )

        if footage is None:
            print("Using animated background fallback.")
            footage = create_fallback_background(index)

        overlay = create_overlay(sentence, index)

        segment_path = SEGMENTS_DIR / f"segment_{index + 1:03d}.mp4"

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

    # Save captions
    (OUTPUT / "captions.srt").write_text(
        "\n".join(subtitles),
        encoding="utf-8"
    )

    # Save footage credits
    (OUTPUT / "pixabay_credits.txt").write_text(
        "\n".join(credits) if credits else
        "No Pixabay footage was downloaded.",
        encoding="utf-8"
    )

    # Save cache for next workflow run
    save_cache(cache)

    # Join all scenes
    concat_path = OUTPUT / "video_concat.txt"

    with open(concat_path, "w", encoding="utf-8") as file:
        for segment in segment_files:
            file.write(f"file '{segment.resolve()}'\n")

    final_video = OUTPUT / "short_video.mp4"

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_path),
            "-c", "copy",
            "-movflags", "+faststart",
            str(final_video)
        ],
        check=True
    )

    print("\nHYBRID VIDEO GENERATION SUCCESSFUL!")
    print("Scenes:", len(sentences))
    print("Video:", final_video)
    print("Captions:", OUTPUT / "captions.srt")
    print("Credits:", OUTPUT / "pixabay_credits.txt")


if __name__ == "__main__":
    generate_video()
