"""Offline face detection and conservative portrait crop planning."""
from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

FACE_MODEL = 'face_detection_yunet_2023mar.onnx'
FACE_SHA256 = '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'
FACE_URL = 'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/' + FACE_MODEL


def verify_face_model(directory: Path) -> Path:
    path = directory / FACE_MODEL
    if not path.is_file():
        raise RuntimeError('缺少构图模型，请运行 python scripts/prepare_model.py；EXE 版请重新解压完整程序目录。')
    if hashlib.sha256(path.read_bytes()).hexdigest() != FACE_SHA256:
        raise RuntimeError('构图模型校验失败，请重新准备模型或重新解压完整程序目录。')
    return path


class FaceDetector:
    def __init__(self, directory: Path):
        import cv2
        path = verify_face_model(directory)
        try:
            # Buffer loading avoids native filename encoding issues on Windows.
            self.detector = cv2.FaceDetectorYN.create(
                'onnx', np.frombuffer(path.read_bytes(), dtype=np.uint8),
                np.empty(0, dtype=np.uint8), (320, 320), 0.7, 0.3, 5000)
        except Exception as error:
            raise RuntimeError(f'构图模型加载失败：{error}') from error

    def detect(self, image: Image.Image) -> np.ndarray:
        scale = min(320 / image.width, 320 / image.height)
        width, height = round(image.width * scale), round(image.height * scale)
        frame = np.zeros((320, 320, 3), dtype=np.uint8)
        frame[:height, :width] = np.asarray(image.convert('RGB').resize(
            (width, height), Image.Resampling.BILINEAR))[:, :, ::-1]
        _, faces = self.detector.detect(frame)
        if faces is None:
            return np.empty((0, 15), dtype=np.float32)
        faces = faces.copy()
        faces[:, 0:14:2] *= image.width / width
        faces[:, 1:14:2] *= image.height / height
        return faces


@dataclass(frozen=True)
class Framing:
    box: tuple[int, int, int, int] | None
    reason: str


def plan_crop(cutout: Image.Image, faces: np.ndarray) -> Framing:
    if len(faces) != 1:
        return Framing(None, '保留原构图：未检测到单一人脸')
    face = np.asarray(faces[0], dtype=float)
    if face.shape != (15,) or not np.isfinite(face).all() or face[14] < 0.9:
        return Framing(None, '保留原构图：人脸检测置信度不足')
    x, y, fw, fh = face[:4]
    width, height = cutout.size
    eyes = face[4:8].reshape(2, 2)
    if (min(fw, fh) < 24 or x < 0 or y < 0 or x + fw > width or y + fh > height
            or not 0.45 < fw / fh < 1.3
            or abs(eyes[0, 1] - eyes[1, 1]) > 0.12 * fw
            or np.any(eyes[:, 0] < x) or np.any(eyes[:, 0] > x + fw)
            or np.any(eyes[:, 1] < y) or np.any(eyes[:, 1] > y + fh)):
        return Framing(None, '保留原构图：人脸位置或姿态不适合自动裁剪')
    if fh / height >= 0.35:
        return Framing(None, '保留原构图：近景照片无需放大')
    if fh / height < 0.12:
        return Framing(None, '保留原构图：人脸过小，请使用清晰的上半身照')

    crop_h = fh / 0.46
    crop_w = crop_h * 358 / 441
    center_x, eye_y = eyes.mean(axis=0)
    left, top = center_x - crop_w / 2, eye_y - 0.40 * crop_h
    # Inspect the head's central strip above the eyes to retain hair/headroom.
    alpha = np.asarray(cutout.getchannel('A'))
    start, end = max(0, int(x - 0.2 * fw)), min(width, int(x + 1.2 * fw))
    rows = np.flatnonzero((alpha[:int(eye_y), start:end] > 64).sum(axis=1) >= max(3, int(fw * 0.08)))
    if not len(rows):
        return Framing(None, '保留原构图：无法可靠确定头顶')
    top = min(top, float(rows[0]) - 0.04 * crop_h)
    box = (round(left), round(top), round(left + crop_w), round(top + crop_h))
    if (box[0] < 0 or box[1] < 0 or box[2] > width or box[3] > height
            or x < box[0] or x + fw > box[2] or y + fh > box[3] - 0.1 * crop_h):
        return Framing(None, '保留原构图：原图空间不足以安全裁剪')
    return Framing(box, '自动构图：按人脸比例裁剪')
