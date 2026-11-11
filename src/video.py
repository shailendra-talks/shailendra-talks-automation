
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path("output")
SCRIPT_FILE = OUTPUT / "short_script.txt"
PARTS_DIR = OUTPUT / "voice_parts"
SCENES_DIR = OUTPUT / "scenes"
SEGMENTS_DIR = OUTPUT / "segments"

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


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), test, font=font)[2]

        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def create_scene(text, index):
    palette = PALETTES[index % len(PALETTES)]
    top, bottom, accent = palette

    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()

    # Gradient background
    for y in range(HEIGHT):
        ratio = y / HEIGHT

        color = tuple(
            int(top[c] * (1 - ratio) + bottom[c] * ratio)
            for c in range(3)
        )

        for x in range(WIDTH):
            pixels[x, y] = color

    draw = ImageDraw.Draw(image)

    # Different decorative layouts
    if index % 3 == 0:
        draw.ellipse((470, 100, 850, 480), outline=accent, width=5)
        draw.ellipse((510, 140, 810, 440), outline=accent, width=2)
        draw.rectangle((55, 240, 70, 900), fill=accent)

    elif index % 3 == 1:
        for x in range(60, 700, 90):
            draw.line((x, 180, x + 100, 1080), fill=accent, width=2)
        draw.rectangle((55, 260, 665, 270), fill=accent)

    else:
        draw.ellipse((420, 760, 850, 1190), outline=accent, width=6)
        draw.ellipse((470, 810, 800, 1140), outline=accent, width=2)
        draw.rectangle((55, 280, 665, 285), fill=accent)

    # Brand heading
    small_font = get_font(27)
    draw.text(
        (60, 100),
        "SHAILENDRA TALKS",
        font=small_font,
        fill=(255, 255, 255)
    )

    draw.text(
        (60, 155),
        f"REAL TALK  /  {index + 1:02d}",
        font=get_font(19),
        fill=accent
    )

    # Main sentence
    font_size = 54
    max_width = 590

    while font_size >= 30:
        font = get_font(font_size)
        lines = wrap_text(draw, text, font, max_width)

        if len(lines) <= 7:
            break

        font_size -= 3

    text_block = "\n".join(lines)

    box = draw.multiline_textbbox(
        (0, 0),
        text_block,
        font=font,
        spacing=20,
        align="left"
    )

    text_height = box[3] - box[1]
    y_position = (HEIGHT - text_height) // 2

    # Dark translucent-style text panel
    draw.rounded_rectangle(
        (35, y_position - 45, 685, y_position + text_height + 55),
        radius=25,
        fill=(8, 12, 25)
    )

    draw.rectangle(
        (35, y_position - 45, 47, y_position + text_height + 55),
        fill=accent
    )

    draw.multiline_text(
        (70, y_position),
        text_block,
        font=font,
        fill=(255, 255, 255),
        spacing=20,
        align="left"
    )

    draw.text(
        (60, 1170),
        "THINK. QUESTION. UNDERSTAND.",
        font=get_font(21),
        fill=accent
    )

    image_path = SCENES_DIR / f"scene_{index + 1:03d}.png"
    image.save(image_path)

    return image_path


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


def generate_video():
    if not SCRIPT_FILE.exists():
        raise FileNotFoundError("Script file not found.")

    script = SCRIPT_FILE.read_text(encoding="utf-8").strip()
    sentences = split_sentences(script)

    audio_files = sorted(PARTS_DIR.glob("part_*.wav"))

    if not sentences:
        raise RuntimeError("No sentences found in script.")

    if len(sentences) != len(audio_files):
        raise RuntimeError(
            f"Mismatch: {len(sentences)} sentences but "
            f"{len(audio_files)} audio files. "
            "Please regenerate voiceover."
        )

    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    # Clean old generated files
    for folder in [SCENES_DIR, SEGMENTS_DIR]:
        for file in folder.iterdir():
            if file.is_file():
                file.unlink()

    subtitles = []
    segment_files = []
    current_time = 0.0

    print(f"Creating {len(sentences)} visual scenes...")

    for index, (sentence, audio_path) in enumerate(
        zip(sentences, audio_files)
    ):

        print(f"Rendering scene {index + 1}/{len(sentences)}")

        duration = get_duration(audio_path)

        if duration <= 0:
            raise RuntimeError(f"Invalid audio duration: {audio_path}")

        image_path = create_scene(sentence, index)

        segment_path = SEGMENTS_DIR / f"segment_{index + 1:03d}.mp4"

        frames = max(1, round(duration * FPS))

        zoom = [
            "zoompan="
            f"z='min(zoom+0.0008,1.08)':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            f"d={frames}:"
            f"s={WIDTH}x{HEIGHT}:"
            f"fps={FPS}"
        ]

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(image_path),
                "-i", str(audio_path),
                "-vf", zoom[0],
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", str(duration),
                "-shortest",
                "-movflags", "+faststart",
                str(segment_path)
            ],
            check=True
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

    # Create subtitle file
    subtitle_path = OUTPUT / "captions.srt"
    subtitle_path.write_text(
        "\n".join(subtitles),
        encoding="utf-8"
    )

    # Join all audio-video scenes
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

    print("\nVIDEO GENERATION SUCCESSFUL!")
    print("Scenes:", len(sentences))
    print("Video:", final_video)
    print("Captions:", subtitle_path)


if __name__ == "__main__":
    generate_video()
