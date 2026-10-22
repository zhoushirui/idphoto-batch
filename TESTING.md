# 本机验收记录

日期：2026-10-22。环境：macOS 15.0.1、Apple Silicon、Python 3.13.17、Tk 9.1。

## 已实际验证

- 已在项目 `.venv` 中安装运行、测试、打包依赖，`python -m pip check` 通过。
- `u2net_human_seg.onnx` 已下载到 `models/` 并通过上游 MD5 校验，大小 175997641 字节。
- `python -m pytest -q`：11 passed，1 skipped。跳过项为需要显式提供照片目录的真实 AI 集成测试。
- `IDPHOTO_AI_INPUT=input python -m pytest tests/test_ai.py -q`：1 passed。测试阻止 Python socket 网络连接，6 张照片推理和导出均完成；仅有 rembg/Pillow 上游弃用警告。
- `python main.py --input input --output-parent .`：6 张全部为 `success`，无失败、无大小不合格；结果保存在项目 `证件照处理结果/`。
- 6 张输出均为 JPEG、RGB、358 × 441；远离人物的左上角像素均为 `(255,255,255)`。
- 中文 Tk 窗口实际创建、刷新、关闭成功。在 GUI 集成检查中模拟文件夹选择返回值，使用真实 AI 完成 6 张处理，验证进度条值为 6、合格数为 6，处理期间 Tk 定时回调持续运行（105 次），没有阻塞主事件循环。完成弹窗回调由测试接收，系统文件选择对话框和打开 Finder 按钮未做鼠标点击验收。
- Python 源码和 PyInstaller spec 的语法检查通过。
- GitHub Actions 工作流 YAML 已用本机 YAML 解析器成功读取。
- `python main.py --smoke-test`：源码模型推理和 JPEG 编码自检通过。
- 使用同一 `idphoto.spec` 在 Mac 上完成 PyInstaller onedir 构建，发行目录约 667 MB；确认模型位于 `_internal/models/`。修复源码路径问题后，冻结程序 `dist/IDPhoto/IDPhoto --smoke-test` 在 HTTP/HTTPS 代理指向不可用本地端口时退出码为 0，模型推理及图片编码通过。此产物是 Mac 程序，不是 Windows EXE。

| 输入 | 输出字节数 | KB（1024 字节） |
| --- | ---: | ---: |
| 1.jpeg | 28504 | 27.84 |
| 2.jpeg | 28619 | 27.95 |
| 3.png | 28351 | 27.69 |
| 4.png | 29958 | 29.26 |
| 5.jpg | 30611 | 29.89 |
| 6.jpeg | 30013 | 29.31 |

## 视觉复核与已修复问题

- 六张人像比例正常，头顶及主体完整，背景已转换为白色。部分头发轮廓仍能看到轻微原背景色，原图本身的模糊、纹理或标记不会被自动修复。这不是专业证件照审核保证。
- 对两张照片比较了 rembg alpha matting：虽然降低了边缘背景色，但导致肩部缺口，因此没有启用该选项。
- 修复极高噪声图片开启 JPEG optimize 时部分 libjpeg 构建的编码失败：回退普通编码后继续按实际字节数判断。
- 修正压缩测试样本：原随机纹理在质量下限仍超过上限，应归于大小不合格案例；合格搜索案例使用平滑纹理。
- 最初 Python 没有 Tk，已安装匹配扩展并实际验证。Homebrew 安装后配置曾返回警告，但最终 Python/Tk 导入及窗口测试通过。沙盒内桌面窗口创建被 macOS 终止，允许桌面访问后测试成功。
- Mac PyInstaller 首次构建成功，但冻结程序自检发现 pymatting 的 Numba 缓存无法定位源码路径。spec 已调整为以源码模块分发 pymatting/Numba，而不是只放入字节码包；重新构建后的冻结程序自检通过。首次冻结启动的依赖加载/JIT 初始化耗时明显高于后续运行，应等待加载提示。

## 仍需 Windows 验收

- Windows 10/11 x64 的 EXE 构建、启动、中文路径与文件选择对话框。
- PyInstaller 在 Windows 上收集的动态库、资源和模型是否在干净电脑上完整可用。
- 整个 onedir 目录复制到另一台断网 Windows 电脑后的模型加载与真实照片批处理。
- Windows 高 DPI 中文界面布局、进度提示和“打开输出文件夹”。
- GitHub Actions 实际云端构建尚未执行：当前目录没有 Git 仓库/远端配置，需要推送到仓库后运行。YAML 和脚本存在不等同于云端构建成功。

## 本机关键依赖

rembg 2.0.67；Pillow 11.3.0；ONNX Runtime 1.23.2；NumPy 2.5.4；OpenCV headless 5.0.0.93；Numba 0.68.0；SciPy 1.18.1；scikit-image 0.26.0；pymatting 1.1.16；PyInstaller 6.22.3；pytest 8.4.2。

依赖文件限制主要包的兼容版本范围，尚未生成跨平台全量锁文件；Windows CI 安装时需保留依赖检查和真实冻结程序自检。
