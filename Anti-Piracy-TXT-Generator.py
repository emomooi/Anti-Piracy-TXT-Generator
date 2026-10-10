# -*- coding: utf-8 -*-
"""
假文包生成器 —— 防盗文诱饵工具（支持末尾保留、字数一致、编码选择）
"""

import os
import re
import random
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# ----------------------------------------------------------------------
# 默认章节标题正则：匹配 "第 1 章 xxx" / "第一章 xxx" 等
# ----------------------------------------------------------------------
DEFAULT_CHAPTER_RE = r'^\s*(第\s*\d+\s*章.*)$'


# ----------------------------------------------------------------------
# 文件读写
# ----------------------------------------------------------------------
def read_text_file(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xef\xbb\xbf'):
        return raw.decode('utf-8-sig'), 'utf-8-sig'
    for enc in ('utf-8', 'gb18030'):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace'), 'utf-8(有损)'


# ----------------------------------------------------------------------
# 填充源（精确截取字数）
# ----------------------------------------------------------------------
class FillerSource:
    def __init__(self, text, rng):
        paras = [p for p in text.split('\n') if p.strip()]
        if not paras:
            paras = ['　　（本章内容暂缺，请支持正版）']
        self.paras = paras
        self.rng = rng

    def take(self, length):
        """精确返回指定长度的文本"""
        if length <= 0:
            return ''
        out, total = [], 0
        idx = self.rng.randrange(len(self.paras))
        n = len(self.paras)
        guard = 0
        # 循环拼接段落，直到总长度 >= 目标长度
        while total < length and guard < 200000:
            p = self.paras[idx % n]
            out.append(p)
            total += len(p) + 1  # +1 代表换行符
            idx += 1
            guard += 1
        result = '\n'.join(out)
        # 精确截断到目标长度（解决最后一段超出的问题）
        return result[:length]


# ----------------------------------------------------------------------
# 章节切分
# ----------------------------------------------------------------------
def split_chapters(text, pattern):
    rx = re.compile(pattern, re.MULTILINE)
    matches = list(rx.finditer(text))
    if not matches:
        return []

    chapters = []
    if matches[0].start() > 0:
        pre = text[:matches[0].start()]
        if pre.strip():
            chapters.append((None, pre))

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((m.group(1).strip(), text[start:end]))

    return chapters


# ----------------------------------------------------------------------
# 核心替换逻辑（保证字数绝对一致）
# ----------------------------------------------------------------------
def replace_middle(body, head_keep, tail_keep, filler):
    paras = body.split('\n')
    n = len(paras)

    hi, acc = 0, 0
    while hi < n and acc < head_keep:
        acc += len(paras[hi]) + 1
        hi += 1

    ti, acc = n, 0
    while ti > hi and acc < tail_keep:
        ti -= 1
        acc += len(paras[ti]) + 1

    if ti <= hi:
        return body, 0, False  # 章太短，保持原样

    head_text = '\n'.join(paras[:hi])
    tail_text = '\n'.join(paras[ti:])

    # 计算原中间段的精确字符数（包含内部的换行符）
    original_mid_len = len(body) - len(head_text) - len(tail_text)
    if head_text and tail_text:
        original_mid_len -= 2  # 减去头尾与中间段连接的两个换行符
    elif head_text or tail_text:
        original_mid_len -= 1  # 减去一个换行符

    if original_mid_len < 0:
        return body, 0, False

    # 获取精确长度的填充文本
    fill = filler.take(original_mid_len)

    # 重新拼接（保证总长度与原 body 完全一致）
    new_body = head_text
    if head_text and fill:
        new_body += '\n'
    new_body += fill
    if tail_text and fill:
        new_body += '\n'
    new_body += tail_text

    return new_body, original_mid_len, True


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------
def generate(text, cfg, log):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    orig_total_len = len(text)

    chapters = split_chapters(text, cfg['pattern'])
    if not chapters:
        raise ValueError('没有识别到任何章节标题，请调整「章节标题正则」。')

    log(f'📖 识别到 {len(chapters)} 个章节块。')

    free_n = cfg['free_n']
    tail_free_n = cfg['tail_free_n']

    if free_n + tail_free_n >= len(chapters):
        raise ValueError(f'前 {free_n} 章 + 末尾 {tail_free_n} 章 ≥ 总章节数，没有需要处理的章节。')

    if free_n == 0 and tail_free_n == 0:
        raise ValueError('前免费章节数和末尾保留章节数不能同时为 0。')

    # 收集填充素材库
    free_chapters = chapters[:free_n]
    tail_chapters = chapters[len(chapters) - tail_free_n:] if tail_free_n > 0 else []
    filler_chapters = free_chapters + tail_chapters

    free_text = '\n'.join(b for _, b in filler_chapters)
    if not free_text.strip():
        raise ValueError('填充素材章节内容为空，无法作为填充源。')

    log(f'🔒 前 {free_n} 章、末尾 {tail_free_n} 章保持原样，作为填充素材库（{len(free_text)} 字）。')

    filler = FillerSource(free_text, cfg['rng'])

    out_parts = []
    changed = 0
    total_mid = 0

    tail_start_idx = len(chapters) - tail_free_n

    for i, (title, body) in enumerate(chapters):
        if i < free_n or i >= tail_start_idx:
            out_parts.append(body)
            continue

        new_body, mid_len, ok = replace_middle(body, cfg['head_keep'], cfg['tail_keep'], filler)
        out_parts.append(new_body)
        if ok:
            changed += 1
            total_mid += mid_len

    result_text = ''.join(out_parts)
    new_total_len = len(result_text)

    log(f'✂️ 已改写 {changed} 章，替换中段约 {total_mid} 字。')
    log(f'📊 原文字数：{orig_total_len} 字')
    log(f'📊 假文包字数：{new_total_len} 字')

    if orig_total_len == new_total_len:
        log('✅ 字数完全一致，完美伪装！')
    else:
        log(f'⚠️ 字数存在差异：相差 {new_total_len - orig_total_len} 字')

    return result_text


# ----------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title('假文包生成器 · 防盗文诱饵版')
        root.geometry('900x700')
        root.minsize(780, 580)

        self.queue = queue.Queue()
        self.running = False

        self._build_ui()
        self.root.after(120, self._poll)

    def _build_ui(self):
        pad = {'padx': 6, 'pady': 5}
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill='both', expand=True)
        frm.columnconfigure(1, weight=1)

        # 源文件
        ttk.Label(frm, text='源 TXT：').grid(row=0, column=0, sticky='e', **pad)
        self.var_in = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_in).grid(row=0, column=1, sticky='ew', **pad)
        ttk.Button(frm, text='浏览…', command=self.pick_in, width=8).grid(row=0, column=2, **pad)

        # 输出文件
        ttk.Label(frm, text='输出到：').grid(row=1, column=0, sticky='e', **pad)
        self.var_out = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_out).grid(row=1, column=1, sticky='ew', **pad)
        ttk.Button(frm, text='浏览…', command=self.pick_out, width=8).grid(row=1, column=2, **pad)

        ttk.Separator(frm, orient='horizontal').grid(
            row=2, column=0, columnspan=3, sticky='ew', pady=10)

        # 参数区
        opts = ttk.LabelFrame(frm, text='参数设置', padding=10)
        opts.grid(row=3, column=0, columnspan=3, sticky='ew')
        opts.columnconfigure(1, weight=1)
        opts.columnconfigure(3, weight=1)

        # 行 0：前免费章数 | 末尾保留章数
        ttk.Label(opts, text='前免费章节数（前 N 章不动）：').grid(row=0, column=0, sticky='e', **pad)
        self.var_free = tk.IntVar(value=3)
        ttk.Spinbox(opts, from_=0, to=9999, textvariable=self.var_free, width=10).grid(
            row=0, column=1, sticky='w', **pad)

        ttk.Label(opts, text='末尾保留章节数（后 N 章不动）：').grid(row=0, column=2, sticky='e', **pad)
        self.var_tail_free = tk.IntVar(value=0)
        ttk.Spinbox(opts, from_=0, to=9999, textvariable=self.var_tail_free, width=10).grid(
            row=0, column=3, sticky='w', **pad)

        # 行 1：章首字数 | 章尾字数
        ttk.Label(opts, text='章首保留字数：').grid(row=1, column=0, sticky='e', **pad)
        self.var_head = tk.IntVar(value=1000)
        ttk.Spinbox(opts, from_=0, to=100000, increment=100,
                    textvariable=self.var_head, width=10).grid(
            row=1, column=1, sticky='w', **pad)

        ttk.Label(opts, text='章尾保留字数：').grid(row=1, column=2, sticky='e', **pad)
        self.var_tail = tk.IntVar(value=1000)
        ttk.Spinbox(opts, from_=0, to=100000, increment=100,
                    textvariable=self.var_tail, width=10).grid(
            row=1, column=3, sticky='w', **pad)

        # 行 2：章节正则 | 输出编码
        ttk.Label(opts, text='章节标题正则：').grid(row=2, column=0, sticky='e', **pad)
        self.var_re = tk.StringVar(value=DEFAULT_CHAPTER_RE)
        ttk.Entry(opts, textvariable=self.var_re).grid(
            row=2, column=1, columnspan=2, sticky='ew', **pad)

        ttk.Label(opts, text='输出编码：').grid(row=2, column=2, sticky='e', **pad)
        self.var_encoding = tk.StringVar(value='UTF-8 (无BOM)')
        enc_combo = ttk.Combobox(opts, textvariable=self.var_encoding,
                                 values=['UTF-8 (无BOM)', 'UTF-8 (带BOM)', 'ANSI (GBK)'],
                                 state='readonly', width=18)
        enc_combo.grid(row=2, column=3, sticky='w', **pad)

        # 行 3：随机种子
        ttk.Label(opts, text='随机种子（可空）：').grid(row=3, column=0, sticky='e', **pad)
        self.var_seed = tk.StringVar()
        ttk.Entry(opts, textvariable=self.var_seed, width=12).grid(
            row=3, column=1, sticky='w', **pad)

        ttk.Label(
            opts,
            text='提示：程序会自动确保生成前后的总字数完全一致（包含换行符）。',
            foreground='#666'
        ).grid(row=4, column=0, columnspan=4, sticky='w', padx=6)

        # 按钮
        btn_bar = ttk.Frame(frm)
        btn_bar.grid(row=4, column=0, columnspan=3, sticky='ew', pady=12)

        self.btn_run = ttk.Button(btn_bar, text='🚀 生成假文包', command=self.run)
        self.btn_run.pack(side='left')

        ttk.Button(btn_bar, text='清空日志', command=self.clear_log).pack(side='left', padx=8)

        self.progress = ttk.Progressbar(btn_bar, mode='indeterminate', length=180)
        self.progress.pack(side='right')

        # 日志
        ttk.Label(frm, text='运行日志：').grid(row=5, column=0, sticky='w')
        self.log_text = ScrolledText(frm, height=14, state='disabled', wrap='word')
        self.log_text.grid(row=6, column=0, columnspan=3, sticky='nsew', pady=(4, 0))
        frm.rowconfigure(6, weight=1)

    def pick_in(self):
        p = filedialog.askopenfilename(
            title='选择正版 TXT',
            filetypes=[('文本文件', '*.txt'), ('所有文件', '*.*')])
        if not p:
            return
        self.var_in.set(p)
        if not self.var_out.get():
            base, ext = os.path.splitext(p)
            self.var_out.set(f'{base}_假文包{ext or ".txt"}')

    def pick_out(self):
        p = filedialog.asksaveasfilename(
            title='保存假文包',
            defaultextension='.txt',
            filetypes=[('文本文件', '*.txt'), ('所有文件', '*.*')])
        if p:
            self.var_out.set(p)

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

    def log(self, msg):
        self.queue.put(msg)

    def _poll(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                self.log_text.configure(state='normal')
                self.log_text.insert('end', msg + '\n')
                self.log_text.see('end')
                self.log_text.configure(state='disabled')
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def run(self):
        if self.running:
            return

        src = self.var_in.get().strip()
        dst = self.var_out.get().strip()

        if not src or not os.path.isfile(src):
            messagebox.showerror('错误', '请选择有效的源 TXT 文件。')
            return
        if not dst:
            messagebox.showerror('错误', '请指定输出文件路径。')
            return

        try:
            pattern = self.var_re.get().strip()
            re.compile(pattern, re.MULTILINE)
        except re.error as e:
            messagebox.showerror('正则错误', f'章节标题正则无法编译：\n{e}')
            return

        seed_txt = self.var_seed.get().strip()
        if seed_txt:
            try:
                seed = int(seed_txt)
            except ValueError:
                seed = seed_txt
        else:
            seed = random.randrange(1 << 30)

        cfg = {
            'pattern': pattern,
            'free_n': int(self.var_free.get()),
            'tail_free_n': int(self.var_tail_free.get()),
            'head_keep': int(self.var_head.get()),
            'tail_keep': int(self.var_tail.get()),
            'rng': random.Random(seed),
        }

        self.running = True
        self.btn_run.configure(state='disabled')
        self.progress.start(12)
        self.log('─' * 46)
        self.log(f'▶ 开始处理（随机种子：{seed}）')

        t = threading.Thread(target=self._worker, args=(src, dst, cfg), daemon=True)
        t.start()

    def _worker(self, src, dst, cfg):
        try:
            text, enc = read_text_file(src)
            self.log(f'📄 读取 {os.path.basename(src)}（编码 {enc}，{len(text)} 字）')

            result = generate(text, cfg, self.log)

            # 根据用户选择决定输出编码
            enc_choice = self.var_encoding.get()
            if enc_choice == 'UTF-8 (无BOM)':
                out_encoding = 'utf-8'
            elif enc_choice == 'UTF-8 (带BOM)':
                out_encoding = 'utf-8-sig'
            else:  # ANSI (GBK)
                out_encoding = 'gb18030'  # gb18030 兼容 GBK，支持更多生僻字

            with open(dst, 'w', encoding=out_encoding, newline='\n') as f:
                f.write(result)

            self.log(f'✅ 完成！已写出：{dst}')
            self.log(f'   文件大小：{os.path.getsize(dst) / 1024:.1f} KB (编码：{enc_choice})')
        except Exception as e:
            self.log(f'❌ 出错：{e}')
            self.root.after(0, lambda: messagebox.showerror('处理失败', str(e)))
        finally:
            self.root.after(0, self._done)

    def _done(self):
        self.progress.stop()
        self.btn_run.configure(state='normal')
        self.running = False


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        elif 'clam' in style.theme_names():
            style.theme_use('clam')
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()