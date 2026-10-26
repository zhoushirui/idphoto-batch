import numpy as np
from PIL import Image

from idphoto.matting import refine_cutout
from idphoto.core import SIZE, compose_portrait, white_background
from idphoto.model import PortraitRemover


def synthetic_portrait():
    alpha = np.zeros((64, 64))
    alpha[10:64, 12:52] = 1
    alpha[10:64, 10:12] = [0.25, 0.75]
    alpha[10:64, 52:54] = [0.75, 0.25]
    foreground = np.array([25, 25, 25])
    background = np.array([190, 10, 30])
    rgb = alpha[:, :, None] * foreground + (1 - alpha[:, :, None]) * background
    return Image.fromarray(np.rint(rgb).astype('uint8')), alpha


def test_gentle_decontamination_preserves_soft_alpha():
    image, alpha = synthetic_portrait()
    mask = Image.fromarray((alpha * 255).astype('uint8'))
    result = np.asarray(refine_cutout(image, mask))
    np.testing.assert_array_equal(result[:, :, 3], np.asarray(mask))
    np.testing.assert_array_equal(result[25, 30, :3], np.asarray(image)[25, 30])
    edge = result[30, 10, :3].astype(int)
    original = np.asarray(image)[30, 10, :3].astype(int)
    assert 0 < edge[0] - edge[1] < original[0] - original[1]


def test_blocky_source_does_not_turn_smooth_mask_into_steps():
    y, x = np.mgrid[:64, :64]
    # A smooth sloping silhouette over a source with large color blocks.
    alpha = np.clip((x - y * 0.4 - 12) / 8, 0, 1)
    rgb = np.full((64, 64, 3), 180, dtype=np.uint8)
    rgb[(x // 8 + y // 8) % 2 == 0] = [90, 110, 130]
    mask = Image.fromarray(np.rint(alpha * 255).astype('uint8'))
    result = refine_cutout(Image.fromarray(rgb), mask)
    np.testing.assert_array_equal(np.asarray(result)[:, :, 3], np.asarray(mask))


def test_safe_straight_alpha_fallback(monkeypatch):
    image, alpha = synthetic_portrait()
    import pymatting
    def fail(*args, **kwargs):
        raise ValueError('solver failed')
    monkeypatch.setattr(pymatting, 'estimate_foreground_ml', fail)
    mask = Image.fromarray((alpha * 255).astype('uint8'))
    result = refine_cutout(image, mask)
    np.testing.assert_array_equal(np.asarray(result)[:, :, :3], np.asarray(image))
    np.testing.assert_array_equal(np.asarray(result)[:, :, 3], np.asarray(mask))
    assert 'fallback' in result.info['refinement']


def test_composite_before_resize_and_preserve_framing():
    cutout = Image.new('RGBA', SIZE, (0, 0, 0, 0))
    cutout.paste((200, 100, 50, 128), (30, 40, 100, 150))
    output = compose_portrait(cutout)
    assert output.getpixel((40, 50)) == (227, 177, 152)
    assert output.getpixel((29, 50)) == (255, 255, 255)
    assert output.getpixel((100, 50)) == (255, 255, 255)
    # Arbitrary colors in fully transparent pixels cannot create a halo.
    alternate = Image.new('RGBA', SIZE, (0, 255, 0, 0))
    alternate.paste((200, 100, 50, 128), (30, 40, 100, 150))
    assert compose_portrait(alternate).tobytes() == output.tobytes()


def test_whole_frame_fits_without_recropping_subject():
    cutout = Image.new('RGBA', (500, 667))
    cutout.paste((20, 20, 20, 255), (100, 40, 400, 667))
    expected = Image.new('RGB', SIZE, 'white')
    from PIL import ImageOps
    fitted = ImageOps.contain(white_background(cutout), SIZE, Image.Resampling.LANCZOS)
    expected.paste(fitted, ((358 - fitted.width) // 2, (441 - fitted.height) // 2))
    assert compose_portrait(cutout).tobytes() == expected.tobytes()
    assert compose_portrait(cutout).getpixel((179, 440)) == (20, 20, 20)


def test_model_requests_mask_and_does_not_mutate_input():
    remover = PortraitRemover.__new__(PortraitRemover)
    remover.session = object()
    calls = []
    def remove(image, **kwargs):
        calls.append((image.size, kwargs))
        return Image.new('L', image.size, 255)
    remover._remove = remove
    original = Image.new('RGB', (2000, 1500), 'gray')
    result = remover(original)
    assert original.size == (2000, 1500)
    assert result.size == (1024, 768)
    assert calls[0][1] == {'session': remover.session, 'only_mask': True, 'post_process_mask': False}


def test_repairs_clothing_patch_without_changing_edges():
    from idphoto.matting import repair_clothing_alpha
    rgb = np.full((128, 128, 3), [0.75, 0.02, 0.1])
    rgb[40:, 20:108] = 0.1
    alpha = np.zeros((128, 128))
    alpha[40:, 20:108] = 1
    alpha[85:110, 25:35] = 0.4
    alpha[85:87, 60:62] = 0.8  # Tiny uncertainty should be left alone.
    alpha[70:, 20:22] = 0.5  # Preserve the garment's outer soft edge.
    repaired = repair_clothing_alpha(rgb, alpha)
    assert (repaired[85:110, 25:35] == 1).all()
    expected = alpha.copy()
    expected[85:110, 25:35] = 1
    np.testing.assert_array_equal(repaired, expected)
    # A similarly dark backdrop provides insufficient color evidence.
    rgb[alpha == 0] = 0.1
    np.testing.assert_array_equal(repair_clothing_alpha(rgb, alpha), alpha)
