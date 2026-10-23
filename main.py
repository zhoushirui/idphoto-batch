import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='批量证件照白底转换')
    parser.add_argument('--input', type=Path, help='命令行模式：输入文件夹')
    parser.add_argument('--output-parent', type=Path, help='结果文件夹的存放位置')
    parser.add_argument('--smoke-test', action='store_true', help='验证本地模型、推理与图片输出后退出')
    args = parser.parse_args()
    if args.input or args.smoke_test:
        from idphoto.core import compose_portrait, create_result_folder, discover, encode_jpeg, process_batch
        from idphoto.model import PortraitRemover
        remover = PortraitRemover()
        if args.smoke_test:
            from PIL import Image
            result = remover(Image.new('RGB', (64, 64), 'white'))
            assert result.size == (64, 64)
            assert result.mode == 'RGBA'
            data, _, _ = encode_jpeg(compose_portrait(Image.new('RGBA', (100, 150), 'gray')))
            assert data[:2] == b'\xff\xd8'
            print('Offline model inference and JPEG encoding smoke test passed.')
            return
        paths = discover(args.input)
        if not paths:
            raise SystemExit('输入目录没有支持的图片')
        output = create_result_folder(args.output_parent or args.input.parent)
        results = process_batch(paths, output, remover,
                                lambda i, r: print(f'{i}/{len(paths)} {Path(r.source).name}: {r.status} {r.error}'))
        print(f'输出：{output}')
        if any(r.status != 'success' for r in results):
            raise SystemExit(2)
    else:
        try:
            import tkinter as tk
            from idphoto.gui import Application
        except ImportError as error:
            raise SystemExit('缺少 Tkinter，请安装带 Tcl/Tk 的 Python；详见 README。') from error
        root = tk.Tk()
        Application(root)
        root.mainloop()


if __name__ == '__main__':
    import sys
    try:
        main()
    except Exception as error:
        # Windowed EXEs have no stderr. A CI smoke test must fail without
        # opening a blocking PyInstaller exception dialog on the runner.
        if sys.stderr is not None:
            import traceback
            traceback.print_exc()
        elif '--smoke-test' not in sys.argv:
            from tkinter import messagebox
            messagebox.showerror('启动失败', str(error))
        raise SystemExit(1)
