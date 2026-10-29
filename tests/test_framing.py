import hashlib
import io

import numpy as np
import pytest
from PIL import Image

from idphoto.core import compose_portrait
from idphoto.framing import FACE_MODEL, plan_crop, verify_face_model
from scripts import prepare_model


def sample():
    cutout = Image.new('RGBA', (800, 1000))
    cutout.paste((40, 40, 40, 255), (260, 180, 540, 1000))
    face = np.array([[280, 240, 240, 300, 340, 340, 460, 340,
                      400, 400, 350, 480, 450, 480, .99]])
    return cutout, face


def test_crop_protects_head_and_places_eyes():
    cutout, faces = sample()
    framing = plan_crop(cutout, faces)
    left, top, right, bottom = framing.box
    assert 0 <= left < 280 < 520 < right <= 800
    assert 0 <= top < 180 < 540 < bottom <= 1000
    assert abs((right - left) / (bottom - top) - 358 / 441) < .003
    assert abs((340 - top) / (bottom - top) - .4) < .01
    cutout.info['crop_box'] = framing.box
    output = compose_portrait(cutout)
    assert output.size == (358, 441)
    assert output.mode == 'RGB'
    assert output.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize('case', ['none', 'multiple', 'confidence', 'nan', 'tilt', 'close', 'space'])
def test_uncertain_or_close_photo_is_preserved(case):
    cutout, faces = sample()
    if case == 'none':
        faces = np.empty((0, 15))
    elif case == 'multiple':
        faces = np.repeat(faces, 2, axis=0)
    elif case == 'confidence':
        faces[0, 14] = .8
    elif case == 'nan':
        faces[0, 0] = np.nan
    elif case == 'tilt':
        faces[0, 5] += 50
    elif case == 'close':
        faces[0, 3] = 380
    elif case == 'space':
        cutout.paste((40, 40, 40, 255), (260, 0, 540, 180))
    assert plan_crop(cutout, faces).box is None


def test_missing_and_corrupt_face_model(tmp_path):
    with pytest.raises(RuntimeError, match='缺少构图模型'):
        verify_face_model(tmp_path)
    (tmp_path / FACE_MODEL).write_bytes(b'bad')
    with pytest.raises(RuntimeError, match='校验失败'):
        verify_face_model(tmp_path)


@pytest.mark.parametrize('bad', [False, True])
def test_face_download_checksum_and_ascii_log(tmp_path, monkeypatch, bad):
    payload = b'face model'
    monkeypatch.setattr(prepare_model, 'model_directory', lambda: tmp_path)
    monkeypatch.setattr(prepare_model, 'FACE_SHA256', 'bad' if bad else hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(prepare_model, 'urlopen', lambda *a, **kw: io.BytesIO(payload))
    monkeypatch.setattr(prepare_model, 'verify_face_model', lambda d: d / FACE_MODEL)
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding='cp1252', errors='strict')
    monkeypatch.setattr(prepare_model.sys, 'stdout', stream)
    if bad:
        with pytest.raises(RuntimeError, match='checksum mismatch'):
            prepare_model.prepare_face_model()
        assert not (tmp_path / FACE_MODEL).exists()
    else:
        prepare_model.prepare_face_model()
        assert (tmp_path / FACE_MODEL).read_bytes() == payload
        monkeypatch.setattr(prepare_model, 'urlopen', lambda *a, **kw: pytest.fail('Unexpected download'))
        prepare_model.prepare_face_model()
    stream.flush()
    assert buffer.getvalue().isascii()
    assert not list(tmp_path.glob('*.part'))
