"""Opt-in integration test: IDPHOTO_AI_INPUT points to a real portrait directory."""
import os
from pathlib import Path

from PIL import Image
import pytest

from idphoto.core import SIZE, create_result_folder, discover, process_batch
from idphoto.model import PortraitRemover


@pytest.mark.skipif(not os.environ.get('IDPHOTO_AI_INPUT'), reason='真实 AI 测试需设置 IDPHOTO_AI_INPUT')
def test_real_ai(tmp_path, monkeypatch):
    paths = discover(Path(os.environ['IDPHOTO_AI_INPUT']))
    assert paths, '真实测试目录没有图片'
    import socket
    def deny_network(*args, **kwargs):
        raise AssertionError('离线 AI 测试不允许网络连接')
    monkeypatch.setattr(socket.socket, 'connect', deny_network)
    remover = PortraitRemover()
    results = process_batch(paths, create_result_folder(tmp_path), remover)
    assert all(r.status != 'failed' for r in results), results
    for result in results:
        with Image.open(result.output) as image:
            assert image.size == SIZE and image.mode == 'RGB'
            assert image.getpixel((0, 0)) == (255, 255, 255)
