import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import create_result_folder, discover, process_batch
from .model import PortraitRemover


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.paths = []
        self.input_folder = None
        self.output_parent = None
        self.output = None
        self.busy = False
        self.remover = None
        self.events = queue.Queue()
        self._build_ui()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def _build_ui(self):
        root = self.root
        root.title('证件照批量处理器')
        root.geometry('820x740')
        root.minsize(740, 740)
        root.configure(background='#f3f5f9')
        family = 'PingFang SC' if sys.platform == 'darwin' else 'Microsoft YaHei UI'
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=(family, 11), background='#f3f5f9', foreground='#253249')
        style.configure('Page.TFrame', background='#f3f5f9')
        style.configure('Card.TFrame', background='#ffffff')
        style.configure('Card.TLabel', background='#ffffff')
        style.configure('Muted.TLabel', background='#ffffff', foreground='#778399', font=(family, 10))
        style.configure('Title.TLabel', font=(family, 22, 'bold'), foreground='#18273f')
        style.configure('Subtitle.TLabel', foreground='#778399', font=(family, 10))
        style.configure('Heading.TLabel', background='#ffffff', font=(family, 12, 'bold'))
        style.configure('TButton', padding=(16, 10), background='#eef2f8', borderwidth=0,
                        foreground='#40536d', focusthickness=2, focuscolor='#aac9ff')
        style.map('TButton', background=[('disabled', '#f1f3f6'), ('pressed', '#dbe4f0'),
                                        ('active', '#e3eaf4')],
                  foreground=[('disabled', '#9aa5b5')])
        style.configure('Primary.TButton', background='#3478f6', foreground='white',
                        font=(family, 12, 'bold'), padding=(24, 12))
        style.map('Primary.TButton', background=[('disabled', '#dce6f7'), ('pressed', '#205dca'),
                                                ('active', '#2469e3')],
                  foreground=[('disabled', '#8196b5')])
        style.configure('Photo.Horizontal.TProgressbar', troughcolor='#edf1f7',
                        background='#3478f6', borderwidth=0, lightcolor='#3478f6',
                        darkcolor='#3478f6', thickness=8)
        panel = ttk.Frame(root, style='Page.TFrame', padding=(30, 22))
        panel.pack(fill='both', expand=True)
        header = ttk.Frame(panel, style='Page.TFrame')
        header.pack(fill='x', pady=(0, 18))
        ttk.Label(header, text='证件照批量处理器', style='Title.TLabel').pack(side='left')
        ttk.Label(header, text='中国工商银行北京市分行',
                  style='Subtitle.TLabel').pack(side='right', anchor='n', pady=(8, 0))
        specs = ttk.Frame(panel, style='Page.TFrame')
        specs.pack(fill='x', pady=(0, 14))
        for text in ('纯白背景', '358 × 441 像素', 'JPG 格式', '10–30 KB'):
            tk.Label(specs, text=text, font=(family, 10), bg='#e8eef9', fg='#547095',
                     padx=12, pady=4).pack(side='left', padx=(0, 8))

        files = ttk.Frame(panel, style='Card.TFrame', padding=16)
        files.pack(fill='x')
        files.columnconfigure(0, weight=1)
        ttk.Label(files, text='01  选择照片', style='Heading.TLabel').grid(row=0, column=0, sticky='w')
        self.photo_count = tk.StringVar(value='尚未选择')
        ttk.Label(files, textvariable=self.photo_count, style='Muted.TLabel').grid(row=0, column=1, sticky='e')
        self.input_text = tk.StringVar(value='选择一个包含 JPG、JPEG 或 PNG 的文件夹')
        self.output_text = tk.StringVar(value='默认在原文件夹旁新建结果文件夹')
        ttk.Label(files, textvariable=self.input_text, style='Muted.TLabel',
                  wraplength=460).grid(row=1, column=0, sticky='w', pady=(10, 14), padx=(0, 12))
        self.choose = ttk.Button(files, text='选择文件夹', command=self.select_input)
        self.choose.grid(row=1, column=1, sticky='e', pady=(10, 14))
        ttk.Separator(files).grid(row=2, column=0, columnspan=2, sticky='ew')
        ttk.Label(files, text='保存位置', style='Card.TLabel').grid(row=3, column=0, sticky='w', pady=(16, 4))
        ttk.Label(files, textvariable=self.output_text, style='Muted.TLabel',
                  wraplength=460).grid(row=4, column=0, sticky='w', padx=(0, 12))
        self.choose_output = ttk.Button(files, text='更改位置', command=self.select_output)
        self.choose_output.grid(row=3, column=1, rowspan=2, sticky='e', pady=(12, 0))

        processing = ttk.Frame(panel, style='Card.TFrame', padding=16)
        processing.pack(fill='x', pady=(16, 0))
        heading = ttk.Frame(processing, style='Card.TFrame')
        heading.pack(fill='x')
        ttk.Label(heading, text='02  开始转换', style='Heading.TLabel').pack(side='left')
        self.progress_text = tk.StringVar(value='准备就绪')
        ttk.Label(heading, textvariable=self.progress_text, style='Muted.TLabel').pack(side='right')
        self.status = tk.StringVar(value='选择照片后，点击下方按钮开始处理。')
        ttk.Label(processing, textvariable=self.status, style='Muted.TLabel',
                  wraplength=650).pack(anchor='w', pady=(14, 12))
        self.progress = ttk.Progressbar(processing, mode='determinate', style='Photo.Horizontal.TProgressbar')
        self.progress.pack(fill='x')
        metrics = ttk.Frame(processing, style='Card.TFrame')
        metrics.pack(fill='x', pady=(12, 0))
        self.metric_values = {}
        for column, (key, title, color) in enumerate((('success', '已合格', '#218466'),
                                                     ('failed', '处理失败', '#bd5461'),
                                                     ('size_warning', '大小待复核', '#b78229'))):
            metrics.columnconfigure(column, weight=1, uniform='metric')
            box = tk.Frame(metrics, background='#f7f9fc', padx=12, pady=9)
            box.grid(row=0, column=column, sticky='ew', padx=(0 if column == 0 else 8, 0))
            variable = tk.StringVar(value='0')
            self.metric_values[key] = variable
            tk.Label(box, textvariable=variable, font=(family, 20, 'bold'),
                     foreground=color, background='#f7f9fc').pack(anchor='w')
            tk.Label(box, text=title, font=(family, 10), foreground='#778399',
                     background='#f7f9fc').pack(anchor='w')
        self.counts = tk.StringVar(value='合格 0 · 失败 0 · 大小不合格 0')
        actions = ttk.Frame(panel, style='Page.TFrame')
        actions.pack(fill='x', pady=(14, 0))
        self.start_button = ttk.Button(actions, text='开始处理', style='Primary.TButton',
                                       command=self.start, state='disabled')
        self.start_button.pack(side='left')
        self.open_button = ttk.Button(actions, text='打开结果文件夹', command=self.open_output, state='disabled')
        self.open_button.pack(side='right')

    def select_input(self):
        selected = filedialog.askdirectory(title='选择照片文件夹')
        if not selected:
            return
        try:
            folder = Path(selected)
            paths = discover(folder)
        except OSError as error:
            messagebox.showerror('读取失败', str(error))
            return
        self.input_folder, self.paths = folder, paths
        self.input_text.set(str(folder))
        self.photo_count.set(f'{len(paths)} 张照片')
        self.status.set('已选好照片，可以开始处理。' if paths else '该文件夹中没有 JPG、JPEG 或 PNG 图片。')
        self.start_button.configure(state='normal' if paths else 'disabled')

    def select_output(self):
        selected = filedialog.askdirectory(title='选择结果文件夹的存放位置')
        if selected:
            self.output_parent = Path(selected)
            self.output_text.set(f'将在 {selected} 内新建结果文件夹')

    def start(self):
        if self.busy or not self.paths:
            return
        self.busy = True
        self.totals = {'success': 0, 'failed': 0, 'size_warning': 0}
        self.counts.set('合格 0 · 失败 0 · 大小不合格 0')
        for variable in self.metric_values.values():
            variable.set('0')
        self.progress_text.set(f'0 / {len(self.paths)} · 0%')
        self.start_button.configure(text='正在处理…')
        for widget in (self.choose, self.choose_output, self.start_button, self.open_button):
            widget.configure(state='disabled')
        self.progress.configure(maximum=len(self.paths), value=0)
        self.status.set('正在加载 AI 模型，首次加载可能需要一些时间…')
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        try:
            if self.remover is None:
                self.remover = PortraitRemover()
            self.output = create_result_folder(self.output_parent or self.input_folder.parent)
            self.events.put(('output', self.output))
            def remove(image):
                return self.remover(image)
            # Announce each file before inference, not only after completion.
            def progress(index, result):
                self.events.put(('progress', (index, result)))
                if index < len(self.paths):
                    self.events.put(('status', f'正在处理：{self.paths[index].name}'))
            self.events.put(('status', f'正在处理：{self.paths[0].name}'))
            results = process_batch(self.paths, self.output, remove, progress)
            self.events.put(('done', results))
        except Exception as error:
            self.events.put(('error', str(error)))

    def poll(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == 'output':
                    self.output_text.set(f'输出：{value}')
                elif event == 'status':
                    self.status.set(value)
                elif event == 'progress':
                    index, result = value
                    self.progress.configure(value=index)
                    self.totals[result.status] += 1
                    self.metric_values[result.status].set(str(self.totals[result.status]))
                    self.progress_text.set(f'{index} / {len(self.paths)} · {index / len(self.paths):.0%}')
                    self.counts.set(f"合格 {self.totals['success']} · 失败 {self.totals['failed']} · 大小不合格 {self.totals['size_warning']}")
                elif event in ('done', 'error'):
                    self.busy = False
                    self.start_button.configure(text='再次处理')
                    for widget in (self.choose, self.choose_output, self.start_button):
                        widget.configure(state='normal')
                    if self.output is not None:
                        self.open_button.configure(state='normal')
                    if event == 'error':
                        self.progress_text.set('处理未完成')
                        self.status.set('请根据提示检查后重试。')
                        messagebox.showerror('处理失败', value)
                    else:
                        self.status.set('处理完成，详细结果见输出目录中的处理报告.json')
                        messagebox.showinfo('处理完成', self.counts.get() + '\n请复核照片及处理报告。')
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def open_output(self):
        try:
            if sys.platform == 'win32':
                os.startfile(str(self.output))
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(self.output)])
        except OSError as error:
            messagebox.showerror('无法打开目录', str(error))

    def close(self):
        if self.busy:
            messagebox.showinfo('正在处理', '请等待当前批次完成后关闭窗口。')
        else:
            self.root.destroy()
