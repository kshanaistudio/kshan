import os
import hashlib
from PIL import Image, ImageOps
import cv2
import numpy as np
from pathlib import Path
from django.conf import settings

def compute_sha256(file_path: str, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file for duplicate protection."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()

import exifread
from datetime import datetime

def get_image_metadata(file_path: str) -> dict:
    """Extract width, height, file size, and detailed EXIF metadata handling EXIF rotation."""
    file_size = os.path.getsize(file_path)
    with Image.open(file_path) as img:
        img = ImageOps.exif_transpose(img) or img
        width, height = img.size
        
    exif_data = {
        'camera': '', 'lens': '', 'focal_length': '', 
        'aperture': '', 'exposure_time': '', 'iso': '', 'date_taken': None
    }
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            
            if 'Image Model' in tags:
                exif_data['camera'] = str(tags['Image Model'])
            if 'EXIF LensModel' in tags:
                exif_data['lens'] = str(tags['EXIF LensModel'])
            
            # Format focal length
            focal_length = tags.get('EXIF FocalLength')
            if focal_length and hasattr(focal_length, 'values') and len(focal_length.values) > 0:
                try:
                    num, den = focal_length.values[0].num, focal_length.values[0].den
                    exif_data['focal_length'] = f"{int(num/den)}mm" if den else ""
                except:
                    exif_data['focal_length'] = str(focal_length)
            
            # Format aperture
            aperture = tags.get('EXIF FNumber')
            if aperture and hasattr(aperture, 'values') and len(aperture.values) > 0:
                try:
                    num, den = aperture.values[0].num, aperture.values[0].den
                    exif_data['aperture'] = f"f/{num/den:.1f}" if den else ""
                except:
                    exif_data['aperture'] = str(aperture)
                    
            # Format exposure
            exposure = tags.get('EXIF ExposureTime')
            if exposure and hasattr(exposure, 'values') and len(exposure.values) > 0:
                try:
                    num, den = exposure.values[0].num, exposure.values[0].den
                    exif_data['exposure_time'] = f"{num}/{den} sec"
                except:
                    exif_data['exposure_time'] = str(exposure)
                    
            if 'EXIF ISOSpeedRatings' in tags:
                exif_data['iso'] = str(tags['EXIF ISOSpeedRatings'])
            
            # Parse date
            date_str = str(tags.get('EXIF DateTimeOriginal', ''))
            if date_str:
                try:
                    exif_data['date_taken'] = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S').isoformat()
                except:
                    pass
    except Exception as e:
        import logging
        logging.getLogger("kshan.image_service").warning(f"Failed to read EXIF: {e}")

    return {
        "width": width,
        "height": height,
        "file_size": file_size,
        "exif": exif_data
    }

def apply_watermark(input_path: str, watermark_text: str = None, logo_path: str = None) -> None:
    """
    Applies:
    1. Photographer custom logo / typography watermark at bottom-center (if provided).
    2. Default KSHAN software site logo watermark at bottom-right of every photo.
    """
    try:
        from PIL import ImageDraw, ImageFont
        from ..models import GlobalSiteSettings
        from django.conf import settings
        
        site_settings = GlobalSiteSettings.get_settings()
        
        with Image.open(input_path) as img:
            img = ImageOps.exif_transpose(img) or img
            img = img.convert("RGBA")
            w, h = img.size

            # Create transparent overlay
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))

            # ── 1. Photographer Branding (Bottom-Center) ──
            if logo_path and Path(logo_path).exists():
                try:
                    with Image.open(logo_path) as logo_img:
                        logo_img = logo_img.convert("RGBA")
                        target_w = max(120, int(w * 0.18))
                        aspect = logo_img.height / float(logo_img.width)
                        target_h = int(target_w * aspect)
                        logo_resized = logo_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

                        pos_x = (w - target_w) // 2
                        pos_y = h - int(h * 0.04) - target_h
                        overlay.paste(logo_resized, (pos_x, pos_y), mask=logo_resized.split()[-1])
                except Exception:
                    pass
            elif watermark_text:
                draw = ImageDraw.Draw(overlay)
                font_size = max(18, int(w * 0.024))
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except Exception:
                    try:
                        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
                    except Exception:
                        font = ImageFont.load_default()

                text = f"◈  {watermark_text.upper()}  ◈"
                bbox = draw.textbbox((0, 0), text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]

                padding_x = int(font_size * 0.85)
                padding_y = int(font_size * 0.42)
                margin_bottom = int(h * 0.04)

                pill_w = text_w + (padding_x * 2)
                pill_h = text_h + (padding_y * 2)
                pill_x1 = (w - pill_w) // 2
                pill_y1 = h - margin_bottom - pill_h
                pill_x2 = pill_x1 + pill_w
                pill_y2 = pill_y1 + pill_h

                corner_radius = max(6, int(pill_h * 0.28))
                draw.rounded_rectangle(
                    [pill_x1, pill_y1, pill_x2, pill_y2],
                    radius=corner_radius,
                    fill=(11, 11, 11, 140),
                    outline=(218, 165, 32, 100),
                    width=1
                )

                text_x = pill_x1 + padding_x
                text_y = pill_y1 + padding_y - 1
                draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 230))

            # ── 2. Default Site Logo / Watermark (Bottom-Right) ──
            if site_settings.site_watermark_enabled:
                site_logo_applied = False
                
                # Check custom uploaded site logo or fallback to default site gold logo
                site_logo_file = None
                if site_settings.site_watermark_logo and hasattr(site_settings.site_watermark_logo, 'path') and Path(site_settings.site_watermark_logo.path).exists():
                    site_logo_file = str(site_settings.site_watermark_logo.path)
                else:
                    default_site_logo = settings.BASE_DIR / "static" / "images" / "kshan_kalam_logo_gold.png"
                    if default_site_logo.exists():
                        site_logo_file = str(default_site_logo)

                if site_logo_file and Path(site_logo_file).exists():
                    try:
                        with Image.open(site_logo_file) as s_logo:
                            s_logo = s_logo.convert("RGBA")
                            # Bottom right logo ~ 10% - 12% width
                            s_target_w = max(70, int(w * 0.11))
                            s_aspect = s_logo.height / float(s_logo.width)
                            s_target_h = int(s_target_w * s_aspect)
                            s_resized = s_logo.resize((s_target_w, s_target_h), Image.Resampling.LANCZOS)
                            
                            # Adjust opacity
                            alpha = s_resized.split()[-1]
                            alpha = alpha.point(lambda p: int(p * (site_settings.site_watermark_opacity or 0.85)))
                            s_resized.putalpha(alpha)

                            s_pos_x = w - s_target_w - int(w * 0.025)
                            s_pos_y = h - s_target_h - int(h * 0.025)
                            overlay.paste(s_resized, (s_pos_x, s_pos_y), mask=alpha)
                            site_logo_applied = True
                    except Exception:
                        pass

                if not site_logo_applied:
                    # Typography fallback badge at bottom-right
                    draw_site = ImageDraw.Draw(overlay)
                    s_font_size = max(13, int(w * 0.016))
                    try:
                        s_font = ImageFont.truetype("arial.ttf", s_font_size)
                    except Exception:
                        s_font = ImageFont.load_default()

                    brand_label = f"✨ {site_settings.site_brand_name.upper()}"
                    s_bbox = draw_site.textbbox((0, 0), brand_label, font=s_font)
                    s_text_w = s_bbox[2] - s_bbox[0]
                    s_text_h = s_bbox[3] - s_bbox[1]

                    s_pad_x = int(s_font_size * 0.6)
                    s_pad_y = int(s_font_size * 0.3)
                    s_pill_w = s_text_w + (s_pad_x * 2)
                    s_pill_h = s_text_h + (s_pad_y * 2)

                    s_x1 = w - s_pill_w - int(w * 0.025)
                    s_y1 = h - s_pill_h - int(h * 0.025)
                    s_x2 = s_x1 + s_pill_w
                    s_y2 = s_y1 + s_pill_h

                    draw_site.rounded_rectangle(
                        [s_x1, s_y1, s_x2, s_y2],
                        radius=5,
                        fill=(15, 14, 20, 180),
                        outline=(199, 168, 107, 180),
                        width=1
                    )
                    draw_site.text((s_x1 + s_pad_x, s_y1 + s_pad_y), brand_label, font=s_font, fill=(245, 230, 204, 240))

            final_img = Image.alpha_composite(img, overlay)
            final_img = final_img.convert("RGB")
            final_img.save(input_path, "JPEG", quality=92, optimize=True)

    except Exception as e:
        import logging
        logging.getLogger("kshan.image_service").warning(f"Failed to apply watermark: {e}")

def create_thumbnail(input_path: str, output_path: str, max_size: int = settings.THUMBNAIL_MAX_SIZE) -> str:
    """Generate an optimized thumbnail preserving aspect ratio and EXIF orientation."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with Image.open(input_path) as img:
        img = ImageOps.exif_transpose(img) or img
        
        if img.mode in ("RGBA", "LA", "P"):
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = rgb_img
        elif img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        img.save(output_path, "JPEG", quality=85, optimize=True)

    return output_path

def load_cv2_image_safe(image_path_or_bytes) -> np.ndarray:
    """Loads an image safely into OpenCV BGR format handling Unicode Windows paths."""
    if isinstance(image_path_or_bytes, (str, Path)):
        file_bytes = np.fromfile(str(image_path_or_bytes), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Unable to read image at path: {image_path_or_bytes}")
        return img
    elif isinstance(image_path_or_bytes, bytes):
        file_bytes = np.frombuffer(image_path_or_bytes, dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Unable to decode image bytes")
        return img
    elif isinstance(image_path_or_bytes, np.ndarray):
        return image_path_or_bytes
    else:
        raise TypeError("Invalid image input type for OpenCV loader")
