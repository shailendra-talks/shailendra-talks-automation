
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path("output")
WIDTH = 1080
HEIGHT = 1920
FPS = 30


def run_command(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n" + result.stderr[-4000:]
        )


def get_font(size, bold=False):
    if bold:
        font_path = (
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans-Bold.ttf"
        )
    else:
        font_path = (
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans.ttf"
        )

    if not Path(font_path).exists():
        raise FileNotFoundError(
            f"Font not found: {font_path}"
        )

    return ImageFont.truetype(font_path, size)


def create_background():
    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (12, 17, 35)
    )

    draw = ImageDraw.Draw(image)

    # Decorative background shapes
    draw.ellipse(
        (-250, 250, 650, 1150),
        fill=(25, 35, 75)
    )

    draw.ellipse(
        (550, 900, 1450, 1800),
        fill=(35, 25, 65)
    )

    draw.rectangle(
        (55, 65, 1025, 1855),
        outline=(95, 105, 145),
        width=3
    )

    # Channel branding
    title_font = get_font(58, bold=True)
    subtitle_font = get_font(29)

    draw.text(
        (90, 130),
        "SHAILENDRA TALKS",
        font=title_font,
        fill=(255, 255, 255)
    )

    draw.text(
        (95, 220),
        "THE MIDDLE CLASS FILES",
        font=subtitle_font,
        fill=(190, 200, 225)
    )

    # Decorative divider
    draw.rounded_rectangle(
        (95, 305, 985, 315),
        radius=5,
        fill=(245, 180, 70)
    )

    # Center graphic
    draw.rounded_rectangle(
        (140, 700, 940, 1120),
        radius=35,
        outline=(245, 180, 70),
        width=5
    )

    center_font = get_font(65, bold=True)

    draw.text(
        (WIDTH // 2, 835),
        "SOCH BADLO.",
        font=center_font,
        fill=(255, 255, 255),
        anchor="mm"
    )

    draw.text(
        (WIDTH // 2, 930),
        "SAWAL PUCHHO.",
        font=center_font,
        fill=(245, 180, 70),
        anchor="mm"
    )

    draw.text(
        (WIDTH // 2, 1730),
        "REAL TALK. NO FILTER.",
        font=subtitle_font,
        fill=(190, 200, 225),
        anchor="mm"
    )

    image.save(OUTPUT / "background.png")


def get_audio_duration(audio_file):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_file)
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Could not read audio duration: " + result.stderr
        )

    return float(result.stdout.strip())


def split_into_caption_lines(script):
    words = script.split()
    chunks = []

    # Keep captions short and readable
    for index in range(0, len(words), 7):
        chunks.append(" ".join(words[index:index + 7]))

    return chunks


def create_subtitles(script, duration):
    chunks = split_into_caption_lines(script)

    if not chunks:
        raise RuntimeError("No caption text found.")

    total_words = sum(
        len(chunk.split()) for chunk in chunks
    )

    current_time = 0.0
    subtitle_entries = []

    for index, chunk in enumerate(chunks, start=1):
        word_count = len(chunk.split())

        segment_duration = (
            duration * word_count / total_words
        )

        start = current_time
        end = min(
            duration,
            current_time + segment_duration
        )

        subtitle_entries.append(
            f"{index}\n"
            f"{format_time(start)} --> {format_time(end)}\n"
            f"{chunk}\n"
        )

        current_time = end

    subtitle_file = OUTPUT / "captions.srt"

    subtitle_file.write_text(
        "\n".join(subtitle_entries),
        encoding="utf-8"
    )

    return subtitle_file


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


def generate_video():
    audio_file = OUTPUT / "voiceover.wav"
    script_file = OUTPUT / "short_script.txt"

    if not audio_file.exists():
        raise FileNotFoundError(
            "Voice file missing: output/voiceover.wav"
        )

    if not script_file.exists():
        raise FileNotFoundError(
            "Script file missing: output/short_script.txt"
        )

    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is not installed.")

    if not shutil.which("ffprobe"):
        raise RuntimeError("FFprobe is not installed.")

    script = script_file.read_text(
        encoding="utf-8"
    ).strip()

    if not script:
        raise RuntimeError("Script is empty.")

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    print("Creating video background...")
    create_background()

    print("Reading audio duration...")
    duration = get_audio_duration(audio_file)

    print("Creating subtitles...")
    subtitle_file = create_subtitles(
        script,
        duration
    )

    video_file = OUTPUT / "short_video.mp4"

    print("Rendering YouTube Shorts video...")

    run_command([
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(OUTPUT / "background.png"),
        "-i", str(audio_file),
        "-vf",
        (
            "scale=1080:1920,"
            "subtitles=output/captions.srt:"
            "force_style='FontName=DejaVu Sans,"
            "FontSize=48,"
            "Bold=1,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BorderStyle=1,"
            "Outline=3,"
            "Shadow=1,"
            "Alignment=2,"
            "MarginV=260'"
        ),
        "-t", str(duration),
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(video_file)
    ])

    print("\nVIDEO GENERATED SUCCESSFULLY!")
    print("Saved:", video_file)


if __name__ == "__main__":
    generate_video()
