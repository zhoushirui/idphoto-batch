from io import BytesIO
import json
import random
import sys
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pytest

from idphoto.core import (MAX_BYTES, MIN_BYTES, SIZE, compose_portrait,
                          create_result_folder, discover, encode_jpeg,
                          process_batch, read_image, save_unique)
from idphoto.model import PortraitRemover, verify_model


@pytest.mark.parametrize('extension', ['jpg', 'jpeg', 'png', 'JPG'])
def test_read_and_discover(tmp_path, extension):
    folder = tmp_path / '中文照片'
    folder.mkdir()
    path = folder / f'张三.{extension}'
    Image.new('RGB', (100, 140), 'blue').save(path)
    (folder / 'child').mkdir()
    Image.new('RGB', (10, 10)).save(folder / 'child' / 'ignored.jpg')
    (folder / 'ignored.txt').write_text('no')
    assert discover(folder) == [path]
    assert read_image(path).mode == 'RGB'


def test_exif_orientation(tmp_path):
    path = tmp_path / 'rotate.jpg'
    exif = Image.Exif()
    exif[274] = 6
    Image.new('RGB', (80, 120)).save(path, exif=exif)
    assert read_image(path).size == (120, 80)


def test_white_size_mode_and_aspect_ratio():
    cutout = Image.new('RGBA', (200, 300))
    ImageDraw.Draw(cutout).rectangle((50, 30, 149, 229), fill=(20, 30, 40, 255))
    result = compose_portrait(cutout)
    assert result.size == SIZE
    assert result.mode == 'RGB'
    assert result.getpixel((0, 0)) == (255, 255, 255)
    from PIL import ImageChops
    bounds = ImageChops.difference(result, Image.new('RGB', SIZE, 'white')).getbbox()
    assert abs((bounds[2] - bounds[0]) / (bounds[3] - bounds[1]) - 0.5) < 0.01
    data, _, _ = encode_jpeg(result)
    with Image.open(BytesIO(data)) as saved:
        assert saved.format == 'JPEG'
        assert saved.mode == 'RGB'
        assert saved.size == SIZE
        assert saved.getpixel((0, 0)) == (255, 255, 255)


def test_empty_subject():
    with pytest.raises(ValueError, match='未识别'):
        compose_portrait(Image.new('RGBA', (20, 20)))


def test_jpeg_search_and_limits():
    rng = random.Random(42)
    # Smooth, detailed image whose quality=100 export exceeds the upper limit.
    source = Image.frombytes('RGB', (20, 20), rng.randbytes(20 * 20 * 3))
    image = source.resize(SIZE, Image.Resampling.BILINEAR)
    data, quality, compliant = encode_jpeg(image)
    assert compliant
    assert MIN_BYTES <= len(data) <= MAX_BYTES
    assert 60 <= quality < 100
    tiny, quality, compliant = encode_jpeg(Image.new('RGB', SIZE, 'white'))
    assert len(tiny) < MIN_BYTES and quality == 100 and not compliant
    noisy = Image.frombytes('RGB', SIZE, rng.randbytes(SIZE[0] * SIZE[1] * 3))
    large, _, compliant = encode_jpeg(noisy)
    assert len(large) > MAX_BYTES and not compliant


def test_collision_and_originals_and_continue(tmp_path):
    folder = tmp_path / '输入'
    folder.mkdir()
    for suffix in ('jpg', 'png'):
        Image.new('RGB', (120, 150), 'gray').save(folder / f'张三.{suffix}')
    (folder / 'broken.jpg').write_bytes(b'not an image')
    originals = {p: p.read_bytes() for p in folder.iterdir()}
    output = create_result_folder(tmp_path)
    results = process_batch(discover(folder), output, lambda image: image.convert('RGBA'))
    assert [r.status for r in results].count('failed') == 1
    assert len(list(output.glob('*.jpg'))) == 2
    assert (output / '张三_证件照.jpg').exists()
    assert (output / '张三_证件照_2.jpg').exists()
    for path, data in originals.items():
        assert path.read_bytes() == data
    for result in results:
        if result.output:
            assert result.size_bytes == __import__('pathlib').Path(result.output).stat().st_size
            assert (result.status == 'success') == (MIN_BYTES <= result.size_bytes <= MAX_BYTES)
    report = json.loads((output / '处理报告.json').read_text(encoding='utf-8'))
    assert report['kb_bytes'] == 1024
    assert len(report['results']) == 3
    assert create_result_folder(tmp_path) != output
    assert save_unique(output, '张三', b'data').name == '张三_证件照_3.jpg'


def test_ai_failure_continues(tmp_path):
    paths = []
    for n in range(2):
        path = tmp_path / f'{n}.png'
        Image.new('RGB', (10, 20)).save(path)
        paths.append(path)
    calls = []
    def remove(image):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError('推理失败')
        return image.convert('RGBA')
    results = process_batch(paths, create_result_folder(tmp_path), remove)
    assert results[0].status == 'failed'
    assert results[1].status != 'failed'


def test_model_missing_corrupt_and_load_error(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match='缺少 AI 模型'):
        PortraitRemover(tmp_path)
    (tmp_path / 'u2net_human_seg.onnx').write_bytes(b'bad')
    with pytest.raises(RuntimeError, match='校验失败'):
        verify_model(tmp_path)
    monkeypatch.setattr('idphoto.model.verify_model', lambda directory: None)
    def fail(*args, **kwargs):
        raise ValueError('invalid runtime')
    monkeypatch.setitem(sys.modules, 'rembg', SimpleNamespace(new_session=fail, remove=None))
    with pytest.raises(RuntimeError, match='AI 模型加载失败'):
        PortraitRemover(tmp_path)
