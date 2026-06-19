import os
import sys
import subprocess
import shutil
from PIL import Image

# Import local processor modules by adding the workspace path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from insta_optimizer.video_processor import probe_video
from insta_optimizer.utils import has_ffmpeg

INPUT_DIR = os.path.abspath("test_media")
OUTPUT_DIR = os.path.abspath("test_media_optimized")

def setup_dummy_media():
    """Create input folder and populate it with dummy photos and videos."""
    if os.path.exists(INPUT_DIR):
        shutil.rmtree(INPUT_DIR)
    os.makedirs(INPUT_DIR, exist_ok=True)
    
    print("[*] Creating dummy test assets...")
    
    # 1. Create a landscape JPEG (1920x1080)
    img_land = Image.new("RGB", (1920, 1080), color=(220, 50, 50))  # redish
    img_land_path = os.path.join(INPUT_DIR, "landscape_photo.jpg")
    img_land.save(img_land_path, "JPEG")
    print(f"  - Created image: {img_land_path} (1920x1080)")
    
    # 2. Create a portrait PNG (1000x2000)
    img_port = Image.new("RGB", (1000, 2000), color=(50, 200, 50))  # greenish
    img_port_path = os.path.join(INPUT_DIR, "portrait_photo.png")
    img_port.save(img_port_path, "PNG")
    print(f"  - Created image: {img_port_path} (1000x2000)")
    
    if not has_ffmpeg():
        print("[!] FFmpeg not found, skipping dummy video generation.")
        return
        
    # 3. Create a landscape video (1920x1080, 2s, Rec 709) using FFmpeg color filter
    vid_land_path = os.path.join(INPUT_DIR, "landscape_video.mp4")
    cmd_land = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:d=2:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        vid_land_path
    ]
    subprocess.run(cmd_land, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"  - Created video: {vid_land_path} (1920x1080, 30fps, blue, stereo audio)")
    
    # 4. Create a tall video (1080x1920, 2s) with no audio
    vid_port_path = os.path.join(INPUT_DIR, "portrait_video.mov")
    cmd_port = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=yellow:s=1080x1920:d=2:r=60",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an", # no audio
        vid_port_path
    ]
    subprocess.run(cmd_port, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"  - Created video: {vid_port_path} (1080x1920, 60fps, yellow, no audio)")


def verify_image(path: str, expected_size: tuple):
    """Verify image exists, is JPEG, and matches the expected size."""
    assert os.path.exists(path), f"Image does not exist: {path}"
    with Image.open(path) as img:
        assert img.format == "JPEG", f"Expected JPEG, got {img.format} for {path}"
        assert img.size == expected_size, f"Expected size {expected_size}, got {img.size} for {path}"


def verify_video(path: str, expected_size: tuple, expected_audio: bool):
    """Verify video exists, is MP4, and matches size and audio stream presence."""
    assert os.path.exists(path), f"Video does not exist: {path}"
    assert path.lower().endswith(".mp4"), f"Expected .mp4 extension for {path}"
    
    info = probe_video(path)
    assert (info["width"], info["height"]) == expected_size, \
        f"Expected video size {expected_size}, got {(info['width'], info['height'])}"
    assert info["has_audio"] == expected_audio, \
        f"Expected audio presence to be {expected_audio}, got {info['has_audio']}"


def run_tests():
    """Execute a series of tests against the optimizer CLI and assert results."""
    # Ensure fresh test directory
    setup_dummy_media()
    
    tests_failed = 0
    tests_run = 0
    
    # Setup clean output directory
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
        
    def log_test(name: str, status: str, details: str = ""):
        nonlocal tests_failed, tests_run
        tests_run += 1
        indicator = "[PASS]" if status == "PASS" else "[FAIL]"
        color = "\033[92m" if status == "PASS" else "\033[91m"
        reset = "\033[0m"
        print(f"{color}{indicator} - {name}{reset} {details}")
        if status == "FAIL":
            tests_failed += 1

    # --- Test 1: Image Feed (4:5) Fit (No mat padding) ---
    try:
        # Run CLI
        cmd = [
            sys.executable, "-m", "insta_optimizer",
            INPUT_DIR, "-o", OUTPUT_DIR,
            "-a", "feed", "--mode", "fit",
        ]
        subprocess.run(cmd, check=True)
        
        # Verify landscape fits into 4:5 (1080x1350)
        verify_image(os.path.join(OUTPUT_DIR, "landscape_photo.jpg"), (1080, 1350))
        # Verify portrait fits into 4:5 (1080x1350)
        verify_image(os.path.join(OUTPUT_DIR, "portrait_photo.jpg"), (1080, 1350))
        log_test("Test 1: Image Feed (4:5) Fit Mode", "PASS")
    except Exception as e:
        log_test("Test 1: Image Feed (4:5) Fit Mode", "FAIL", str(e))
        
    # --- Test 2: Image Feed (4:5) Crop Mode ---
    try:
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        cmd = [
            sys.executable, "-m", "insta_optimizer",
            INPUT_DIR, "-o", OUTPUT_DIR,
            "-a", "feed", "--mode", "crop"
        ]
        subprocess.run(cmd, check=True)
        verify_image(os.path.join(OUTPUT_DIR, "landscape_photo.jpg"), (1080, 1350))
        verify_image(os.path.join(OUTPUT_DIR, "portrait_photo.jpg"), (1080, 1350))
        log_test("Test 2: Image Feed (4:5) Crop Mode", "PASS")
    except Exception as e:
        log_test("Test 2: Image Feed (4:5) Crop Mode", "FAIL", str(e))
        
    # --- Test 3: Image Reels (9:16) with 10% Margin White Mat ---
    try:
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        cmd = [
            sys.executable, "-m", "insta_optimizer",
            INPUT_DIR, "-o", OUTPUT_DIR,
            "-a", "reels", "-m", "--mat-padding", "0.10", "--mat-color", "white"
        ]
        subprocess.run(cmd, check=True)
        verify_image(os.path.join(OUTPUT_DIR, "landscape_photo.jpg"), (1080, 1920))
        verify_image(os.path.join(OUTPUT_DIR, "portrait_photo.jpg"), (1080, 1920))
        log_test("Test 3: Image Reels (9:16) with 10% White Mat", "PASS")
    except Exception as e:
        log_test("Test 3: Image Reels (9:16) with 10% White Mat", "FAIL", str(e))

    if not has_ffmpeg():
        print("[!] FFmpeg not found, skipping video processing tests.")
        print(f"\nCompleted: {tests_run} tests run. {tests_failed} failed.")
        sys.exit(tests_failed)
        
    # --- Test 4: Video Feed (4:5) Fit (No mat padding) ---
    try:
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        cmd = [
            sys.executable, "-m", "insta_optimizer",
            INPUT_DIR, "-o", OUTPUT_DIR,
            "-a", "feed", "--mode", "fit"
        ]
        subprocess.run(cmd, check=True)
        # Landscape video should be optimized and fit to 1080x1350, preserving audio
        verify_video(os.path.join(OUTPUT_DIR, "landscape_video.mp4"), (1080, 1350), expected_audio=True)
        # Portrait video should fit into 1080x1350, has no audio
        verify_video(os.path.join(OUTPUT_DIR, "portrait_video.mp4"), (1080, 1350), expected_audio=False)
        log_test("Test 4: Video Feed (4:5) Fit Mode", "PASS")
    except Exception as e:
        log_test("Test 4: Video Feed (4:5) Fit Mode", "FAIL", str(e))

    # --- Test 5: Video Reels (9:16) with 5% Black Mat ---
    try:
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        cmd = [
            sys.executable, "-m", "insta_optimizer",
            INPUT_DIR, "-o", OUTPUT_DIR,
            "-a", "reels", "-m", "--mat-color", "black", "--mat-padding", "0.05"
        ]
        subprocess.run(cmd, check=True)
        # Verify 9:16 dimensions (1080x1920)
        verify_video(os.path.join(OUTPUT_DIR, "landscape_video.mp4"), (1080, 1920), expected_audio=True)
        verify_video(os.path.join(OUTPUT_DIR, "portrait_video.mp4"), (1080, 1920), expected_audio=False)
        log_test("Test 5: Video Reels (9:16) with 5% Black Mat", "PASS")
    except Exception as e:
        log_test("Test 5: Video Reels (9:16) with 5% Black Mat", "FAIL", str(e))
        
    print(f"\n[Summary] {tests_run - tests_failed}/{tests_run} tests passed.")
    if tests_failed > 0:
        print("[!] Some tests failed.")
        sys.exit(1)
    else:
        print("[*] All tests passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
