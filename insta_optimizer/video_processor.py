import os
import json
import subprocess
from typing import Dict, Any, Tuple, Optional
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

from insta_optimizer.utils import calculate_dimensions, parse_color

def probe_video(input_path: str) -> Dict[str, Any]:
    """
    Use ffprobe to query video dimensions, duration, audio streams, and rotation metadata.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        input_path
    ]
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    metadata = json.loads(result.stdout)
    
    # Extract properties
    video_stream = None
    has_audio = False
    
    for stream in metadata.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and video_stream is None:
            video_stream = stream
        elif codec_type == "audio":
            has_audio = True
            
    if not video_stream:
        raise ValueError(f"No video streams found in {input_path}")
        
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    
    # Determine duration
    duration = float(metadata.get("format", {}).get("duration", 0.0))
    if duration <= 0:
        duration = float(video_stream.get("duration", 0.0))
        
    # Check frame rate
    r_frame_rate = video_stream.get("r_frame_rate", "30/1")
    try:
        num, den = map(int, r_frame_rate.split("/"))
        frame_rate = num / den if den > 0 else 30.0
    except Exception:
        frame_rate = 30.0
        
    # Detect rotation metadata (e.g. shot portrait on phone, rotate tags)
    rotation = 0
    # 1. Check side data list
    for side_data in video_stream.get("side_data_list", []):
        if side_data.get("side_data_type") == "Display Matrix":
            rotation = abs(int(side_data.get("rotation", 0)))
            
    # 2. Check tags
    if rotation == 0:
        rotate_tag = video_stream.get("tags", {}).get("rotate")
        if rotate_tag:
            try:
                rotation = abs(int(rotate_tag))
            except ValueError:
                pass
                
    # If 90 or 270 degrees, swap width and height for sizing calculations since ffmpeg
    # will auto-rotate the input frames before feeding them to filters.
    if rotation in (90, 270):
        width, height = height, width
        
    return {
        "width": width,
        "height": height,
        "duration": duration,
        "has_audio": has_audio,
        "frame_rate": frame_rate,
        "rotation": rotation
    }

def optimize_video(
    input_path: str,
    output_path: str,
    target_w: int,
    target_h: int,
    mode: str = "fit",
    mat_color_str: str = "white",
    padding_pct: float = 0.0,
    bitrate_kbps: int = 8000,
    status_prefix: str = "Processing video"
) -> None:
    """
    Optimize a video for Instagram, performing H.264 transcoding, AAC audio encoding, Rec. 709 color tags,
    and optional matting/borders.
    """
    # 1. Probe source video metadata
    info = probe_video(input_path)
    input_w = info["width"]
    input_h = info["height"]
    duration = info["duration"]
    has_audio = info["has_audio"]
    frame_rate = info["frame_rate"]
    
    # 2. Calculate scaling dimensions (video dimensions must be even for H.264)
    scaled_w, scaled_h, x_off, y_off = calculate_dimensions(
        input_w, input_h, target_w, target_h,
        mode=mode, padding_pct=padding_pct, force_even=True
    )
    
    # 3. Build FFmpeg filter arguments
    _, ffmpeg_color = parse_color(mat_color_str)
    
    filters = []
    if mode == "fit":
        # Scale with high quality Lanczos filter, then pad
        filters.append(f"scale={scaled_w}:{scaled_h}:flags=lanczos")
        filters.append(f"pad={target_w}:{target_h}:{x_off}:{y_off}:color={ffmpeg_color}")
    elif mode == "crop":
        # Scale to fill canvas, then crop
        filters.append(f"scale={scaled_w}:{scaled_h}:flags=lanczos")
        filters.append(f"crop={target_w}:{target_h}:{x_off}:{y_off}")
    else:  # mode == "scale"
        filters.append(f"scale={scaled_w}:{scaled_h}:flags=lanczos")
        
    # Cap frame rate at 60 fps to match Instagram guidelines
    if frame_rate > 60.0:
        filters.append("fps=fps=60")
        
    filter_str = ",".join(filters)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 4. Construct FFmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-progress", "-",  # output key-value progress logs to stdout
        "-nostats",
        "-i", input_path,
        "-c:v", "libx264",
        "-profile:v", "high",
        "-preset", "medium",
        "-b:v", f"{bitrate_kbps}k",
        "-maxrate", f"{int(bitrate_kbps * 1.5)}k",
        "-bufsize", f"{int(bitrate_kbps * 2)}k",
        "-pix_fmt", "yuv420p",
        # Color metadata to enforce sRGB compatibility (Rec. 709)
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
    ]
    
    if filter_str:
        cmd.extend(["-vf", filter_str])
        
    if has_audio:
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "256k",
            "-ar", "48000"
        ])
    else:
        cmd.extend(["-an"])  # strip audio if original has none
        
    cmd.append(output_path)
    
    # 5. Run FFmpeg and capture progress
    # We pipe stdout to parse progress. Stderr is redirected to a temporary file
    # to avoid blocking the pipe buffer and causing deadlocks.
    import tempfile
    
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr_file:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            text=True,
            encoding="utf-8"
        )
        
        # Show progress bar with Rich
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(status_prefix, total=100)
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                
                line = line.strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    if key == "out_time_us":
                        try:
                            time_us = int(val)
                            time_sec = time_us / 1_000_000.0
                            if duration > 0:
                                pct = min(100.0, (time_sec / duration) * 100.0)
                                progress.update(task, completed=pct)
                        except ValueError:
                            pass
                    elif key == "progress" and val == "end":
                        progress.update(task, completed=100)
                        
            # Clean up stream
            stdout, _ = process.communicate()
            
            if process.returncode != 0:
                stderr_file.seek(0)
                stderr = stderr_file.read()
                raise RuntimeError(
                    f"FFmpeg command failed with exit code {process.returncode}.\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"FFmpeg error log:\n{stderr}"
                )
