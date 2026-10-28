from dataclasses import asdict, dataclass
from io import BytesIO
import json
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps

SIZE = (358, 441)
MIN_BYTES = 10 * 1024
MAX_BYTES = 30 * 1024
EXTENSIONS = {'.jpg', '.jpeg', '.png'}


def discover(folder: Path) -> list[Path]:
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS),
                  key=lambda p: p.name.casefold())


def read_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        if image.format not in {'JPEG', 'PNG'}:
            raise ValueError('文件内容不是 JPG/JPEG/PNG 图片')
        image = ImageOps.exif_transpose(image)
        # Transparent source pixels are composited before inference.
        rgba = image.convert('RGBA')
        background = Image.new('RGBA', rgba.size, 'white')
        return Image.alpha_composite(background, rgba).convert('RGB')


def white_background(cutout: Image.Image) -> Image.Image:
    cutout = cutout.convert('RGBA')
    if cutout.getchannel('A').getextrema()[1] == 0:
        raise ValueError('未识别到人物，请使用清晰的单人正面照片')
    background = Image.new('RGBA', cutout.size, (255, 255, 255, 255))
    return Image.alpha_composite(background, cutout).convert('RGB')


def compose_portrait(cutout: Image.Image) -> Image.Image:
    # Composite straight-alpha colors at source resolution before resampling.
    # Fit the full original frame, preserving subject scale and position.
    subject = ImageOps.contain(white_background(cutout), SIZE, Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', SIZE, (255, 255, 255))
    x = (SIZE[0] - subject.width) // 2
    y = (SIZE[1] - subject.height) // 2
    canvas.paste(subject, (x, y))
    return canvas


def encode_jpeg(image: Image.Image) -> tuple[bytes, int, bool]:
    if image.size != SIZE or image.mode != 'RGB':
        raise ValueError('编码前图片必须为 358×441 RGB')
    smallest = None
    # Full descending search avoids assuming JPEG byte size is monotonic.
    for quality in range(100, 59, -1):
        buffer = BytesIO()
        try:
            image.save(buffer, 'JPEG', quality=quality, subsampling=0, optimize=True)
        except OSError:
            # Some libjpeg builds exhaust the optimization buffer for very
            # noisy quality=100 images. The standard encoder remains usable.
            buffer = BytesIO()
            image.save(buffer, 'JPEG', quality=quality, subsampling=0, optimize=False)
        data = buffer.getvalue()
        if smallest is None or len(data) < len(smallest[0]):
            smallest = (data, quality, False)
        if MIN_BYTES <= len(data) <= MAX_BYTES:
            return data, quality, True
        if quality == 100 and len(data) < MIN_BYTES:
            return data, quality, False
    assert smallest is not None
    return smallest


def create_result_folder(parent: Path) -> Path:
    for number in range(1, 100000):
        path = parent / ('证件照处理结果' if number == 1 else f'证件照处理结果_{number}')
        try:
            path.mkdir()
            return path
        except FileExistsError:
            continue
    raise OSError('无法创建唯一结果文件夹')


def save_unique(folder: Path, stem: str, data: bytes) -> Path:
    for number in range(1, 100000):
        suffix = '' if number == 1 else f'_{number}'
        target = folder / f'{stem}{suffix}.jpg'
        try:
            with target.open('xb') as file:
                file.write(data)
            return target
        except FileExistsError:
            continue
    raise OSError('输出文件重名过多')


@dataclass
class Result:
    source: str
    status: str
    output: str = ''
    size_bytes: int = 0
    quality: int = 0
    error: str = ''


def process_batch(paths: list[Path], output: Path,
                  remove: Callable[[Image.Image], Image.Image],
                  progress: Callable[[int, Result], None] | None = None,
                  *, debug_output: bool = False) -> list[Result]:
    results = []
    for index, path in enumerate(paths, 1):
        try:
            cutout = remove(read_image(path))
            image = compose_portrait(cutout)
            data, quality, _ = encode_jpeg(image)
            target = save_unique(output, path.stem, data)
            size = target.stat().st_size
            if debug_output:
                debug = output / '调试输出' / target.stem
                debug.mkdir(parents=True)
                cutout.save(debug / '01-cutout.png')
                white_background(cutout).save(debug / '02-white-source.png')
                image.save(debug / '03-white-358x441.png')
                details = {
                    'model': cutout.info.get('model', 'custom'),
                    'refinement': cutout.info.get('refinement', 'not specified'),
                    'working_size': cutout.size,
                    'final_jpeg': target.name,
                    'size_bytes': size,
                    'quality': quality,
                }
                (debug / 'details.json').write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
            with Image.open(target) as saved:
                if saved.format != 'JPEG' or saved.mode != 'RGB' or saved.size != SIZE:
                    raise ValueError('保存后图片格式校验失败')
            compliant = MIN_BYTES <= size <= MAX_BYTES
            result = Result(str(path), 'success' if compliant else 'size_warning',
                            str(target), size, quality,
                            '' if compliant else '文件大小不在 10–30 KB 内；请人工复核')
        except Exception as error:
            result = Result(str(path), 'failed', error=str(error))
        results.append(result)
        if progress:
            progress(index, result)
    # Output is a newly created run directory; report never touches originals.
    report = {'kb_bytes': 1024, 'results': [asdict(r) for r in results]}
    with (output / '处理报告.json').open('x', encoding='utf-8') as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return results
