"""Conservative image preprocessing and orientation recovery for the OCR pipeline.

Avoids destructive binarization/thresholding to protect faint text, mobile screenshots,
and colored stamps while handling EXIF metadata, upscale, contrast, and 90/180/270 degree rotation.
"""
from typing import Tuple, List, Optional
from statistics import mean
import numpy as np
from PIL import Image, ImageOps
from rapidocr import RapidOCR


def preprocess_image(image: Image.Image) -> Image.Image:
    """Applies conservative, non-destructive preprocessing.
    
    1. EXIF orientation correction.
    2. Conversion to standard RGB format.
    3. Mild upscale if image resolution is too low for OCR text recognition.
    4. Mild contrast normalization if dynamic range is compressed.
    """
    # 1. EXIF orientation
    processed = ImageOps.exif_transpose(image)
    if processed is None:
        processed = image

    # 2. Convert to RGB
    if processed.mode not in ("RGB", "L"):
        processed = processed.convert("RGB")

    # 3. Mild upscale for very small images/receipts (e.g. width < 600px)
    w, h = processed.size
    min_dim = min(w, h)
    if min_dim < 600:
        scale_factor = 2.0
        new_size = (int(w * scale_factor), int(h * scale_factor))
        processed = processed.resize(new_size, Image.Resampling.BICUBIC)

    # 4. Mild contrast normalization if image is washed out
    if processed.mode == "RGB":
        stat = ImageOps.grayscale(processed)
    else:
        stat = processed
    extrema = stat.getextrema()
    if extrema and (extrema[1] - extrema[0]) < 60:
        processed = ImageOps.autocontrast(processed, cutoff=1)

    return processed


def run_ocr_with_orientation(
    ocr: RapidOCR,
    image: Image.Image,
    try_rotations_on_failure: bool = True,
) -> Tuple[List[str], List[float], int, any]:
    """Executes RapidOCR with orientation handling.
    
    First runs OCR with use_cls=True on the preprocessed image.
    If 0 text or very low confidence (< 0.40) is returned and try_rotations_on_failure is enabled,
    evaluates 90°, 180°, and 270° rotations and selects the best candidate.
    
    Returns:
        (txts, scores, detected_angle, raw_output)
    """
    preprocessed = preprocess_image(image)
    img_np = np.array(preprocessed)

    # Initial attempt with cls model enabled
    initial_output = ocr(img_np, use_cls=True)
    initial_txts = list(initial_output.txts or ())
    initial_scores = list(initial_output.scores or ())

    avg_score = mean(initial_scores) if initial_scores else 0.0
    # If initial run found confident text, return immediately (fast path)
    if initial_txts and avg_score >= 0.50:
        return initial_txts, initial_scores, 0, initial_output

    if not try_rotations_on_failure:
        return initial_txts, initial_scores, 0, initial_output

    # Check 90, 180, 270 degree rotations if initial extraction was poor/empty
    best_txts = initial_txts
    best_scores = initial_scores
    best_angle = 0
    best_output = initial_output
    best_metric = (len(initial_txts), avg_score)

    for angle in (90, 180, 270):
        rotated_img = preprocessed.rotate(angle, expand=True)
        rot_output = ocr(np.array(rotated_img), use_cls=True)
        rot_txts = list(rot_output.txts or ())
        rot_scores = list(rot_output.scores or ())
        rot_avg = mean(rot_scores) if rot_scores else 0.0
        metric = (len(rot_txts), rot_avg)

        # Higher text count, or substantially better score with similar text count
        if (len(rot_txts) > len(best_txts) and rot_avg >= 0.40) or (len(rot_txts) == len(best_txts) and rot_avg > best_metric[1] + 0.1):
            best_txts = rot_txts
            best_scores = rot_scores
            best_angle = angle
            best_output = rot_output
            best_metric = metric

    return best_txts, best_scores, best_angle, best_output
