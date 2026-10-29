import hashlib
import io

import pytest

from scripts import prepare_model


@pytest.mark.parametrize('existing,bad_checksum', [(False, False), (True, False), (False, True)])
def test_prepare_model_cp1252(tmp_path, monkeypatch, existing, bad_checksum):
    directory = tmp_path / '中文模型目录'
    directory.mkdir()
    payload = b'test model bytes'
    target = directory / f'{prepare_model.MODEL_NAME}.onnx'
    if existing:
        target.write_bytes(payload)
    monkeypatch.setattr(prepare_model, 'model_directory', lambda: directory)
    monkeypatch.setattr(prepare_model, 'MODEL_MD5', 'invalid' if bad_checksum else hashlib.md5(payload).hexdigest())
    verified = []
    def verify(folder):
        assert target.read_bytes() == payload
        verified.append(folder)
        return target
    monkeypatch.setattr(prepare_model, 'verify_model', verify)
    def download(*args, **kwargs):
        assert not existing, 'Existing model must not be downloaded again'
        return io.BytesIO(payload)
    monkeypatch.setattr(prepare_model, 'urlopen', download)
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding='cp1252', errors='strict')
    monkeypatch.setattr(prepare_model.sys, 'stdout', stream)
    if bad_checksum:
        with pytest.raises(RuntimeError, match='checksum mismatch'):
            prepare_model.prepare_portrait_model()
        assert not target.exists()
    else:
        prepare_model.prepare_portrait_model()
        assert verified == [directory]
    stream.flush()
    assert buffer.getvalue().isascii()
    assert not target.with_suffix('.onnx.part').exists()
