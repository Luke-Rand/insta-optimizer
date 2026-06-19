import shutil
import re
from typing import Tuple, Dict

# Standard CSS/FFmpeg colors mapping to RGB
COLOR_MAP: Dict[str, Tuple[int, int, int]] = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "silver": (192, 192, 192),
    "maroon": (128, 0, 0),
    "olive": (128, 128, 0),
    "purple": (128, 0, 128),
    "teal": (0, 128, 128),
    "navy": (0, 0, 128),
}

def has_ffmpeg() -> bool:
    """Check if ffmpeg and ffprobe are available in the PATH."""
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

def parse_color(color_str: str) -> Tuple[Tuple[int, int, int], str]:
    """
    Parse a color string (e.g. 'white', '#FFFFFF', '0xFFFFFF')
    and return a tuple of ((R, G, B), ffmpeg_color_string).
    """
    c_clean = color_str.strip().lower()
    
    # 1. Check named color map
    if c_clean in COLOR_MAP:
        rgb = COLOR_MAP[c_clean]
        return rgb, c_clean
        
    # 2. Check Hex colors (e.g. #ffffff, ffffff, #fff, fff)
    hex_match = re.match(r"^#?([a-f0-9]{3,8})$", c_clean)
    if hex_match:
        hex_val = hex_match.group(1)
        if len(hex_val) == 3:
            # e.g. fff -> ffffff
            hex_val = "".join(ch * 2 for ch in hex_val)
        
        if len(hex_val) == 6:
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            return (r, g, b), f"0x{hex_val.upper()}"
        elif len(hex_val) == 8:
            # includes alpha, ignore alpha for RGB but keep for ffmpeg
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            return (r, g, b), f"0x{hex_val.upper()}"

    # Fallback to white if invalid
    return (255, 255, 255), "white"

def make_even(val: int) -> int:
    """Round value to the nearest even integer. H.264 codec requires even dimensions."""
    val = int(round(val))
    return val if val % 2 == 0 else val + 1

def calculate_dimensions(
    input_w: int,
    input_h: int,
    target_w: int,
    target_h: int,
    mode: str = "fit",
    padding_pct: float = 0.0,
    force_even: bool = True
) -> Tuple[int, int, int, int]:
    """
    Calculate the dimensions and offsets for centering/cropping an image or video.
    
    Parameters:
      input_w, input_h: Input dimensions
      target_w, target_h: Target canvas dimensions (e.g. 1080, 1350)
      mode: 'fit' (pad/mat), 'crop' (fill), or 'scale' (no borders/crop, just scale largest)
      padding_pct: Margin percentage to apply if mode is 'fit'.
      force_even: If True, rounds dimensions to even numbers.
      
    Returns:
      (scaled_w, scaled_h, x_offset, y_offset)
    """
    input_aspect = input_w / input_h
    target_aspect = target_w / target_h
    
    if mode == "fit":
        # Calculate active canvas size after padding
        active_w = target_w * (1.0 - 2.0 * padding_pct)
        active_h = target_h * (1.0 - 2.0 * padding_pct)
        active_aspect = active_w / active_h
        
        if input_aspect > active_aspect:
            # Input is wider: scale to fit active width
            scaled_w = active_w
            scaled_h = active_w / input_aspect
        else:
            # Input is taller: scale to fit active height
            scaled_h = active_h
            scaled_w = active_h * input_aspect
            
        if force_even:
            scaled_w = make_even(scaled_w)
            scaled_h = make_even(scaled_h)
        else:
            scaled_w = int(round(scaled_w))
            scaled_h = int(round(scaled_h))
            
        # Center the scaled image/video in the target canvas
        x_offset = int(round((target_w - scaled_w) / 2.0))
        y_offset = int(round((target_h - scaled_h) / 2.0))
        
        # Ensure coordinates are non-negative
        x_offset = max(0, x_offset)
        y_offset = max(0, y_offset)
        
        if force_even:
            x_offset = make_even(x_offset)
            y_offset = make_even(y_offset)
            
        return scaled_w, scaled_h, x_offset, y_offset
        
    elif mode == "crop":
        # Calculate scaled dimensions to fill the target canvas completely (some cropping will occur)
        if input_aspect > target_aspect:
            # Input is wider: scale height to match target height, crop sides
            scaled_h = target_h
            scaled_w = target_h * input_aspect
        else:
            # Input is taller: scale width to match target width, crop top/bottom
            scaled_w = target_w
            scaled_h = target_w / input_aspect
            
        if force_even:
            scaled_w = make_even(scaled_w)
            scaled_h = make_even(scaled_h)
        else:
            scaled_w = int(round(scaled_w))
            scaled_h = int(round(scaled_h))
            
        # Center crop offset (relative to the scaled image, so offsets are negative or we do crop box)
        # We'll calculate crop box offsets relative to scaled dimensions:
        x_offset = int(round((scaled_w - target_w) / 2.0))
        y_offset = int(round((scaled_h - target_h) / 2.0))
        x_offset = max(0, x_offset)
        y_offset = max(0, y_offset)
        
        if force_even:
            x_offset = make_even(x_offset)
            y_offset = make_even(y_offset)
            
        return scaled_w, scaled_h, x_offset, y_offset

    else:  # 'scale' mode
        # Simply scale the media so that it fits within the target canvas, but don't add borders or crop.
        # Just return the new scaled dimensions and zero offsets.
        if input_aspect > target_aspect:
            scaled_w = target_w
            scaled_h = target_w / input_aspect
        else:
            scaled_h = target_h
            scaled_w = target_h * input_aspect
            
        if force_even:
            scaled_w = make_even(scaled_w)
            scaled_h = make_even(scaled_h)
        else:
            scaled_w = int(round(scaled_w))
            scaled_h = int(round(scaled_h))
            
        return scaled_w, scaled_h, 0, 0
