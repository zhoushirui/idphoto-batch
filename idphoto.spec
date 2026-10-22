# Build on Windows using: python -m PyInstaller --noconfirm --clean idphoto.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH)
model = root / 'models' / 'u2net_human_seg.onnx'
if not model.is_file():
    raise RuntimeError('Run python scripts/prepare_model.py before packaging')

datas = [(str(model), 'models')]
binaries = []
hiddenimports = []
for package in ('rembg', 'onnxruntime', 'pymatting', 'scipy', 'skimage', 'numba', 'llvmlite'):
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
