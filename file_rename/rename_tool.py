import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class RenameToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("파일명 문자열 제거 도구")
        self.root.geometry("720x560")
        self.root.resizable(True, True)

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # 경로 선택
        path_frame = ttk.LabelFrame(self.root, text="대상 폴더")
        path_frame.pack(fill="x", **pad)

        self.path_var = tk.StringVar(value=os.path.dirname(os.path.abspath(__file__)))
        ttk.Entry(path_frame, textvariable=self.path_var, width=60).pack(side="left", fill="x", expand=True, padx=(6, 2), pady=6)
        ttk.Button(path_frame, text="찾아보기", command=self._browse).pack(side="left", padx=(0, 6), pady=6)

        # 옵션
        opt_frame = ttk.LabelFrame(self.root, text="옵션")
        opt_frame.pack(fill="x", **pad)

        ttk.Label(opt_frame, text="제거할 문자열:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.target_var = tk.StringVar(value=" (1)")
        ttk.Entry(opt_frame, textvariable=self.target_var, width=30).grid(row=0, column=1, sticky="w", padx=4, pady=6)

        self.subdir_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="하위 폴더 포함", variable=self.subdir_var).grid(row=0, column=2, padx=12)

        self.case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="대소문자 구분 안 함", variable=self.case_var).grid(row=0, column=3, padx=4)

        # 버튼
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", **pad)
        ttk.Button(btn_frame, text="미리보기", command=self._preview).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="전체 선택", command=self._select_all).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="전체 해제", command=self._deselect_all).pack(side="left", padx=4)
        self.apply_btn = ttk.Button(btn_frame, text="이름 변경 적용", command=self._apply, state="disabled")
        self.apply_btn.pack(side="right", padx=4)

        # 미리보기 테이블
        table_frame = ttk.LabelFrame(self.root, text="미리보기 (체크된 항목만 적용)")
        table_frame.pack(fill="both", expand=True, **pad)

        cols = ("check", "before", "after", "folder")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("check", text="적용")
        self.tree.heading("before", text="변경 전")
        self.tree.heading("after", text="변경 후")
        self.tree.heading("folder", text="폴더")
        self.tree.column("check", width=40, anchor="center", stretch=False)
        self.tree.column("before", width=220)
        self.tree.column("after", width=220)
        self.tree.column("folder", width=180)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<ButtonRelease-1>", self._toggle_check)

        # 상태바
        self.status_var = tk.StringVar(value="준비")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief="sunken").pack(fill="x", side="bottom", padx=8, pady=(0, 4))

        # 내부 데이터: {iid: {"checked": bool, "dir": str, "before": str, "after": str}}
        self._rows = {}

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.path_var.get())
        if d:
            self.path_var.set(d)

    def _get_files(self):
        root_dir = self.path_var.get()
        if not os.path.isdir(root_dir):
            messagebox.showerror("오류", "유효한 폴더를 선택하세요.")
            return []
        files = []
        if self.subdir_var.get():
            for dirpath, _, filenames in os.walk(root_dir):
                for f in filenames:
                    files.append((dirpath, f))
        else:
            for f in os.listdir(root_dir):
                full = os.path.join(root_dir, f)
                if os.path.isfile(full):
                    files.append((root_dir, f))
        return files

    def _remove_string(self, name, target):
        if self.case_var.get():
            idx = name.lower().find(target.lower())
            while idx != -1:
                name = name[:idx] + name[idx + len(target):]
                idx = name.lower().find(target.lower())
            return name
        else:
            return name.replace(target, "")

    def _preview(self):
        target = self.target_var.get()
        if not target:
            messagebox.showwarning("경고", "제거할 문자열을 입력하세요.")
            return

        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows.clear()

        files = self._get_files()
        count = 0
        for dirpath, filename in files:
            new_name = self._remove_string(filename, target)
            if new_name != filename:
                iid = self.tree.insert("", "end", values=("✔", filename, new_name, dirpath))
                self._rows[iid] = {"checked": True, "dir": dirpath, "before": filename, "after": new_name}
                count += 1

        if count == 0:
            self.status_var.set("변경할 파일이 없습니다.")
            self.apply_btn.config(state="disabled")
        else:
            self.status_var.set(f"{count}개 파일 발견 — 미리보기 완료")
            self.apply_btn.config(state="normal")

    def _toggle_check(self, event):
        region = self.tree.identify_region(event.x, event.y)
        col = self.tree.identify_column(event.x)
        if region == "cell" and col == "#1":
            iid = self.tree.identify_row(event.y)
            if iid in self._rows:
                self._rows[iid]["checked"] = not self._rows[iid]["checked"]
                mark = "✔" if self._rows[iid]["checked"] else ""
                vals = list(self.tree.item(iid, "values"))
                vals[0] = mark
                self.tree.item(iid, values=vals)

    def _select_all(self):
        for iid, row in self._rows.items():
            row["checked"] = True
            vals = list(self.tree.item(iid, "values"))
            vals[0] = "✔"
            self.tree.item(iid, values=vals)

    def _deselect_all(self):
        for iid, row in self._rows.items():
            row["checked"] = False
            vals = list(self.tree.item(iid, "values"))
            vals[0] = ""
            self.tree.item(iid, values=vals)

    def _apply(self):
        selected = [(row["dir"], row["before"], row["after"]) for row in self._rows.values() if row["checked"]]
        if not selected:
            messagebox.showinfo("안내", "적용할 항목이 없습니다.")
            return

        confirm = messagebox.askyesno("확인", f"{len(selected)}개 파일의 이름을 변경하시겠습니까?")
        if not confirm:
            return

        success, failed = 0, []
        for dirpath, before, after in selected:
            src = os.path.join(dirpath, before)
            dst = os.path.join(dirpath, after)
            try:
                if os.path.exists(dst):
                    raise FileExistsError(f"이미 존재하는 파일: {after}")
                os.rename(src, dst)
                success += 1
            except Exception as e:
                failed.append(f"{before} → {after}: {e}")

        msg = f"{success}개 파일 이름 변경 완료."
        if failed:
            msg += f"\n실패 {len(failed)}건:\n" + "\n".join(failed)
            messagebox.showwarning("완료 (일부 실패)", msg)
        else:
            messagebox.showinfo("완료", msg)

        self.status_var.set(msg.split("\n")[0])
        self._preview()


if __name__ == "__main__":
    root = tk.Tk()
    app = RenameToolApp(root)
    root.mainloop()
