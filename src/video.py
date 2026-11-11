
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WIDTH = 720
HEIGHT = 1280
FPS = 30

OUTPUT = Path("output")
SCRIPT_FILE = OUTPUT / "short_script.txt"
AUDIO_FILE = OUTPUT / "voiceover.wav"
VIDEO_FILE = OUTPUT / "short_video.mp4"


def run(command):
    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL
    )


def get_duration():
    result = subprocess.check_output([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(AUDIO_FILE)
    ])

    return float(result.decode().strip())


def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def split_script(text):
    sentences = re.split(r'(?<=[.!?।])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return [text.strip()]

    scenes = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) < 100:
            current += " " + sentence
        else:
            if current:
                scenes.append(current.strip())
            current = sentence

    if current:
        scenes.append(current.strip())

    return scenes[:9]


def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()

        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def create_scene(text, index, total):
    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()

    # Dark blue gradient background
    for y in range(HEIGHT):
        ratio = y / HEIGHT

        r = int(9 + ratio * 10)
        g = int(17 + ratio * 12)
        b = int(39 + ratio * 30)

        for x in range(WIDTH):
            pixels[x, y] = (r, g, b)

    draw = ImageDraw.Draw(image)

    # Decorative shapes
    draw.ellipse(
        (470, 120, 850, 500),
        outline=(35, 75, 125),
        width=5
    )

    draw.ellipse(
        (-170, 850, 250, 1270),
        outline=(30, 70, 115),
        width=5
    )

    # Brand
    brand_font = get_font(25, True)
    draw.text(
        (55, 65),
        "SHAILENDRA TALKS",
        font=brand_font,
        fill=(100, 190, 255)
    )

    # Scene number
    small_font = get_font(22)
    draw.text(
        (55, 145),
        f"INSIGHT  {index:02d} / {total:02d}",
        font=small_font,
        fill=(145, 165, 195)
    )

    # Accent line
    draw.rounded_rectangle(
        (55, 205, 165, 215),
        radius=5,
        fill=(55, 160, 255)
    )

    # Main text
    font = get_font(48, True)
    lines = wrap_text(text, font, 600, draw)

    line_height = 70
    total_height = len(lines) * line_height
    start_y = (HEIGHT - total_height) // 2

    for i, line in enumerate(lines):
        draw.text(
            (55, start_y + i * line_height),
            line,
            font=font,
            fill=(245, 248, 255),
            stroke_width=1,
            stroke_fill=(20, 35, 60)
        )

    # Bottom branding
    draw.line(
        (55, 1150, 665, 1150),
        fill=(55, 85, 125),
        width=2
    )

    draw.text(
        (55, 1175),
        "THINK DIFFERENT. QUESTION EVERYTHING.",
        font=get_font(17, True),
        fill=(140, 165, 195)
    )

    path = OUTPUT / f"scene_{index:02d}.png"
    image.save(path)

    return path


def create_subtitles(scenes, durations):
    current_time = 0
    subtitle_file = OUTPUT / "captions.srt"

    def timestamp(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)

        return (
            f"{hours:02d}:{minutes:02d}:"
            f"{secs:02d},{millis:03d}"
        )

    with open(subtitle_file, "w", encoding="utf-8") as f:
        for i, (scene, duration) in enumerate(zip(scenes, durations)):
            start = current_time
            end = current_time + duration

            f.write(f"{i + 1}\n")
            f.write(
                f"{timestamp(start)} --> {timestamp(end)}\n"
            )
            f.write(f"{scene}\n\n")

            current_time = end


def generate_video():
    OUTPUT.mkdir(exist_ok=True)

    if not SCRIPT_FILE.exists():
        raise FileNotFoundError("Script file missing.")

    if not AUDIO_FILE.exists():
        raise FileNotFoundError("Voiceover file missing.")

    script = SCRIPT_FILE.read_text(
        encoding="utf-8"
    ).strip()

    scenes = split_script(script)
    audio_duration = get_duration()

    # Divide video time according to scene length
    weights = [max(len(s), 1) for s in scenes]
    total_weight = sum(weights)

    durations = [
        audio_duration * weight / total_weight
        for weight in weights
    ]

    scene_files = []

    print("Creating professional faceless scenes...")

    for i, (scene, duration) in enumerate(
        zip(scenes, durations), start=1
    ):
        image_path = create_scene(
            scene,
            i,
            len(scenes)
        )

        video_path = OUTPUT / f"part_{i:02d}.mp4"

        frames = max(1, round(duration * FPS))

        run([
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", str(image_path),
            "-t", str(duration),
            "-vf",
            (
                "zoompan="
                "z='min(zoom+0.0005,1.06)':"
                "d=1:"
                "s=720x1280:"
                "fps=30,"
                "format=yuv420p"
            ),
            "-an",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(video_path)
        ])

        scene_files.append(video_path)

    # Join scenes
    concat_file = OUTPUT / "concat.txt"

    with open(concat_file, "w") as f:
        for path in scene_files:
            f.write(f"file '{path.resolve()}'\n")

    silent_video = OUTPUT / "silent_video.mp4"

    run([
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(silent_video)
    ])

    # Add AI voiceover
    run([
        "ffmpeg",
        "-y",
        "-i", str(silent_video),
        "-i", str(AUDIO_FILE),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(VIDEO_FILE)
    ])

    create_subtitles(scenes, durations)

    print("\nVIDEO GENERATED SUCCESSFULLY!")
    print("Video:", VIDEO_FILE)
    print("Subtitles:", OUTPUT / "captions.srt")


if __name__ == "__main__":
    generate_video()
