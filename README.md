# 批量证件照白底转换

Python + Tkinter 桌面工具，使用 rembg 的 `u2net_human_seg` 人像模型和 ONNX Runtime CPU 推理。照片在本机处理，不上传、不采集遥测。支持 macOS 和 Windows 共用代码。

## 环境和安装

推荐 **Python 3.13 64 位**，开发与 Windows CI 统一使用此版本。不要使用 Python 3.14 创建本项目环境。Mac 推荐 Apple Silicon、macOS 14 或更新版本；其他 Mac 架构和旧系统需要确认依赖轮子兼容性，尚未验证。Windows 目标为 Windows 10/11 x64；安装 python.org Python 时启用 Tcl/Tk、pip 和 Python Launcher。

运行依赖见 `requirements.txt`；开发测试及打包依赖见 `requirements-build.txt`。rembg 固定为 2.0.67，Pillow、ONNX Runtime 和打包工具限定兼容版本范围。

### macOS

推荐使用带 Tk 的 python.org Python 3.13，或者通过 Homebrew 安装：

```bash
brew install python@3.13 python-tk@3.13
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
python -m pip check
python scripts/prepare_model.py
python main.py
```

若出现 `No module named _tkinter`，需要为创建虚拟环境所用的 Python 安装匹配的 Tk 扩展，必要时重建虚拟环境。不要通过 `pip install tkinter` 解决。

### Windows（PowerShell）

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\prepare_model.py
.\.venv\Scripts\python.exe main.py
```

不要求激活虚拟环境，避免 PowerShell 执行策略问题。

## 使用

1. 点击“选择输入文件夹”，只读取直接子文件中的 JPG/JPEG/PNG，支持中文路径、文件名和大写扩展名。
2. 可选“选择输出位置”，程序始终在该位置新建唯一的结果文件夹；默认位置为输入文件夹的父目录。
3. 点击“开始处理”，后台线程加载一次模型并逐张处理，界面显示进度、当前文件、合格/失败/大小不合格数量。
4. 完成后打开输出文件夹，人工复核照片和 `处理报告.json`。损坏文件和单张推理失败不会中止其他照片。

输出名为 `原文件名_证件照.jpg`，重名自动增加 `_2` 等编号。创建结果目录及写图片都采用防覆盖方式，不修改原图。文件选择阶段显示的是支持扩展名的数量，内容有效性在处理时确认。

也可以使用命令行：

```bash
python main.py --input input --output-parent .
```

每次运行创建新的 `证件照处理结果` 或带编号的目录。全部合格时退出码为 0；有失败或大小不合格时为 2；模型等致命错误为非零。

## 处理规则与限制

- 读取时应用 EXIF 旋转，处理原图透明通道；推理工作图最长边限制为 1024 像素，控制边缘求解的内存占用。
- rembg 只提供掩膜，原图 RGB 不预乘 alpha，避免重复乘透明度造成黑边。通常保留模型原始透明度，仅用 pymatting 温和修正半透明边缘颜色；不重新求解透明度，不腐蚀或模糊轮廓，避免把低清原图的压缩色块变成台阶。对背景高度一致且与深色衣服明显不同的照片，仅修复衣服内部成片的透明度误判，保留外轮廓和零散像素。完全不透明区域保留原 RGB；颜色估计失败时回退原图颜色，并在调试记录中注明。为保持自然轮廓，允许少量背景残色，原模型的分割误差仍需人工复核。
- 在工作图分辨率完成去污染和白底合成，再等比例缩放整张照片，居中放入 **358 × 441 RGB 纯白画布**。保留原图构图，不再按人物边界重新缩小排版；原图宽高比不同时增加白色留边。
- 第一版没有人脸检测。推荐清晰单人上半身正面照；全身照、多人物、遮挡或原图已缺失的头发/肩部无法保证专业证件照构图。复杂背景与头发边缘可能有残留，AI 结果必须人工复核。
- JPEG 采用 4:4:4 色度采样、优化编码，从 quality=100 到 60 逐档搜索，选择满足 **10240–30720 字节（包含边界）**的最高质量结果。1 KB = 1024 字节。
- 若最高质量仍低于 10 KB，则保留该结果并标记大小不合格；若 quality≥60 都大于 30 KB，则保存此范围内字节数最小的结果并标记大小不合格。不会填充文件、修改像素尺寸或静默当作成功。
- 每张保存后重新读取检查 JPEG/RGB/尺寸并检查实际文件字节数。`success` 表示这些机器指标合格，**不代表 AI 分割或证件照身份审核通过**。
- 合成画布确实为 RGB(255,255,255)，测试会检查导出后远离主体的白色区域。JPEG 是有损格式，人物边缘附近的白色像素可能因块压缩出现微小偏差，无法保证所有背景像素解码后逐点严格等于 255；需要逐点无损白色时应采用 PNG，但本工具按需求固定输出 JPG。
- 处理期间请勿移动/修改输入文件，关闭窗口会提示等待批次结束。

## 调试输出

正常使用仅保存最终 JPG 和 `处理报告.json`，不再生成“调试输出”文件夹。开发排查时可显式调用 `process_batch(..., debug_output=True)`，额外保存 `调试输出/最终文件名（不含扩展名）/`：

- `01-cutout.png`：工作分辨率透明人像，用于检查 alpha 和前景颜色。
- `02-white-source.png`：缩放前的无损白底照片。
- `03-white-358x441.png`：缩放后的无损白底照片，不受 30 KB 限制。
- `details.json`：模型、细化算法或回退原因、工作尺寸、最终 JPG 字节数和质量。

最终压缩 JPG 在结果文件夹根目录。依次对比上述文件可定位抠图、缩放或 JPEG 压缩问题。调试图会增加磁盘占用，复核后可删除“调试输出”子目录。

## 模型与离线运行

联网准备阶段运行 `python scripts/prepare_model.py`，下载约 176 MB 的模型到项目 `models/u2net_human_seg.onnx`，并验证上游 MD5。模型不会提交到 Git。模型地址和校验值来自 [rembg 2.0.67 人像模型实现](https://github.com/danielgatis/rembg/blob/v2.0.67/rembg/sessions/u2net_human_seg.py)。模型来源及许可需随 [U-2-Net 上游](https://github.com/xuebinqin/U-2-Net) 的条款使用。

程序正常启动前检查模型存在和校验值，缺失/损坏会清楚报错，不在界面中隐式下载。`U2NET_HOME` 指向项目模型目录，冻结程序则指向 PyInstaller `_MEIPASS/models`；源码版和 EXE 都复用同一套路径逻辑。无需 API Key、独立显卡或手动配置推理框架。

准备好依赖和模型后，源码程序可离线运行。Windows 打包配置会随程序包含模型与依赖，但在真实 Windows EXE 测试通过前，不应声称 Windows 离线交付已验证。

## 测试

不需要模型的基础测试：

```bash
python -m pytest -q
```

覆盖读图、中文路径、非递归扫描、EXIF 旋转、等比例排版、白底、JPEG 格式/RGB/尺寸、质量搜索及大小上下限异常、重名防覆盖、原图保护、损坏图片及推理异常后继续、模型缺失/损坏/加载失败。默认跳过真实 AI 测试。

真实 AI 测试（使用自备照片，不将私人照片上传到仓库）：

```bash
IDPHOTO_AI_INPUT=input python -m pytest tests/test_ai.py -q
python main.py --smoke-test
```

PowerShell：

```powershell
$env:IDPHOTO_AI_INPUT = 'input'
.\.venv\Scripts\python.exe -m pytest tests/test_ai.py -q
Remove-Item Env:IDPHOTO_AI_INPUT
```

真实测试验证推理及编码流程，不会将大小异常伪装成合格，也不代替人工观察抠图效果。`--smoke-test` 使用合成图片验证模型推理和编码，可以对打包后的 EXE 使用。

## Windows 打包

**必须在 Windows x64 上构建 Windows EXE。macOS 构建产物不能作为 Windows 软件分发。**

在项目根目录执行：

```bat
build_windows.bat
```

脚本创建独立 `.venv-build`、检查 Python/Tk 位数及版本、安装依赖、检查依赖、运行基础测试、准备模型、运行源码推理自检，然后使用 `idphoto.spec` 和 PyInstaller `--clean --noconfirm` 构建，并运行 EXE 推理自检。任何步骤失败立即返回非零退出码。

构建结果：`dist/IDPhoto/IDPhoto.exe`。使用 **onedir** 模式，必须分发整个 `dist/IDPhoto/` 目录（包含 `_internal` 下的模型、动态库和资源），不能只复制 EXE。spec 收集 rembg、ONNX Runtime、图像/数值库及其运行资源，Tk 使用 PyInstaller 标准钩子。pymatting 和 Numba 以 Python 源码模块形式分发，避免冻结后 Numba 缓存找不到源码路径。模型约 176 MB，加上 CPU 推理依赖，整个发行目录会明显大于普通 Tk 小程序。

Windows 上还需手动验收：双击 EXE 启动中文界面、断网状态下模型加载、中文路径和多张真实图片处理、结果大小提示、打开输出目录、全新电脑上运行。自检不能覆盖这些全部行为。

## GitHub Actions

`.github/workflows/windows-build.yml` 使用官方 `windows-latest` x64 Runner，支持推送 `main` 自动构建以及 Actions 页面手动 `Run workflow`。

流水线安装 Python 3.13 和依赖 → 基础测试 → 下载校验模型 → 源码推理自检 → PyInstaller onedir 构建 → 禁用 HTTP/HTTPS 代理通路的 EXE 推理自检 → 压缩完整 `IDPhoto` 文件夹 → 上传 `IDPhoto-Windows-x64` artifact。测试/构建失败不会执行成功产物上传。下载 artifact 后解压内部 ZIP，再运行目录中的 EXE。

Runner 构建阶段需要访问 PyPI 和 GitHub 模型下载地址。代理自检验证无需在线下载模型，不等同于在完全隔离网络的 Windows 电脑上验收。工作流需推送到实际 GitHub 仓库后才能触发；本地创建 YAML 不表示云端构建已执行。

## 文件结构

```text
main.py                       GUI / CLI 入口
idphoto/core.py               图片处理、压缩、批处理报告
idphoto/model.py              模型路径、校验、CPU 推理
idphoto/matting.py            保留透明轮廓的温和边缘颜色修正
idphoto/gui.py                Tkinter 和后台线程事件队列
scripts/prepare_model.py      显式联网下载模型
tests/                       单元测试和真实 AI 测试
models/                      本地模型（忽略 Git）
requirements*.txt             运行及构建依赖
idphoto.spec                  Windows onedir 资源配置
build_windows.bat             Windows 一键构建
.github/workflows/            GitHub Windows 构建
```

实际环境验收记录见 `TESTING.md`。
