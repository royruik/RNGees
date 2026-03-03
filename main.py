"""
GTO RNG — Poker Decision Tool
Always-on-top desktop overlay for GGPoker
Run: python gto_rng.py
"""

import tkinter as tk
from tkinter import font as tkfont
import secrets
import threading
import time

# ── THEME ──────────────────────────────────────────────
BG          = "#0a1a10"
FELT        = "#0d2818"
FELT_MID    = "#1a4028"
FELT_LIGHT  = "#163621"
GOLD        = "#c9a84c"
GOLD_DIM    = "#7a6330"
CREAM       = "#f0e6cc"
DIM         = "#4a6355"
GREEN_ON    = "#2ecc71"
RED         = "#c0392b"
BORDER      = "#1e4a30"

# ── HELPERS ────────────────────────────────────────────
def crypto_rand(lo, hi):
    lo, hi = int(lo), int(hi)
    if lo > hi:
        lo, hi = hi, lo
    return lo + secrets.randbelow(hi - lo + 1)


# ── MAIN APP ───────────────────────────────────────────
class GTORNGApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("GTO RNG")
        self.configure(bg=BG)
        self.overrideredirect(True)       # frameless
        self.wm_attributes("-topmost", True)  # always on top
        self.wm_attributes("-alpha", 0.95)

        # Restore position
        self.geometry("320x80")
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{sw-340}+{sh//2 - 200}")

        self.tables = []
        self._drag_x = 0
        self._drag_y = 0
        self.minimized = False

        self._build_titlebar()
        self._build_body()
        self._add_table("TABLE 1")
        self._add_table("TABLE 2")
        self._update_size()

    # ── TITLEBAR ───────────────────────────────────────
    def _build_titlebar(self):
        bar = tk.Frame(self, bg=FELT_MID, height=32)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Drag
        bar.bind("<ButtonPress-1>", self._drag_start)
        bar.bind("<B1-Motion>", self._drag_motion)

        # Logo
        logo = tk.Label(bar, text="GTO  RNG", bg=FELT_MID, fg=GOLD,
                        font=("Courier New", 11, "bold"), padx=10)
        logo.pack(side="left")
        logo.bind("<ButtonPress-1>", self._drag_start)
        logo.bind("<B1-Motion>", self._drag_motion)

        # Buttons right side
        btn_frame = tk.Frame(bar, bg=FELT_MID)
        btn_frame.pack(side="right", padx=6)

        self._add_btn = self._icon_btn(btn_frame, "+", GOLD, self._on_add_table, "Add table")
        self._add_btn.pack(side="left", padx=2)

        all_btn = self._icon_btn(btn_frame, "⚡", CREAM, self._gen_all, "Generate all")
        all_btn.pack(side="left", padx=2)

        stop_btn = self._icon_btn(btn_frame, "⏹", DIM, self._stop_all, "Stop all timers")
        stop_btn.pack(side="left", padx=2)

        min_btn = self._icon_btn(btn_frame, "—", DIM, self._toggle_minimize, "Minimize")
        min_btn.pack(side="left", padx=2)

        close_btn = self._icon_btn(btn_frame, "✕", RED, self.destroy, "Close")
        close_btn.pack(side="left", padx=2)

    def _icon_btn(self, parent, text, color, cmd, tip=""):
        b = tk.Label(parent, text=text, bg=FELT_MID, fg=color,
                     font=("Courier New", 11), cursor="hand2", padx=4, pady=2)
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg="#254030"))
        b.bind("<Leave>", lambda e: b.configure(bg=FELT_MID))
        return b

    def _drag_start(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _drag_motion(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _toggle_minimize(self):
        self.minimized = not self.minimized
        if self.minimized:
            self.body_frame.pack_forget()
        else:
            self.body_frame.pack(fill="both", expand=True)
        self._update_size()

    # ── BODY ───────────────────────────────────────────
    def _build_body(self):
        self.body_frame = tk.Frame(self, bg=BG)
        self.body_frame.pack(fill="both", expand=True)

        self.tables_frame = tk.Frame(self.body_frame, bg=BG)
        self.tables_frame.pack(fill="both", expand=True, padx=6, pady=6)

    # ── ADD / REMOVE TABLE ─────────────────────────────
    def _on_add_table(self):
        n = len(self.tables) + 1
        self._add_table(f"TABLE {n}")

    def _add_table(self, name="TABLE"):
        t = TablePanel(self.tables_frame, name, on_remove=self._remove_table)
        t.pack(fill="x", pady=(0, 6))
        self.tables.append(t)
        self._update_size()

    def _remove_table(self, panel):
        if panel in self.tables:
            self.tables.remove(panel)
        panel.stop_timer()
        panel.destroy()
        self._update_size()

    # ── GLOBAL ACTIONS ─────────────────────────────────
    def _gen_all(self):
        for t in self.tables:
            t.generate()

    def _stop_all(self):
        for t in self.tables:
            t.stop_timer()

    # ── RESIZE ─────────────────────────────────────────
    def _update_size(self):
        self.update_idletasks()
        w = 320
        h = self.winfo_reqheight()
        x = self.winfo_x()
        y = self.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")


# ── TABLE PANEL ────────────────────────────────────────
class TablePanel(tk.Frame):
    def __init__(self, parent, name, on_remove):
        super().__init__(parent, bg=FELT, bd=0, highlightthickness=1,
                         highlightbackground=BORDER)
        self.on_remove = on_remove
        self._timer_thread = None
        self._timer_running = False
        self._rolling = False

        self._build(name)

    def _build(self, name):
        # ── Header row ──
        hdr = tk.Frame(self, bg=FELT_MID)
        hdr.pack(fill="x")

        # Indicator dot
        self.indicator = tk.Label(hdr, text="●", bg=FELT_MID, fg=DIM,
                                  font=("Courier New", 8), padx=4)
        self.indicator.pack(side="left")

        # Editable name
        self.name_var = tk.StringVar(value=name)
        name_entry = tk.Entry(hdr, textvariable=self.name_var, bg=FELT_MID,
                              fg=GOLD, font=("Courier New", 9, "bold"),
                              bd=0, insertbackground=GOLD, width=14,
                              highlightthickness=0)
        name_entry.pack(side="left", padx=(0, 4), pady=4)

        # Remove button
        rem = tk.Label(hdr, text="✕", bg=FELT_MID, fg=RED,
                       font=("Courier New", 9), cursor="hand2", padx=6)
        rem.pack(side="right")
        rem.bind("<Button-1>", lambda e: self.on_remove(self))
        rem.bind("<Enter>", lambda e: rem.configure(bg="#2a1010"))
        rem.bind("<Leave>", lambda e: rem.configure(bg=FELT_MID))

        # ── Number display ──
        num_frame = tk.Frame(self, bg=FELT)
        num_frame.pack(fill="x", pady=(6, 2))

        self.num_label = tk.Label(num_frame, text="—", bg=FELT,
                                  fg=CREAM, font=("Courier New", 36, "bold"),
                                  anchor="center")
        self.num_label.pack(fill="x")

        self.range_label = tk.Label(num_frame, text="range: 1 – 100",
                                    bg=FELT, fg=DIM,
                                    font=("Courier New", 8))
        self.range_label.pack()

        # ── Controls ──
        ctrl = tk.Frame(self, bg=FELT)
        ctrl.pack(fill="x", padx=6, pady=(4, 2))

        # Generate button
        gen_btn = tk.Button(ctrl, text="GENERATE", bg=FELT_MID, fg=CREAM,
                            font=("Courier New", 10, "bold"),
                            bd=0, activebackground=FELT_LIGHT,
                            activeforeground=GOLD, cursor="hand2",
                            relief="flat", pady=6,
                            command=self.generate)
        gen_btn.pack(fill="x", pady=(0, 6))

        # Range row
        range_row = tk.Frame(ctrl, bg=FELT)
        range_row.pack(fill="x", pady=(0, 4))

        tk.Label(range_row, text="MIN", bg=FELT, fg=DIM,
                 font=("Courier New", 8)).pack(side="left")

        self.min_var = tk.StringVar(value="1")
        min_e = tk.Entry(range_row, textvariable=self.min_var, width=5,
                         bg="#0a1810", fg=CREAM, font=("Courier New", 10),
                         bd=0, insertbackground=CREAM, justify="center",
                         highlightthickness=1, highlightbackground=BORDER)
        min_e.pack(side="left", padx=4)
        self.min_var.trace_add("write", lambda *_: self._update_range_label())

        tk.Label(range_row, text="—", bg=FELT, fg=DIM,
                 font=("Courier New", 10)).pack(side="left")

        self.max_var = tk.StringVar(value="100")
        max_e = tk.Entry(range_row, textvariable=self.max_var, width=5,
                         bg="#0a1810", fg=CREAM, font=("Courier New", 10),
                         bd=0, insertbackground=CREAM, justify="center",
                         highlightthickness=1, highlightbackground=BORDER)
        max_e.pack(side="left", padx=4)
        self.max_var.trace_add("write", lambda *_: self._update_range_label())

        # Timer row
        timer_row = tk.Frame(ctrl, bg=FELT)
        timer_row.pack(fill="x", pady=(0, 6))

        tk.Label(timer_row, text="AUTO", bg=FELT, fg=DIM,
                 font=("Courier New", 8)).pack(side="left")

        self.timer_btn = tk.Label(timer_row, text="OFF", bg=FELT, fg=DIM,
                                  font=("Courier New", 8, "bold"),
                                  cursor="hand2", padx=6, pady=2,
                                  relief="flat", bd=0,
                                  highlightthickness=1,
                                  highlightbackground=BORDER)
        self.timer_btn.pack(side="left", padx=4)
        self.timer_btn.bind("<Button-1>", lambda e: self.toggle_timer())

        tk.Label(timer_row, text="every", bg=FELT, fg=DIM,
                 font=("Courier New", 8)).pack(side="left")

        self.interval_var = tk.StringVar(value="5")
        int_e = tk.Entry(timer_row, textvariable=self.interval_var, width=4,
                         bg="#0a1810", fg=CREAM, font=("Courier New", 10),
                         bd=0, insertbackground=CREAM, justify="center",
                         highlightthickness=1, highlightbackground=BORDER)
        int_e.pack(side="left", padx=4)

        tk.Label(timer_row, text="sec", bg=FELT, fg=DIM,
                 font=("Courier New", 8)).pack(side="left")

        # History strip
        self.hist_frame = tk.Frame(self, bg="#080f0c")
        self.hist_frame.pack(fill="x")
        self.hist_labels = []

    # ── GENERATE ───────────────────────────────────────
    def generate(self):
        if self._rolling:
            return
        self._rolling = True

        def _roll():
            lo = self.min_var.get().strip() or "1"
            hi = self.max_var.get().strip() or "100"
            try:
                lo, hi = int(lo), int(hi)
            except ValueError:
                lo, hi = 1, 100

            # Quick roll animation (8 frames)
            for _ in range(8):
                n = crypto_rand(lo, hi)
                self.num_label.configure(fg=DIM, text=str(n))
                time.sleep(0.05)

            final = crypto_rand(lo, hi)
            self.num_label.configure(fg=GOLD, text=str(final))
            self.after(300, lambda: self.num_label.configure(fg=CREAM))
            self._add_history(final)
            self._rolling = False

        threading.Thread(target=_roll, daemon=True).start()

    def _update_range_label(self):
        lo = self.min_var.get() or "1"
        hi = self.max_var.get() or "100"
        self.range_label.configure(text=f"range: {lo} – {hi}")

    def _add_history(self, num):
        lbl = tk.Label(self.hist_frame, text=str(num), bg="#080f0c",
                       fg=DIM, font=("Courier New", 8), padx=4, pady=2)
        lbl.pack(side="left")
        self.hist_labels.append(lbl)
        if len(self.hist_labels) > 10:
            old = self.hist_labels.pop(0)
            old.destroy()

    # ── TIMER ──────────────────────────────────────────
    def toggle_timer(self):
        if self._timer_running:
            self.stop_timer()
        else:
            self.start_timer()

    def start_timer(self):
        try:
            secs = max(1, int(self.interval_var.get()))
        except ValueError:
            secs = 5

        self._timer_running = True
        self.timer_btn.configure(text=" ON ", fg=GREEN_ON,
                                 highlightbackground=GREEN_ON)
        self.indicator.configure(fg=GREEN_ON)

        def _loop():
            self.generate()
            while self._timer_running:
                time.sleep(secs)
                if self._timer_running:
                    self.generate()

        self._timer_thread = threading.Thread(target=_loop, daemon=True)
        self._timer_thread.start()

    def stop_timer(self):
        self._timer_running = False
        self.timer_btn.configure(text="OFF", fg=DIM,
                                 highlightbackground=BORDER)
        self.indicator.configure(fg=DIM)


# ── ENTRY POINT ────────────────────────────────────────
if __name__ == "__main__":
    app = GTORNGApp()
    app.mainloop()