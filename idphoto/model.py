import hashlib
import os
from pathlib import Path
import sys

MODEL_NAME = 'u2net_human_seg'
MODEL_MD5 = 'c09ddc2e0104f800e3e1bb4652583d1f'


def model_directory() -> Path:
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    return root / 'models'


def verify_model(directory: Path) -> Path:
    path = directory / f'{MODEL_NAME}.onnx'
    if not path.is_file():
        raise RuntimeError('缺少 AI 模型。源码版请先运行 python scripts/prepare_model.py；'
                           'EXE 版请重新解压完整程序目录。')
    with path.open('rb') as file:
        digest = hashlib.file_digest(file, 'md5').hexdigest()
    if digest != MODEL_MD5:
        raise RuntimeError('AI 模型校验失败，请删除损坏的模型并重新运行模型准备脚本。')
    return path


class PortraitRemover:
    def __init__(self, directory: Path | None = None):
        directory = directory or model_directory()
        verify_model(directory)
        os.environ['U2NET_HOME'] = str(directory)
        try:
            from rembg import new_session, remove
            self._remove = remove
            self.session = new_session(MODEL_NAME, providers=['CPUExecutionProvider'])
        except Exception as error:
            raise RuntimeError(f'AI 模型加载失败，请检查运行依赖及完整程序目录：{error}') from error
        from .framing import FaceDetector
        self.face_detector = FaceDetector(directory)

    def __call__(self, image):
        from PIL import Image
        from .matting import refine_cutout

        # Bound foreground estimation while retaining more source detail
        # than the final 358 x 441 image. Never mutate the caller's image.
        working = image.convert('RGB')
        working.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        mask = self._remove(working, session=self.session, only_mask=True,
                            post_process_mask=False)
        cutout = refine_cutout(working, mask)
        cutout.info['model'] = MODEL_NAME
        from .framing import plan_crop
        try:
            framing = plan_crop(cutout, self.face_detector.detect(working))
            cutout.info['crop_box'] = framing.box
            cutout.info['framing'] = framing.reason
        except Exception as error:
            cutout.info['framing'] = f'保留原构图：人脸检测失败（{type(error).__name__}）'
        return cutout
