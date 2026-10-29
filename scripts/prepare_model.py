"""Explicit network step; normal application startup never downloads models."""
import hashlib
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from idphoto.model import MODEL_MD5, MODEL_NAME, model_directory, verify_model
from idphoto.framing import FACE_MODEL, FACE_SHA256, FACE_URL, verify_face_model


def prepare_portrait_model():
    directory = model_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{MODEL_NAME}.onnx'
    if target.exists():
        print(f'Model already verified: {ascii(str(verify_model(directory)))}')
        return
    temporary = target.with_suffix('.onnx.part')
    url = f'https://github.com/danielgatis/rembg/releases/download/v0.0.0/{MODEL_NAME}.onnx'
    print('Downloading portrait model (about 176 MB)...', flush=True)
    try:
        digest = hashlib.md5()
        with urlopen(url, timeout=60) as response, temporary.open('wb') as file:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                file.write(chunk)
        if digest.hexdigest() != MODEL_MD5:
            raise RuntimeError('Downloaded model checksum mismatch. Please retry.')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Model downloaded and verified: {ascii(str(verify_model(directory)))}')


def prepare_face_model():
    directory = model_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / FACE_MODEL
    if target.exists():
        print(f'Face model already verified: {ascii(str(verify_face_model(directory)))}')
        return
    temporary = target.with_suffix('.onnx.part')
    print('Downloading face detection model...', flush=True)
    try:
        with urlopen(FACE_URL, timeout=60) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != FACE_SHA256:
            raise RuntimeError('Downloaded face model checksum mismatch. Please retry.')
        temporary.write_bytes(payload)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Face model downloaded and verified: {ascii(str(verify_face_model(directory)))}')


def main():
    prepare_portrait_model()
    prepare_face_model()


if __name__ == '__main__':
    main()
