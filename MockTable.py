"""
MockTable.py — Simulates GGPoker table for RNGees detection testing.
Window title contains "$" so RNGees auto-detects it.

Space = trigger action buttons
Escape or click any button = dismiss
Click anywhere = print screen coordinates
"""

import tkinter as tk
import threading
import time

BG      = "#1a1a1a"
TABLE   = "#2d7a2d"
GOLD    = "#c9a84c"
CREAM   = "#f0e6cc"
DIM     = "#555555"
RED_BTN = "#c0392b"
RED_HOV = "#e74c3c"

class MockTable(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GGPoker $ - Table 1")
        self.configure(bg=BG)
        self.geometry("900x600")
        self.resizable(True, True)
        self.minsize(600, 400)
        self._action_visible = False
        self._auto_interval  = 6
        self._auto_running   = True
        self._build()
        threading.Thread(target=self._auto_cycle, daemon=True).start()

    def _build(self):
        # ── TOP BAR ──────────────────────────────────────────
        top = tk.Frame(self, bg="#222222", height=36)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)
        tk.Label(top, text="GGPoker $  ·  体验场德扑  ·  100/200",
                 bg="#222222", fg=CREAM, font=("Arial", 9), padx=12).pack(side="left", pady=8)
        tk.Label(top, text="auto every", bg="#222222", fg=DIM,
                 font=("Arial", 8)).pack(side="right", padx=(0,4), pady=8)
        self._iv = tk.StringVar(value="6")
        e = tk.Entry(top, textvariable=self._iv, width=3, bg=BG, fg=CREAM,
                     font=("Arial", 9), bd=0, justify="center",
                     insertbackground=CREAM, highlightthickness=1,
                     highlightbackground="#333333")
        e.pack(side="right", pady=8)
        e.bind("<Return>",   lambda ev: self._update_interval())
        e.bind("<FocusOut>", lambda ev: self._update_interval())
        tk.Label(top, text="s  |", bg="#222222", fg=DIM,
                 font=("Arial", 8)).pack(side="right", padx=(0,8))

        # ── MAIN CANVAS ──────────────────────────────────────
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", self._on_resize)

        self._canvas.create_oval(80, 40, 820, 420,
                                 fill=TABLE, outline="#1a5c1a", width=4, tags="felt")
        self._canvas.create_text(450, 220, text="GG POKER.CA",
                                 fill="#2a8a2a", font=("Arial", 22, "bold"), tags="wm")
        self._status_id = self._canvas.create_text(
            450, 150, text="Waiting…", fill=DIM, font=("Arial", 11), tags="status")
        self._deal_btn = tk.Button(
            self._canvas, text="▶  DEAL  (Space)",
            bg="#333333", fg=GOLD, font=("Arial", 10, "bold"),
            bd=0, relief="flat", cursor="hand2", padx=14, pady=7,
            activebackground="#444444", command=self._trigger_action)
        self._canvas.create_window(450, 280, window=self._deal_btn, tags="deal_btn")

        # ── ACTION BUTTONS — canvas windows, anchor SE ───────
        self._btn_frame = tk.Frame(self._canvas, bg=BG)
        for text, col in [("让牌/弃牌  Fold", 0), ("让牌  Call", 1), ("加注至  Raise", 2)]:
            b = tk.Button(self._btn_frame, text=text,
                          bg=RED_BTN, fg="white",
                          font=("Arial", 11, "bold"), bd=0, relief="flat",
                          cursor="hand2", padx=18, pady=10,
                          activebackground=RED_HOV, activeforeground="white",
                          command=self._resolve_action)
            b.grid(row=0, column=col, padx=4, pady=6)
            b.bind("<Button-1>", self._print_coords)
        self._btn_win = None   # canvas window item, created on trigger

        # ── DETECTION REGION HIGHLIGHT ───────────────────────
        self._region_rect  = self._canvas.create_rectangle(
            0, 0, 1, 1, outline="#ff0000", width=2, dash=(4,3), tags="region")
        self._region_label = self._canvas.create_text(
            0, 0, text="detection region",
            fill="#ff0000", font=("Arial", 7), anchor="se", tags="region_lbl")

        # ── BINDINGS ─────────────────────────────────────────
        self.bind("<space>",  lambda e: self._trigger_action())
        self.bind("<Escape>", lambda e: self._resolve_action())
        self._canvas.bind("<Button-1>", self._print_coords)

    def _on_resize(self, e):
        w, h = e.width, e.height
        self._canvas.coords("wm",       w//2, h//2 - 20)
        self._canvas.coords("status",   w//2, h//2 - 80)
        self._canvas.coords("deal_btn", w//2, h//2 + 20)
        # Reposition buttons if visible
        if self._btn_win:
            self._canvas.coords(self._btn_win, w, h)
        # Detection region — matches RNGees ACTION_X=0.45, Y1=0.85, Y2=1.00
        # RNGees works on full GetWindowRect (topbar+canvas)
        # canvas_h = total_h - TOPBAR(36), so convert:
        TOP = 36
        total_h = h + TOP
        rx1  = int(w * 0.45)
        ry1  = int(total_h * 0.85) - TOP   # in canvas coords
        ry2  = h                             # canvas bottom = GetWindowRect bottom
        self._canvas.coords(self._region_rect,  rx1, ry1, w, ry2)
        self._canvas.coords(self._region_label, w - 2, ry1 - 2)

    def _trigger_action(self):
        if self._action_visible:
            return
        self._action_visible = True
        self._canvas.itemconfig("status", text="Your action!", fill=GOLD)
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if self._btn_win:
            self._canvas.delete(self._btn_win)
        self._btn_win = self._canvas.create_window(
            w, h, window=self._btn_frame, anchor="se")
        self._canvas.lift(self._btn_win)

    def _resolve_action(self):
        if not self._action_visible:
            return
        self._action_visible = False
        self._canvas.itemconfig("status", text="Waiting…", fill=DIM)
        if self._btn_win:
            self._canvas.delete(self._btn_win)
            self._btn_win = None

    def _print_coords(self, e):
        print(f"[CLICK] screen=({e.x_root},{e.y_root}) | "
              f"win=({self.winfo_x()},{self.winfo_y()}) "
              f"size=({self.winfo_width()}x{self.winfo_height()})")

    def _auto_cycle(self):
        while self._auto_running:
            time.sleep(self._auto_interval)
            if not self._action_visible:
                self.after(0, self._trigger_action)
                time.sleep(4)
                self.after(0, self._resolve_action)

    def _update_interval(self):
        try:
            self._auto_interval = max(1, int(self._iv.get()))
        except ValueError:
            pass

if __name__ == "__main__":
    MockTable().mainloop()