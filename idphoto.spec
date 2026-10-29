# Build on Windows using: python -m PyInstaller --noconfirm --clean idphoto.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH)
model = root / 'models' / 'u2net_human_seg.onnx'
if not model.is_file():
    raise RuntimeError('Run python scripts/prepare_model.py before packaging')

face_model = root / 'models' / 'face_detection_yunet_2023mar.onnx'
license_file = root / 'models' / 'YUNET-LICENSE.txt'
if not face_model.is_file() or not license_file.is_file():
    raise RuntimeError('Face model or license missing; run scripts/prepare_model.py')
datas = [(str(path), 'models') for path in (model, face_model, license_file)]
binaries = []
hiddenimports = []
for package in ('rembg', 'onnxruntime', 'pymatting', 'scipy', 'skimage', 'numba', 'llvmlite', 'cv2'):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden
datas += copy_metadata('rembg')

a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, hookspath=[],
             hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
             # Numba's cached functions need real source paths, including
             # when installed in a read-only Windows distribution directory.
             module_collection_mode={'pymatting': 'py', 'numba': 'py'})
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='IDPhoto',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='IDPhoto')
