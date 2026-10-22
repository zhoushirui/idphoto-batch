@echo off
setlocal
cd /d "%~dp0"
if not exist .venv-build\Scripts\python.exe (
    py -3.13 -m venv .venv-build
    if errorlevel 1 goto :fail
)
set "BUILD_PYTHON=.venv-build\Scripts\python.exe"
"%BUILD_PYTHON%" -c "import sys, struct, tkinter; assert sys.version_info[:2] == (3,13) and struct.calcsize('P') == 8, 'Python 3.13 x64 required'"
if errorlevel 1 goto :fail
"%BUILD_PYTHON%" -m pip install -r requirements-build.txt
if errorlevel 1 goto :fail
"%BUILD_PYTHON%" -m pip check
if errorlevel 1 goto :fail
"%BUILD_PYTHON%" -m pytest -q
if errorlevel 1 goto :fail
"%BUILD_PYTHON%" scripts\prepare_model.py
if errorlevel 1 goto :fail
"%BUILD_PYTHON%" main.py --smoke-test
if errorlevel 1 goto :fail
"%BUILD_PYTHON%" -m PyInstaller --noconfirm --clean idphoto.spec
if errorlevel 1 goto :fail
start /wait "" dist\IDPhoto\IDPhoto.exe --smoke-test
if errorlevel 1 goto :fail
echo Build completed: dist\IDPhoto\IDPhoto.exe
echo Distribute the entire dist\IDPhoto folder.
exit /b 0
:fail
echo Build failed. See errors above.
exit /b 1
