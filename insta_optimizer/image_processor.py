import io
import os
from PIL import Image, ImageOps, ImageCms
from insta_optimizer.utils import calculate_dimensions, parse_color

def convert_to_srgb(img: Image.Image) -> Image.Image:
    """
    Standardize the image's orientation and convert its color profile to sRGB.
    """
    # 1. Correct orientation using EXIF tag
    img = ImageOps.exif_transpose(img)
    
    # 2. Convert color space to sRGB if ICC profile exists
    icc = img.info.get("icc_profile")
    if icc:
        try:
            f_icc = io.BytesIO(icc)
            src_profile = ImageCms.ImageCmsProfile(f_icc)
            srgb_profile = ImageCms.createProfile("sRGB")
            # Apply color profile transform
            img = ImageCms.profileToProfile(img, src_profile, srgb_profile, outputMode="RGB")
            return img
        except Exception:
            # Fallback if profile conversion fails
            pass
            
    # Standard color mode conversion
    if img.mode != "RGB":
        return img.convert("RGB")
    return img

def optimize_image(
    input_path: str,
    output_path: str,
    target_w: int,
    target_h: int,
    mode: str = "fit",
    mat_color_str: str = "white",
    padding_pct: float = 0.0,
    quality: int = 85
) -> None:
    """
    Optimize an image for Instagram with options to fit (with or without matting border),
    crop (fill), or scale directly.
    
    Parameters:
      input_path: Path to the source photo.
      output_path: Path to write the optimized photo.
      target_w, target_h: Target dimensions (e.g. 1080, 1350).
      mode: 'fit' (pads empty areas), 'crop' (center crops), 'scale' (no padding/cropping, scales primary axis).
      mat_color_str: Color name or hex code for the mat background.
      padding_pct: Percentage of padding to apply when in 'fit' mode.
      quality: JPEG quality (1-100).
    """
    # Open image
    with Image.open(input_path) as raw_img:
        # Standardize colors and orientation
        img = convert_to_srgb(raw_img)
        input_w, input_h = img.size
        
        # Calculate target size and offset
        scaled_w, scaled_h, x_off, y_off = calculate_dimensions(
            input_w, input_h, target_w, target_h,
            mode=mode, padding_pct=padding_pct, force_even=False
        )
        
        # Select appropriate Resampling filter (LANCZOS is highest quality for downscaling)
        resample_filter = getattr(Image, "LANCZOS", Image.Resampling.LANCZOS)
        
        if mode == "fit":
            # Scale active photo
            scaled_img = img.resize((scaled_w, scaled_h), resample_filter)
            
            # Parse color for background canvas
            rgb_color, _ = parse_color(mat_color_str)
            
            # Create target canvas and paste scaled image centered
            canvas = Image.new("RGB", (target_w, target_h), rgb_color)
            canvas.paste(scaled_img, (x_off, y_off))
            final_img = canvas
            
        elif mode == "crop":
            # Scale photo to fill canvas (some parts will overshoot)
            scaled_img = img.resize((scaled_w, scaled_h), resample_filter)
            
            # Crop the target window out of the center
            crop_box = (x_off, y_off, x_off + target_w, y_off + target_h)
            final_img = scaled_img.crop(crop_box)
            
        else:  # mode == "scale"
            # Just scale the photo
            final_img = img.resize((scaled_w, scaled_h), resample_filter)
            
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save as JPEG with sRGB and optimized compression settings
        final_img.save(
            output_path,
            "JPEG",
            quality=quality,
            optimize=True,
            icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        )
