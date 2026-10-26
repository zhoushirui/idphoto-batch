"""Conservative foreground color correction without changing the silhouette."""
import numpy as np
from PIL import Image


def repair_clothing_alpha(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Restore sizeable opacity defects inside dark clothing on a flat backdrop."""
    from scipy.ndimage import distance_transform_edt, label

    background_pixels = rgb[alpha < 0.02]
    if len(background_pixels) < 100:
        return alpha
    background = np.median(background_pixels, axis=0)
    if (np.ptp(background) < 0.35 or
            np.quantile(np.max(abs(background_pixels - background), axis=1), 0.7) > 0.08):
        return alpha
    dark = (rgb.max(axis=2) < 0.27) & (np.linalg.norm(rgb - background, axis=2) > 0.5)
    regions, _ = label(dark)
    counts = np.bincount(regions.ravel())
    trusted = np.bincount(regions.ravel(), weights=(alpha > 0.98).ravel(), minlength=len(counts))
    eligible = (counts >= 100) & (trusted >= 0.6 * counts)
    eligible[0] = False
    # Keep a two-pixel boundary untouched, including soft garment edges.
    interior = distance_transform_edt(eligible[regions]) > 2
    candidate = interior & (alpha > 0.1) & (alpha < 0.98)
    candidate[:int(alpha.shape[0] * 0.55)] = False
    patches, _ = label(candidate)
    patch_sizes = np.bincount(patches.ravel())
    substantial = patch_sizes >= 16
    substantial[0] = False
    repaired = alpha.copy()
    repaired[substantial[patches]] = 1.0
    return repaired


def refine_cutout(image: Image.Image, mask: Image.Image) -> Image.Image:
    from pymatting import estimate_foreground_ml

    rgb = np.asarray(image.convert('RGB'), dtype=np.float64) / 255.0
    alpha = np.asarray(mask.convert('L'), dtype=np.float64) / 255.0
    if alpha.shape != rgb.shape[:2]:
        raise ValueError('分割掩膜与原图尺寸不一致')
    original_alpha = alpha
    alpha = repair_clothing_alpha(rgb, alpha)
    repaired_pixels = int(np.count_nonzero(alpha != original_alpha))
    foreground = rgb.copy()
    note = 'Original mask: insufficient foreground/background seeds.'
    if (alpha > 0.95).any() and (alpha < 0.02).any() and min(alpha.shape) >= 3:
        try:
            estimated = estimate_foreground_ml(rgb, alpha)
            if not np.isfinite(estimated).all():
                raise ValueError('Non-finite foreground result')
            # Keep the model's smooth alpha. Re-solving alpha against compressed
            # source colors can turn JPEG blocks into staircase-shaped edges.
            # Limit color correction and preserve opaque skin/clothing exactly.
            weight = (0.5 * (1.0 - alpha))[..., None]
            foreground = rgb * (1.0 - weight) + estimated * weight
            note = 'Original alpha preserved; gentle foreground color correction.'
        except (ValueError, RuntimeError, np.linalg.LinAlgError) as error:
            note = f'Original mask fallback: {type(error).__name__}: {error}'
    rgba = np.dstack((foreground, alpha))
    cutout = Image.fromarray(np.rint(np.clip(rgba, 0, 1) * 255).astype(np.uint8))
    cutout.info['refinement'] = note + f' Clothing opacity repairs: {repaired_pixels} pixels.'
    return cutout
