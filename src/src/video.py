
import subprocess
import shutil
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
            "FFmpeg error:\n" + result.stderr[-4000:]
        )


def get_font(size, bold=False):
    font_path = (
        "/usr/share/fonts/truetype/dejavu/"
        "DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/"
        "DejaVuSans.ttf"
    )
    return ImageFont.truetype(font_path, size)


def create_background():
    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (12, 17, 35)
    )

    draw = ImageDraw.Draw(image)

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

    draw.text(
        (90, 130),
        "SHAILENDRA TALKS",
        font=get_font(58, True),
        fill="white"
    )

    draw.text(
        (95, 220),
        "THE MIDDLE CLASS FILES",
        font=get_font(29),
        fill=(190, 200, 225)
    )

    draw.rounded_rectangle(
        (95, 305, 985, 315),
        radius=5,
        fill=(245, 180, 70)
    )

    draw.rounded_rectangle(
        (140, 700, 940, 1120),
        radius=35,
        outline=(245, 180, 70),
        width=5
    )

    draw.text(
        (540, 835),
        "SOCH BADLO.",
        font=get_font(65, True),
        fill="white",
        anchor="mm"
    )

    draw.text(
        (540, 930),
        "SAWAL PUCHHO.",
        font=get_font(65, True),
        fill=(245, 180, 70),
        anchor="mm"
    )

    draw.text(
        (540, 1730),
        "REAL TALK. NO FILTER.",
        font=get_font(29),
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
        " ".join(words[i:i + 7])
        for i in range(0, len(words), 7)
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


def generate_video():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    audio_file = OUTPUT / "voiceover.wav"
    script_file = OUTPUT / "short_script.txt"

    if not audio_file.exists():
        raise FileNotFoundError(
            "output/voiceover.wav is missing."
        )

    if not script_file.exists():
        raise FileNotFoundError(
            "output/short_script.txt is missing."
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

    print("Creating background...")
    create_background()

    duration = get_audio_duration(audio_file)

    print("Creating subtitles...")
    create_subtitles(script, duration)

    video_file = OUTPUT / "short_video.mp4"

    print("Rendering YouTube Shorts...")

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

    print("VIDEO GENERATED SUCCESSFULLY!")
    print("Saved:", video_file)


if __name__ == "__main__":
    generate_video()
