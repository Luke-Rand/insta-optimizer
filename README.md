# Instagram Photo & Video Optimizer CLI

A cross-platform Python command-line utility to automatically optimize photos and videos for posting to Instagram feed (4:5 / 1:1) and Reels/Stories (9:16). 

It enforces optimal color space (sRGB), resolutions, video/audio codecs, and target bitrates to prevent Instagram's servers from aggressively compressing or distorting your files. It also offers a custom "matting" border option to fit any widescreen or custom aspect ratio image/video into a standard vertical canvas.

---

## Technical Specifications Target

* **Photos**:
  * Output Format: JPEG
  * Color Profile: sRGB
  * Quality: 85% (Optimal compression threshold)
* **Videos**:
  * Container: MP4
  * Video Codec: H.264 (High Profile, yuv420p pixel format)
  * Audio Codec: AAC-LC (stereo, 48 kHz, 256 kbps)
  * Bitrate: 8,000 kbps (capping quality standard)
  * Frame rate: Capped at 60 fps
* **Aspect Ratios**:
  * **feed**: `4:5` vertical ratio (1080 x 1350 px)
  * **reels**: `9:16` vertical ratio (1080 x 1920 px)
  * **square**: `1:1` square ratio (1080 x 1080 px)

---

## Installation

### Prerequisites
1. **Python 3.8+**
2. **FFmpeg** and **FFprobe** (must be available in your system `PATH` for video processing).

### Setup
1. Clone or download this repository.
2. Create and activate a Python virtual environment:
   * **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   * **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. Install the package locally:
   ```bash
   pip install .
   ```

---

## Usage

Once installed, you can run the command `insta-optimizer` directly, or execute it as a module using `python -m insta_optimizer`.

Alternatively, you can run the application directly using the root entrypoint script `main.py`:
```bash
python main.py [options] INPUT_DIR
```

### Basic Usage
Optimize a folder of images/videos to the default Instagram Feed vertical layout (4:5):
```bash
insta-optimizer /path/to/source_media
# OR
python main.py /path/to/source_media
```
This scans `/path/to/source_media` and outputs optimized files to `/path/to/source_media_optimized`.

### Main CLI Options

* `INPUT_DIR` (required): The path to the folder containing your source images and/or videos.
* `-o`, `--output-dir PATH`: Directory where optimized files will be written. Defaults to `<INPUT_DIR>_optimized`.
* `-a`, `--aspect [feed|reels|square]`: Target Instagram dimension template. Default: `feed` (1080x1350).
* `-m`, `--mat`: Enable a border (mat) to fit the image or video within the target aspect ratio canvas without cropping.
* `--mat-color COLOR`: Canvas background color. Default: `white`. Supports hex codes (e.g. `#eaeaea`) and standard color names (white, black, gray, red, blue, etc.).
* `--mat-padding FLOAT`: Padding margin percentage around the media. Default: `0.05` (5% padding).
* `--mode [fit|crop|scale]`: Resizing behavior when matting is disabled.
  * `fit`: Fits image within target bounds, padding edges if necessary (0% margin).
  * `crop`: Crops the center of the image to fill the target aspect ratio.
  * `scale`: Scales the image size without cropping or border padding. (Warning: may exceed Instagram's native aspect ratio bounds).
* `-q`, `--quality INTEGER`: JPEG compression quality (1-100). Default: `85`.
* `-b`, `--bitrate INTEGER`: Video bitrate in kbps. Default: `8000`.
* `-r`, `--recursive`: Recursively traverse directories inside the input folder.
* `--dry-run`: Preview which files would be processed without performing operations.
* `--help`: Show all options.

### Examples

**Optimize for Reels (9:16) with a 5% white matting frame**:
```bash
insta-optimizer /path/to/media -a reels -m
```

**Crop media to square (1:1) grid posts**:
```bash
insta-optimizer /path/to/media -a square --mode crop
```

**Optimize with a customized dark gray mat background and 10% padding border**:
```bash
insta-optimizer /path/to/media -m --mat-color "#333333" --mat-padding 0.10
```
