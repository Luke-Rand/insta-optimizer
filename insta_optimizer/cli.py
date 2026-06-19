import os
import time
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from insta_optimizer import __version__
from insta_optimizer.utils import has_ffmpeg
from insta_optimizer.image_processor import optimize_image
from insta_optimizer.video_processor import optimize_video

# Supported extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}

# Aspect ratio mappings: (width, height)
ASPECT_RATIOS = {
    "feed": (1080, 1350),      # 4:5 vertical
    "reels": (1080, 1920),     # 9:16 vertical
    "square": (1080, 1080),    # 1:1 square
}

console = Console()

@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument(
    "input_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True)
)
@click.option(
    "-o", "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
    help="Output directory. Defaults to '<input_dir>_optimized'."
)
@click.option(
    "-a", "--aspect",
    type=click.Choice(["feed", "reels", "square"], case_sensitive=False),
    default="feed",
    show_default=True,
    help="Target Instagram aspect ratio / template."
)
@click.option(
    "-m", "--mat",
    is_flag=True,
    help="Enable white border (matting) to fit media inside the aspect ratio canvas without cropping."
)
@click.option(
    "--mat-color",
    default="white",
    show_default=True,
    help="Color of the mat/border (hex code like '#ffffff' or standard name like 'white', 'black', 'gray')."
)
@click.option(
    "--mat-padding",
    type=click.FloatRange(0.0, 0.5),
    default=0.05,
    show_default=True,
    help="Padding percentage around the media when matting is enabled (e.g., 0.05 is 5% margin)."
)
@click.option(
    "--mode",
    type=click.Choice(["fit", "crop", "scale"], case_sensitive=False),
    default="fit",
    show_default=True,
    help="Fallback resizing mode. 'fit' pads borders, 'crop' center-crops to target size, 'scale' scales primary axis without borders."
)
@click.option(
    "-q", "--quality",
    type=click.IntRange(1, 100),
    default=85,
    show_default=True,
    help="JPEG compression quality (80-85 is the recommended sweet spot)."
)
@click.option(
    "-b", "--bitrate",
    type=click.IntRange(1000, 30000),
    default=8000,
    show_default=True,
    help="Target video bitrate in kbps (5000-10000 kbps is recommended)."
)
@click.option(
    "-r", "--recursive",
    is_flag=True,
    help="Search input directory recursively for images and videos."
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Scan files and display what would be processed without executing conversion."
)
@click.version_option(version=__version__, prog_name="insta-optimizer")
def cli(
    input_dir: str,
    output_dir: str,
    aspect: str,
    mat: bool,
    mat_color: str,
    mat_padding: float,
    mode: str,
    quality: int,
    bitrate: int,
    recursive: bool,
    dry_run: bool
) -> None:
    """
    Optimize photos and videos in INPUT_DIR for posting to Instagram.
    
    This CLI tool resizes, adjusts color spaces to sRGB, compresses, and scales
    your media to fit Instagram's optimal feed (4:5) or reels (9:16) templates.
    """
    start_time = time.time()
    
    # 1. Title Banner
    console.print(Panel(
        f"[bold purple]Instagram Optimizer CLI v{__version__}[/]\n"
        "[dim]Sleek, cross-platform media processing for Instagram grid and reels[/]",
        expand=False
    ))
    
    # 2. Normalize and resolve paths
    input_path = os.path.abspath(input_dir)
    if not output_dir:
        output_path = f"{input_path}_optimized"
    else:
        output_path = os.path.abspath(output_dir)
        
    target_w, target_h = ASPECT_RATIOS[aspect.lower()]
    
    # Enforce 'fit' mode if matting is requested
    final_mode = "fit" if mat else mode.lower()
    padding_pct = mat_padding if mat else 0.0
    
    # Log configuration parameters
    console.print("[bold yellow]Configuration Summary:[/]")
    console.print(f"  - Input Directory:  [cyan]{input_path}[/]")
    console.print(f"  - Output Directory: [cyan]{output_path}[/]")
    console.print(f"  - Target Template:  [cyan]{aspect.upper()} ({target_w}x{target_h})[/]")
    console.print(f"  - Layout Mode:      [cyan]{final_mode.upper()}[/]" + (f" (Matting enabled, Padding: {padding_pct*100:.1f}%, Color: {mat_color})" if mat else ""))
    console.print(f"  - Photo Quality:    [cyan]{quality}% (JPEG)[/]")
    console.print(f"  - Video Bitrate:    [cyan]{bitrate} kbps (H.264 / AAC)[/]")
    if dry_run:
        console.print("  - Execution Mode:   [bold red]DRY RUN[/]")
    console.print("")

    # 3. Check for FFmpeg if we might encounter video files
    ffmpeg_available = has_ffmpeg()
    
    # 4. Discover files
    files_to_process = []
    
    # Helper to scan directories
    def scan_dir(dir_path: str) -> None:
        for entry in os.scandir(dir_path):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                # Skip files inside the output directory if it overlaps
                if os.path.commonpath([entry.path, output_path]) == output_path:
                    continue
                if ext in IMAGE_EXTENSIONS:
                    files_to_process.append((entry.path, "image"))
                elif ext in VIDEO_EXTENSIONS:
                    files_to_process.append((entry.path, "video"))
            elif entry.is_dir() and recursive:
                # Skip output directory recursively
                if os.path.abspath(entry.path) == output_path:
                    continue
                scan_dir(entry.path)

    scan_dir(input_path)
    
    total_files = len(files_to_process)
    if total_files == 0:
        console.print("[bold yellow]No supported photos or videos found in the input directory.[/]")
        return
        
    console.print(f"Found [bold green]{total_files}[/] files to process.\n")
    
    # Warn user about missing FFmpeg if video files are present
    has_videos = any(ftype == "video" for _, ftype in files_to_process)
    if has_videos and not ffmpeg_available:
        if dry_run:
            console.print("[bold red]WARNING: FFmpeg/FFprobe are not installed on the system PATH. Video files will FAIL during run mode.[/]\n")
        else:
            console.print("[bold red]ERROR: Video files found, but FFmpeg and FFprobe are not available in your PATH.[/]")
            console.print("Please install FFmpeg or remove videos from the input folder to proceed. Exiting.\n")
            return

    # Track results
    success_count = 0
    fail_count = 0
    skipped_count = 0
    
    results = []

    # 5. Process files
    for idx, (fpath, ftype) in enumerate(files_to_process, start=1):
        rel_path = os.path.relpath(fpath, input_path)
        out_fpath = os.path.join(output_path, rel_path)
        
        # Enforce JPEG output for photos
        if ftype == "image":
            out_fpath = os.path.splitext(out_fpath)[0] + ".jpg"
        elif ftype == "video":
            out_fpath = os.path.splitext(out_fpath)[0] + ".mp4"
            
        console.print(f"[bold]({idx}/{total_files}) Processing [cyan]{rel_path}[/] ({ftype.upper()})[/]")
        
        if dry_run:
            console.print(f"  [dim]Would write to {out_fpath}[/]")
            success_count += 1
            results.append((rel_path, ftype, "SUCCESS (Dry Run)", ""))
            continue
            
        try:
            if ftype == "image":
                optimize_image(
                    input_path=fpath,
                    output_path=out_fpath,
                    target_w=target_w,
                    target_h=target_h,
                    mode=final_mode,
                    mat_color_str=mat_color,
                    padding_pct=padding_pct,
                    quality=quality
                )
            elif ftype == "video":
                optimize_video(
                    input_path=fpath,
                    output_path=out_fpath,
                    target_w=target_w,
                    target_h=target_h,
                    mode=final_mode,
                    mat_color_str=mat_color,
                    padding_pct=padding_pct,
                    bitrate_kbps=bitrate,
                    status_prefix="  Encoding"
                )
            
            console.print("  [bold green][OK] Success![/]")
            success_count += 1
            results.append((rel_path, ftype, "SUCCESS", ""))
            
        except Exception as e:
            console.print(f"  [bold red][ERROR] Failed:[/] {e}")
            fail_count += 1
            results.append((rel_path, ftype, "FAILED", str(e)))
            
        console.print("")

    # 6. Print Summary Table
    duration = time.time() - start_time
    
    summary_table = Table(title="Processing Summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("File Name", style="dim")
    summary_table.add_column("Type")
    summary_table.add_column("Status")
    summary_table.add_column("Details")
    
    for r_path, r_type, r_status, r_detail in results:
        status_style = "green" if "SUCCESS" in r_status else "red"
        summary_table.add_row(
            r_path,
            r_type.upper(),
            f"[{status_style}]{r_status}[/]",
            r_detail if r_detail else "Optimized successfully"
        )
        
    console.print(summary_table)
    console.print("")
    
    console.print(Panel(
        f"Processing completed in [green]{duration:.2f}[/] seconds.\n"
        f"Successfully processed: [bold green]{success_count}[/] / Failed: [bold red]{fail_count}[/]",
        title="Execution Complete",
        expand=False
    ))

if __name__ == "__main__":
    cli()
