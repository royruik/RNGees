"""
GTO RNG Overlay — Auto-attaches to GGPoker table windows
Requires: pip install pywin32

Run: python gto_rng.py
"""

import tkinter as tk
import secrets
import threading
import time
import sys
import os
import random

try:
    import win32gui
    WIN32 = True
except ImportError:
    WIN32 = False

# ── THEME ────────────────────────────────────────────────
BG       = "#0a1a10"
FELT     = "#0d2818"
FELT_MID = "#1a4028"
GOLD     = "#c9a84c"
CREAM    = "#f0e6cc"
DIM      = "#3a5a45"
GREEN    = "#2ecc71"
RED_COL  = "#ff5555"
BORDER   = "#1e4a30"

# Reference table size — widget scales proportionally to this
REF_TABLE_W = 560
REF_TABLE_H = 415
REF_WIDGET  = 70    # widget size at reference resolution
MARGIN      = 6     # inset from table corner

def widget_size_for(tw, th):
    """Scale widget size proportionally to table size. Min 60, max 160."""
    scale = min(tw / REF_TABLE_W, th / REF_TABLE_H)
    return max(60, min(160, int(REF_WIDGET * scale)))

def font_size_for(s):
    """Large number font size relative to widget size."""
    return max(18, int(s * 0.52))

# ── COLOUR GRADIENT: green(low) → gold(mid) → red(high) ──
def number_color(val, lo, hi):
    if hi == lo:
        return GOLD
    t = max(0.0, min(1.0, (val - lo) / (hi - lo)))
    if t < 0.5:
        s = t * 2
        r = int(0x27 + (0xc9 - 0x27) * s)
        g = int(0xae + (0xa8 - 0xae) * s)
        b = int(0x60 + (0x4c - 0x60) * s)
    else:
        s = (t - 0.5) * 2
        r = int(0xc9 + (0xe7 - 0xc9) * s)
        g = int(0xa8 + (0x2d - 0xa8) * s)
        b = int(0x4c + (0x2d - 0x4c) * s)
    return f"#{r:02x}{g:02x}{b:02x}"

def crypto_rand(lo, hi):
    lo, hi = int(lo), int(hi)
    if lo > hi: lo, hi = hi, lo
    return lo + secrets.randbelow(hi - lo + 1)

# ── WINDOW DETECTION ─────────────────────────────────────
MATCH_KEYWORDS   = ["德扑", "体验场", "holdem","NL","$"]
EXCLUDE_KEYWORDS = ["chrome", "firefox", "edge", "claude",
                    "visual studio", "code", "notepad"]
MIN_W, MIN_H = 400, 300

def is_poker_table(title, w, h):
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS):
        return False
    if w < MIN_W or h < MIN_H:
        return False
    return any(kw in title for kw in MATCH_KEYWORDS)

def find_poker_windows():
    if not WIN32:
        return []
    results = []
    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return
        try:
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x2, y2 = rect
            ww, hh = x2 - x, y2 - y
            if is_poker_table(title, ww, hh):
                results.append((hwnd, title, x, y, ww, hh))
        except Exception:
            pass
    win32gui.EnumWindows(_cb, None)
    return results

def get_window_rect(hwnd):
    """Return (x, y, w, h) for a given hwnd, or None if gone."""
    if not WIN32:
        return None
    try:
        rect = win32gui.GetWindowRect(hwnd)
        x, y, x2, y2 = rect
        return x, y, x2 - x, y2 - y
    except Exception:
        return None


# ── RNG WIDGET ───────────────────────────────────────────
class RNGWidget(tk.Toplevel):
    def __init__(self, master, hwnd=None, table_title="", tw=560, th=415):
        super().__init__(master)
        self.hwnd         = hwnd          # win32 handle to track (None = manual)
        self.table_title  = table_title
        self._lo          = 1
        self._hi          = 100
        self._rolling     = False
        self._timer_running = False
        self._drag_x      = self._drag_y = 0
        self._tracking    = hwnd is not None
        self._S           = widget_size_for(tw, th)

        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.wm_attributes("-alpha", 0.93)
        self.configure(bg="#060e09")
        S = self._S
        self.geometry(f"{S}x{S}")
        self.resizable(False, False)

        self._build()
        self._build_menu()

        # Start position tracking loop if attached to a real window
        if self._tracking:
            threading.Thread(target=self._track_loop, daemon=True).start()

    # ── BUILD ─────────────────────────────────────────
    def _build(self):
        S = self._S
        self.cv = tk.Canvas(self, width=S, height=S,
                            bg="#060e09", highlightthickness=0)
        self.cv.place(x=0, y=0)

        pad = 3
        self.cv.create_rectangle(pad, pad, S-pad, S-pad,
                                  fill="#0d1f14", outline=BORDER,
                                  width=1, tags="bg_rect")

        fs = font_size_for(S)
        self.num_id = self.cv.create_text(
            S // 2, S // 2, text="?",
            fill=GOLD, font=("Courier New", fs, "bold"),
            anchor="center"
        )

        # Timer dot — top right
        self.dot_id = self.cv.create_oval(
            S-11, 4, S-4, 11, fill=DIM, outline=""
        )

        self.cv.bind("<ButtonPress-1>",   self._drag_start)
        self.cv.bind("<B1-Motion>",       self._drag_motion)
        self.cv.bind("<Double-Button-1>", lambda e: self.generate())
        self.cv.bind("<Button-3>",        self._show_menu)
        self.cv.bind("<Enter>", lambda e: self.cv.itemconfig("bg_rect", outline=GOLD))
        self.cv.bind("<Leave>", lambda e: self.cv.itemconfig("bg_rect", outline=BORDER))

    def _build_menu(self):
        m = tk.Menu(self, tearoff=0, bg=FELT_MID, fg=CREAM,
                    activebackground="#254030", activeforeground=GOLD,
                    font=("Courier New", 9), bd=0, relief="flat")
        m.add_command(label="▶  Generate",         command=self.generate)
        m.add_separator()
        m.add_command(label="⏱  Auto  3 sec",      command=lambda: self._start_timer(3))
        m.add_command(label="⏱  Auto  5 sec",      command=lambda: self._start_timer(5))
        m.add_command(label="⏱  Auto 10 sec",      command=lambda: self._start_timer(10))
        m.add_command(label="⏱  Auto 30 sec",      command=lambda: self._start_timer(30))
        m.add_command(label="⏹  Stop Timer",       command=self.stop_timer)
        m.add_separator()
        m.add_command(label="⚙  Set Range…",       command=self._range_dialog)
        m.add_separator()
        m.add_command(label="✕  Close",            command=self.destroy)
        self._menu = m

    def _show_menu(self, e):
        self._menu.tk_popup(e.x_root, e.y_root)

    # ── POSITION TRACKING ─────────────────────────────
    def _track_loop(self):
        """Follow the table window as it moves."""
        while self._tracking:
            try:
                r = get_window_rect(self.hwnd)
                if r:
                    tx, ty, tw, th = r
                    S  = widget_size_for(tw, th)
                    wx = tx + MARGIN                   # bottom-left X
                    wy = ty + th - S - MARGIN          # bottom-left Y
                    self.after(0, self._move_to, wx, wy, S)
            except Exception:
                pass
            time.sleep(0.25)   # track at 4 Hz — smooth enough, low CPU

    def _move_to(self, wx, wy, new_s):
        try:
            if new_s != self._S:
                # Table was resized — rebuild widget at new size
                self._S = new_s
                self.cv.destroy()
                self.geometry(f"{new_s}x{new_s}")
                self._build()
            self.geometry(f"+{wx}+{wy}")
        except Exception:
            pass

    # ── GENERATE ──────────────────────────────────────
    def generate(self):
        if self._rolling:
            return
        self._rolling = True
        lo, hi = self._lo, self._hi

        def _roll():
            for _ in range(7):
                self.cv.itemconfig(self.num_id,
                                   text=str(crypto_rand(lo, hi)), fill=DIM)
                time.sleep(0.045)
            final = crypto_rand(lo, hi)
            col   = number_color(final, lo, hi)
            self.cv.itemconfig(self.num_id, text=str(final), fill=col)
            self._rolling = False
            self._flash(col)

        threading.Thread(target=_roll, daemon=True).start()

    def _flash(self, color):
        self.cv.itemconfig("bg_rect", outline=color)
        self.after(400, lambda: self.cv.itemconfig("bg_rect", outline=BORDER))

    # ── TIMER ─────────────────────────────────────────
    def _start_timer(self, secs):
        self.stop_timer()
        self._timer_running = True
        self.cv.itemconfig(self.dot_id, fill=GREEN)
        def _loop():
            self.generate()
            while self._timer_running:
                time.sleep(secs)
                if self._timer_running:
                    self.generate()
        threading.Thread(target=_loop, daemon=True).start()

    def stop_timer(self):
        self._timer_running = False
        self.cv.itemconfig(self.dot_id, fill=DIM)

    # ── RANGE DIALOG ──────────────────────────────────
    def _range_dialog(self):
        S = self._S
        d = tk.Toplevel(self)
        d.configure(bg=FELT)
        d.overrideredirect(True)
        d.wm_attributes("-topmost", True)
        d.geometry(f"190x100+{self.winfo_x() + S + 4}+{self.winfo_y()}")

        tk.Label(d, text="SET RANGE", bg=FELT, fg=GOLD,
                 font=("Courier New", 9, "bold")).pack(pady=(10, 6))
        row = tk.Frame(d, bg=FELT)
        row.pack()
        lo_v = tk.StringVar(value=str(self._lo))
        hi_v = tk.StringVar(value=str(self._hi))

        def _entry(parent, var):
            return tk.Entry(parent, textvariable=var, width=5, bg=BG, fg=CREAM,
                            font=("Courier New", 10), bd=0, insertbackground=CREAM,
                            justify="center", highlightthickness=1,
                            highlightbackground=BORDER)

        tk.Label(row, text="MIN", bg=FELT, fg=DIM,
                 font=("Courier New", 8)).pack(side="left", padx=3)
        _entry(row, lo_v).pack(side="left")
        tk.Label(row, text="MAX", bg=FELT, fg=DIM,
                 font=("Courier New", 8)).pack(side="left", padx=3)
        _entry(row, hi_v).pack(side="left")

        def _apply():
            try:
                self._lo, self._hi = int(lo_v.get()), int(hi_v.get())
            except ValueError:
                pass
            d.destroy()

        tk.Button(d, text="APPLY", bg=FELT_MID, fg=GOLD,
                  font=("Courier New", 9, "bold"), bd=0, relief="flat",
                  pady=4, command=_apply).pack(fill="x", padx=14, pady=8)
        d.bind("<Return>", lambda e: _apply())
        d.bind("<Escape>", lambda e: d.destroy())

    # ── DRAG (manual widgets only) ────────────────────
    def _drag_start(self, e):
        self._tracking = False   # detach from table when manually dragged
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _drag_motion(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def destroy(self):
        self._tracking = False
        self._timer_running = False
        super().destroy()


# ── CONTROL PANEL ────────────────────────────────────────
class ControlPanel(tk.Tk):
    def __init__(self):
        super().__init__()

        # Normal OS window — taskbar icon, real minimize & close buttons
        self.title("GTO RNG")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("360x460")
        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.wm_attributes("-topmost", False)   # NOT always-on-top

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{sw//2 - 180}+{sh//2 - 230}")

        self.widgets: dict = {}
        self._manual_n    = 0
        self._scan_active = True
        self._rows: dict  = {}

        self._build()

        if WIN32:
            self._log("Scanning for GGPoker table windows…")
            self._log("Keywords: 德扑 / 体验场 / holdem")
            threading.Thread(target=self._scan_loop, daemon=True).start()
        else:
            self._log("pywin32 not found — manual mode only.")
            self._log("Install:  pip install pywin32")

    # ── UI ────────────────────────────────────────────
    def _build(self):
        hdr = tk.Frame(self, bg=FELT_MID, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="GTO  RNG", bg=FELT_MID, fg=GOLD,
                 font=("Courier New", 14, "bold"), padx=14).pack(side="left", pady=12)

        self._status_lbl = tk.Label(hdr, text="idle", bg=FELT_MID, fg=DIM,
                                    font=("Courier New", 7))
        self._status_lbl.pack(side="left")

        btn_row = tk.Frame(self, bg=BG, pady=10)
        btn_row.pack(fill="x", padx=12)

        def abtn(label, color, cmd):
            tk.Button(btn_row, text=label, bg=FELT_MID, fg=color,
                      font=("Courier New", 9, "bold"), bd=0, relief="flat",
                      cursor="hand2", padx=10, pady=7,
                      activebackground="#254030", activeforeground=GOLD,
                      command=cmd).pack(side="left", padx=3)

        abtn("+ ADD",   GOLD,  self._add_manual)
        abtn("⚡ ALL",  CREAM, self._gen_all)
        abtn("⏹ STOP", DIM,   self._stop_all)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        tk.Label(self, text="  ACTIVE WIDGETS", bg=BG, fg=DIM,
                 font=("Courier New", 8), anchor="w", pady=6).pack(fill="x")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        list_outer = tk.Frame(self, bg=BG)
        list_outer.pack(fill="both", expand=True)

        self._list_canvas = tk.Canvas(list_outer, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(list_outer, orient="vertical",
                          command=self._list_canvas.yview,
                          bg=FELT_MID, troughcolor=BG, bd=0, relief="flat")
        self._inner = tk.Frame(self._list_canvas, bg=BG)
        self._inner.bind(
            "<Configure>",
            lambda e: self._list_canvas.configure(
                scrollregion=self._list_canvas.bbox("all"))
        )
        self._list_canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._list_canvas.configure(yscrollcommand=sb.set)
        self._list_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        self._log_box = tk.Text(
            self, height=5, bg="#050d08", fg=DIM,
            font=("Courier New", 7), bd=0, state="disabled",
            padx=8, pady=6, relief="flat", insertbackground=GOLD
        )
        self._log_box.pack(fill="x")

    # ── HELPERS ───────────────────────────────────────
    def _log(self, msg):
        def _do():
            self._log_box.configure(state="normal")
            self._log_box.insert("end", f"> {msg}\n")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _do)

    def _set_status(self, msg):
        self.after(0, lambda: self._status_lbl.configure(text=msg))

    def _refresh_status(self):
        auto_n   = sum(1 for k in self.widgets if isinstance(k, int))
        manual_n = sum(1 for k in self.widgets if isinstance(k, str))
        self._set_status(f"{auto_n + manual_n} active  |  {auto_n} auto  {manual_n} manual")

    # ── WIDGET LIST ───────────────────────────────────
    def _add_row(self, key, title):
        row = tk.Frame(self._inner, bg=FELT, pady=5, padx=8)
        row.pack(fill="x", pady=2, padx=6)

        tk.Label(row, text="●", bg=FELT, fg=GREEN,
                 font=("Courier New", 8)).pack(side="left", padx=(0, 6))
        tk.Label(row, text=title[:26], bg=FELT, fg=CREAM,
                 font=("Courier New", 8), anchor="w").pack(side="left")

        def _focus():
            w = self.widgets.get(key)
            if w:
                try: w.lift(); w.deiconify()
                except: pass

        def _close_one():
            w = self.widgets.get(key)
            if w:
                try: w.destroy()
                except: pass
            self.widgets.pop(key, None)
            self._remove_row(key)
            self._refresh_status()

        tk.Button(row, text="focus", bg=BG, fg=DIM,
                  font=("Courier New", 7), bd=0, relief="flat",
                  cursor="hand2", padx=5,
                  activebackground="#254030", activeforeground=GOLD,
                  command=_focus).pack(side="right", padx=2)
        tk.Button(row, text="✕", bg=BG, fg=RED_COL,
                  font=("Courier New", 9, "bold"), bd=0, relief="flat",
                  cursor="hand2", padx=5,
                  activebackground="#3a1010", activeforeground=RED_COL,
                  command=_close_one).pack(side="right", padx=2)

        self._rows[key] = row

    def _remove_row(self, key):
        if key in self._rows:
            self._rows[key].destroy()
            del self._rows[key]

    # ── AUTO SCAN ─────────────────────────────────────
    def _scan_loop(self):
        while self._scan_active:
            try:
                found     = find_poker_windows()
                found_map = {hw: (t, x, y, w, h) for hw, t, x, y, w, h in found}

                # Remove closed tables
                gone = [k for k in list(self.widgets)
                        if isinstance(k, int) and k not in found_map]
                for k in gone:
                    try: self.widgets[k].destroy()
                    except: pass
                    self.widgets.pop(k, None)
                    self.after(0, self._remove_row, k)
                    self.after(0, self._log, "Table closed — widget removed")

                # Attach to new tables
                for hwnd, (title, tx, ty, tw, th) in found_map.items():
                    if hwnd not in self.widgets:
                        S  = widget_size_for(tw, th)
                        wx = tx + MARGIN
                        wy = ty + th - S - MARGIN      # bottom-left corner
                        w  = RNGWidget(self, hwnd=hwnd,
                                       table_title=title, tw=tw, th=th)
                        w.geometry(f"+{wx}+{wy}")
                        self.widgets[hwnd] = w
                        label = title or f"Table {hwnd}"
                        self.after(0, self._add_row, hwnd, label)
                        self.after(0, self._log, f"Attached: {label}")

                self.after(0, self._refresh_status)

            except Exception as ex:
                self.after(0, self._log, f"Scan error: {ex}")

            time.sleep(2)

    # ── MANUAL ADD ────────────────────────────────────
    def _add_manual(self):
        self._manual_n += 1
        key   = f"manual_{self._manual_n}"
        title = f"Manual {self._manual_n}"
        sw    = self.winfo_screenwidth()
        sh    = self.winfo_screenheight()
        ox    = sw // 2 + random.randint(-200, 200)
        oy    = sh // 2 + random.randint(-80, 80)
        w = RNGWidget(self, hwnd=None, table_title=title)
        w.geometry(f"+{ox}+{oy}")
        self.widgets[key] = w
        self._add_row(key, title)
        self._log(f"Added manual widget: {title}")
        self._refresh_status()

    # ── GLOBAL ACTIONS ────────────────────────────────
    def _gen_all(self):
        for w in list(self.widgets.values()):
            try: w.generate()
            except: pass
        self._log("Generated all")

    def _stop_all(self):
        for w in list(self.widgets.values()):
            try: w.stop_timer()
            except: pass
        self._log("Stopped all timers")

    def _quit(self):
        self._scan_active = False
        for w in list(self.widgets.values()):
            try: w.destroy()
            except: pass
        try: self.destroy()
        except: pass
        os._exit(0)


if __name__ == "__main__":
    if not WIN32:
        print("=" * 55)
        print("  pywin32 not found — running in MANUAL mode.")
        print("  To enable auto-detection of GGPoker tables:")
        print("    pip install pywin32")
        print("=" * 55)
    ControlPanel().mainloop()