"""
MockTable.py — Simulates GGPoker table action prompt for RNGees detection testing.
Window title contains "$" so RNGees auto-detects it.

Matches GGPoker layout:
 - Dark table background
 - Action buttons appear bottom-right: Fold / Call / Raise (red buttons)
 - No buttons when waiting

Press Space or click DEAL to trigger action. Click any action button to dismiss.
Auto-cycles every N seconds.
"""

import tkinter as tk
import threading
import time

BG       = "#1a1a1a"
TABLE    = "#2d7a2d"
DARK     = "#111111"
GOLD     = "#c9a84c"
CREAM    = "#f0e6cc"
DIM      = "#555555"
RED_BTN  = "#c0392b"   # matches GGPoker action button red
RED_HOV  = "#e74c3c"
BORDER   = "#333333"

class MockTable(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GGPoker $ - Table 1")
        self.configure(bg=DARK)
        self.geometry("900x600")
        self.resizable(True, True)
        self.minsize(600, 400)

        self._action_visible = False
        self._auto_running   = True
        self._auto_interval  = 6

        self._build()
        threading.Thread(target=self._auto_cycle, daemon=True).start()

    def _build(self):
        # ── TOP BAR ──────────────────────────────────────
        top = tk.Frame(self, bg="#222222", height=36)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="GGPoker $  ·  体验场德扑  ·  100/200",
                 bg="#222222", fg=CREAM,
                 font=("Arial", 9), padx=12).pack(side="left", pady=8)

        tk.Label(top, text="auto every", bg="#222222", fg=DIM,
                 font=("Arial", 8)).pack(side="right", padx=(0, 4), pady=8)
        self._iv = tk.StringVar(value="6")
        e = tk.Entry(top, textvariable=self._iv, width=3,
                     bg=DARK, fg=CREAM, font=("Arial", 9),
                     bd=0, justify="center", insertbackground=CREAM,
                     highlightthickness=1, highlightbackground=BORDER)
        e.pack(side="right", pady=8)
        e.bind("<Return>",   lambda ev: self._update_interval())
        e.bind("<FocusOut>", lambda ev: self._update_interval())
        tk.Label(top, text="s  |", bg="#222222", fg=DIM,
                 font=("Arial", 8)).pack(side="right", padx=(0, 8))

        # ── TABLE CANVAS ─────────────────────────────────
        self._canvas = tk.Canvas(self, bg=DARK, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", self._on_resize)

        # Draw felt table oval
        self._canvas.create_oval(80, 60, 820, 440,
                                  fill=TABLE, outline="#1a5c1a", width=4,
                                  tags="felt")

        # GGPoker watermark
        self._canvas.create_text(450, 250, text="GG POKER.CA",
                                  fill="#2a8a2a", font=("Arial", 22, "bold"),
                                  tags="wm")

        # Status text
        self._status_id = self._canvas.create_text(
            450, 180, text="Waiting…",
            fill=DIM, font=("Arial", 11), tags="status"
        )

        # Deal button
        self._deal_btn = tk.Button(self._canvas, text="▶  DEAL  (Space)",
                                    bg="#333333", fg=GOLD,
                                    font=("Arial", 10, "bold"),
                                    bd=0, relief="flat", cursor="hand2",
                                    padx=14, pady=7,
                                    activebackground="#444444",
                                    command=self._trigger_action)
        self._canvas.create_window(450, 300, window=self._deal_btn, tags="deal_btn")

        # ── ACTION BUTTONS (hidden until action) ─────────
        self._btn_frame = tk.Frame(self._canvas, bg=DARK)

        def make_btn(text, col):
            b = tk.Button(self._btn_frame, text=text,
                          bg=RED_BTN, fg="white",
                          font=("Arial", 11, "bold"),
                          bd=0, relief="flat", cursor="hand2",
                          padx=18, pady=10,
                          activebackground=RED_HOV, activeforeground="white",
                          command=self._resolve_action)
            b.grid(row=0, column=col, padx=5, pady=8)

        make_btn("让牌/弃牌  Fold", 0)
        make_btn("让牌  Call",      1)
        make_btn("加注至  Raise",   2)

        self._action_win = None   # canvas window item for btn_frame

        # Keyboard
        self.bind("<space>", lambda e: self._trigger_action())
        self.bind("<Escape>", lambda e: self._resolve_action())

    def _on_resize(self, e):
        """Reposition elements on resize."""
        w, h = e.width, e.height
        self._canvas.coords("wm",     w//2, h//2 - 20)
        self._canvas.coords("status", w//2, h//2 - 80)
        self._canvas.coords("deal_btn", w//2, h//2 + 20)
        if self._action_win:
            self._canvas.coords(self._action_win, w - 10, h - 10)

    def _trigger_action(self):
        if self._action_visible:
            return
        self._action_visible = True
        self._canvas.itemconfig("status", text="Your action!", fill=GOLD)

        # Place action buttons anchored to bottom-right
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if self._action_win:
            self._canvas.delete(self._action_win)
        self._action_win = self._canvas.create_window(
            w - 10, h - 10,
            window=self._btn_frame,
            anchor="se",
            tags="action_win"
        )
        self._btn_frame.lift()

    def _resolve_action(self):
        if not self._action_visible:
            return
        self._action_visible = False
        self._canvas.itemconfig("status", text="Waiting…", fill=DIM)
        if self._action_win:
            self._canvas.delete(self._action_win)
            self._action_win = None

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