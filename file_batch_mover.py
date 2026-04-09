import os
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path


class FileBatchMover:
    def __init__(self, root):
        self.root = root
        self.root.title("파일 배치 이동기 - 폴더구조 유지")
        self.root.geometry("720x620")
        self.root.resizable(True, True)

        self.is_running = False
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # 소스 경로
        frm_src = ttk.LabelFrame(self.root, text="원본 경로 (A)")
        frm_src.pack(fill="x", **pad)
        self.var_src = tk.StringVar()
        ttk.Entry(frm_src, textvariable=self.var_src, width=60).pack(side="left", padx=5, pady=5, fill="x", expand=True)
        ttk.Button(frm_src, text="찾아보기", command=self._browse_src).pack(side="left", padx=5, pady=5)

        # 대상 경로
        frm_dst = ttk.LabelFrame(self.root, text="저장 경로 (B) — 배치 폴더들이 생성될 위치")
        frm_dst.pack(fill="x", **pad)
        self.var_dst = tk.StringVar()
        ttk.Entry(frm_dst, textvariable=self.var_dst, width=60).pack(side="left", padx=5, pady=5, fill="x", expand=True)
        ttk.Button(frm_dst, text="찾아보기", command=self._browse_dst).pack(side="left", padx=5, pady=5)

        # 옵션
        frm_opt = ttk.Frame(self.root)
        frm_opt.pack(fill="x", **pad)

        ttk.Label(frm_opt, text="배치당 최대 파일+폴더 수:").pack(side="left")
        self.var_batch = tk.IntVar(value=500)
        ttk.Spinbox(frm_opt, from_=1, to=100000, textvariable=self.var_batch, width=8).pack(side="left", padx=5)

        ttk.Label(frm_opt, text="   배치 폴더 이름 접두사:").pack(side="left")
        self.var_prefix = tk.StringVar(value="batch")
        ttk.Entry(frm_opt, textvariable=self.var_prefix, width=12).pack(side="left", padx=5)

        # 빈 폴더 포함 옵션
        frm_opt2 = ttk.Frame(self.root)
        frm_opt2.pack(fill="x", padx=10, pady=2)
        self.var_include_empty = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frm_opt2,
            text="빈 폴더(파일 없는 폴더) 포함",
            variable=self.var_include_empty
        ).pack(side="left")

        # 진행 상황
        frm_prog = ttk.LabelFrame(self.root, text="진행 상황")
        frm_prog.pack(fill="x", **pad)

        self.lbl_status = ttk.Label(frm_prog, text="대기 중")
        self.lbl_status.pack(anchor="w", padx=5, pady=2)

        self.progressbar = ttk.Progressbar(frm_prog, mode="determinate")
        self.progressbar.pack(fill="x", padx=5, pady=4)

        self.lbl_count = ttk.Label(frm_prog, text="")
        self.lbl_count.pack(anchor="w", padx=5, pady=2)

        # 로그
        frm_log = ttk.LabelFrame(self.root, text="로그")
        frm_log.pack(fill="both", expand=True, **pad)
        self.log = scrolledtext.ScrolledText(frm_log, height=14, state="disabled", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=5, pady=5)

        # 버튼
        frm_btn = ttk.Frame(self.root)
        frm_btn.pack(fill="x", padx=10, pady=8)
        self.btn_start = ttk.Button(frm_btn, text="시작", command=self._start, width=14)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(frm_btn, text="중지", command=self._stop, width=14, state="disabled")
        self.btn_stop.pack(side="left", padx=4)
        ttk.Button(frm_btn, text="로그 지우기", command=self._clear_log, width=14).pack(side="right", padx=4)

    # ── UI 헬퍼 ──────────────────────────────────────────────

    def _browse_src(self):
        path = filedialog.askdirectory(title="원본 폴더 선택")
        if path:
            self.var_src.set(path)

    def _browse_dst(self):
        path = filedialog.askdirectory(title="저장 폴더 선택")
        if path:
            self.var_dst.set(path)

    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _set_status(self, text):
        self.lbl_status.config(text=text)

    def _set_count(self, text):
        self.lbl_count.config(text=text)

    def _set_progress(self, value, maximum):
        self.progressbar["maximum"] = maximum
        self.progressbar["value"] = value

    # ── 제어 ────────────────────────────────────────────────

    def _start(self):
        src = self.var_src.get().strip()
        dst = self.var_dst.get().strip()
        batch_size = self.var_batch.get()
        prefix = self.var_prefix.get().strip() or "batch"

        if not src or not os.path.isdir(src):
            messagebox.showerror("오류", "유효한 원본 경로를 선택하세요.")
            return
        if not dst:
            messagebox.showerror("오류", "저장 경로를 선택하세요.")
            return
        if batch_size < 1:
            messagebox.showerror("오류", "배치 크기는 1 이상이어야 합니다.")
            return

        # 원본이 대상 안에 있으면 안 됨
        src_abs = os.path.abspath(src)
        dst_abs = os.path.abspath(dst)
        if dst_abs == src_abs or dst_abs.startswith(src_abs + os.sep):
            messagebox.showerror("오류", "저장 경로가 원본 경로 안에 있으면 안 됩니다.")
            return

        self.is_running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._clear_log()

        include_empty = self.var_include_empty.get()
        thread = threading.Thread(
            target=self._run, args=(src_abs, dst_abs, batch_size, prefix, include_empty), daemon=True
        )
        thread.start()

    def _stop(self):
        self.is_running = False
        self._set_status("중지 요청됨 — 현재 파일 완료 후 중단됩니다")

    # ── 핵심 로직 ────────────────────────────────────────────

    def _run(self, src, dst, batch_size, prefix, include_empty):
        try:
            self._log(f"원본 폴더 스캔 중: {src}")
            self._set_status("항목 목록 수집 중...")

            # 1) 모든 항목 수집: (rel_path, 'file'|'dir')
            #    - 비어있지 않은 폴더: 항상 카운트
            #    - 비어있는 폴더: include_empty 옵션에 따라 포함 여부 결정
            #    - 파일: 항상 카운트
            all_items = []  # (rel_path, type)

            for root_dir, dirs, files in os.walk(src):
                rel_root = os.path.relpath(root_dir, src)
                is_empty_dir = (not dirs and not files)

                # 루트 자신은 제외, 빈 폴더는 옵션에 따라
                if rel_root != ".":
                    if not is_empty_dir or include_empty:
                        all_items.append((rel_root, "dir"))

                for fname in sorted(files):
                    rel_path = os.path.relpath(os.path.join(root_dir, fname), src)
                    all_items.append((rel_path, "file"))

            total_items = len(all_items)
            total_files = sum(1 for _, t in all_items if t == "file")
            total_dirs  = sum(1 for _, t in all_items if t == "dir")

            if total_items == 0:
                self._log("항목이 없습니다.")
                self._finish(False)
                return

            total_batches = max(1, (total_items + batch_size - 1) // batch_size)
            self._log(f"총 항목: {total_items:,}개  (파일 {total_files:,} + 빈폴더 {total_dirs:,})")
            self._log(f"배치 크기: {batch_size:,}  |  배치 수: {total_batches}")
            self._log("-" * 60)

            # 2) 배치별 처리
            processed = 0
            copied_files = 0

            for batch_idx in range(total_batches):
                if not self.is_running:
                    self._log("⛔ 사용자에 의해 중단되었습니다.")
                    self._finish(False)
                    return

                batch_items = all_items[batch_idx * batch_size: (batch_idx + 1) * batch_size]
                batch_name  = f"{prefix}_{batch_idx + 1:03d}"
                batch_dst   = os.path.join(dst, batch_name)

                b_files = sum(1 for _, t in batch_items if t == "file")
                b_dirs  = sum(1 for _, t in batch_items if t == "dir")
                self._log(f"[{batch_name}] 파일 {b_files:,}개 + 빈폴더 {b_dirs:,}개 처리 시작")

                for rel_path, item_type in batch_items:
                    if not self.is_running:
                        self._log("⛔ 사용자에 의해 중단되었습니다.")
                        self._finish(False)
                        return

                    if item_type == "dir":
                        os.makedirs(os.path.join(batch_dst, rel_path), exist_ok=True)
                    else:
                        dst_file = os.path.join(batch_dst, rel_path)
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        shutil.copy2(os.path.join(src, rel_path), dst_file)
                        copied_files += 1

                    processed += 1
                    self.root.after(0, self._set_progress, processed, total_items)
                    self.root.after(0, self._set_count,
                                    f"{processed:,} / {total_items:,} 항목  ({batch_name})")

                self._log(f"  ✔ [{batch_name}] 완료 → {batch_dst}")

            self._log("-" * 60)
            self._log(f"✅ 완료! 파일 {copied_files:,}개 + 빈폴더 {total_dirs:,}개 → {total_batches}개 배치 폴더")
            self._log(f"📂 저장 위치: {dst}")
            self._log("")
            self._log("※ 합치는 방법 (Windows):")
            for i in range(1, total_batches + 1):
                bname = f"{prefix}_{i:03d}"
                self._log(f"   xcopy /E /H /Y \"{os.path.join(dst, bname)}\" \"<최종 경로>\\\"")
            self._finish(True)

        except Exception as e:
            self._log(f"❌ 오류 발생: {e}")
            self._finish(False)

    def _finish(self, success):
        self.is_running = False
        self.root.after(0, self.btn_start.config, {"state": "normal"})
        self.root.after(0, self.btn_stop.config, {"state": "disabled"})
        status = "완료" if success else "중단/오류"
        self.root.after(0, self._set_status, status)
        if success:
            self.root.after(0, messagebox.showinfo, "완료", "모든 파일 복사가 완료되었습니다!")


def main():
    root = tk.Tk()
    app = FileBatchMover(root)
    root.mainloop()


if __name__ == "__main__":
    main()
