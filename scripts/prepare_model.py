"""Explicit network step; normal application startup never downloads models."""
import hashlib
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from idphoto.model import MODEL_MD5, MODEL_NAME, model_directory, verify_model


def main():
    directory = model_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{MODEL_NAME}.onnx'
    if target.exists():
        print(f'模型已存在：{verify_model(directory)}')
        return
    temporary = target.with_suffix('.onnx.part')
    url = f'https://github.com/danielgatis/rembg/releases/download/v0.0.0/{MODEL_NAME}.onnx'
    print('正在下载人像模型（约 176 MB）…', flush=True)
    try:
        digest = hashlib.md5()
        with urlopen(url, timeout=60) as response, temporary.open('wb') as file:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                file.write(chunk)
        if digest.hexdigest() != MODEL_MD5:
            raise RuntimeError('下载的模型校验失败，请重试')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'模型已下载并校验：{verify_model(directory)}')


if __name__ == '__main__':
    main()
