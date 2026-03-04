"""
RNGees Overlay — Auto-attaches to Online Poker table windows
Requires: pip install pywin32

Run: python RNGees.py
"""

import tkinter as tk
import secrets
import threading
import time
import os
import random
import ctypes

try:
    import win32gui
    WIN32 = True
except ImportError:
    WIN32 = False

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

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

REF_TABLE_W = 560
REF_TABLE_H = 415
REF_WIDGET  = 60
MARGIN      = 6

def widget_size_for(tw, th):
    scale = min(tw / REF_TABLE_W, th / REF_TABLE_H)
    return max(56, min(160, int(REF_WIDGET * scale)))

def font_size_for(s):
    return max(14, int(s * 0.42))

# ── COLOUR GRADIENT ──────────────────────────────────────
def number_color(val, lo, hi, invert=False):
    # default (invert=False): red(low) → gold(mid) → green(high)
    # invert=True:            green(low) → gold(mid) → red(high)
    if hi == lo:
        return GOLD
    t = max(0.0, min(1.0, (val - lo) / (hi - lo)))
    if invert:
        t = 1.0 - t
    if t < 0.5:
        s = t * 2
        # red → gold
        r = int(0xe7 + (0xc9 - 0xe7) * s)
        g = int(0x2d + (0xa8 - 0x2d) * s)
        b = int(0x2d + (0x4c - 0x2d) * s)
    else:
        s = (t - 0.5) * 2
        # gold → green
        r = int(0xc9 + (0x27 - 0xc9) * s)
        g = int(0xa8 + (0xae - 0xa8) * s)
        b = int(0x4c + (0x60 - 0x4c) * s)
    return f"#{r:02x}{g:02x}{b:02x}"

def crypto_rand(lo, hi):
    lo, hi = int(lo), int(hi)
    if lo > hi: lo, hi = hi, lo
    return lo + secrets.randbelow(hi - lo + 1)

# ── WINDOW DETECTION ─────────────────────────────────────
MATCH_KEYWORDS   = ["德扑", "holdem", "NL", "$"]
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
    def __init__(self, master, hwnd=None, table_title="", tw=560, th=415,
                 invert_gradient=False):
        super().__init__(master)
        self.hwnd           = hwnd
        self.table_title    = table_title
        self._lo            = 1
        self._hi            = 100
        self._rolling       = False
        self._timer_running = False
        self._timer_gen    = 0  # increments on each new timer to invalidate old threads
        self._tracking      = hwnd is not None
        self._S             = widget_size_for(tw, th)
        self._invert        = invert_gradient

        # Offset from table's bottom-left corner (in pixels).
        # User can drag to reposition; offset is preserved across table moves.
        self._off_x = self._S + MARGIN                # default: one widget width from left
        self._off_y = -(self._S + MARGIN)             # negative = up from bottom
        self._drag_moved   = False
        self._drag_start_x = self._drag_start_y = 0
        self._dragging     = False  # pause tracking while user is dragging
        self._resizing     = False
        self._resize_start_x = self._resize_start_y = 0
        self._resize_start_s = 0

        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.wm_attributes("-alpha", 0.93)
        self.configure(bg="#060e09")
        self.geometry(f"{self._S}x{self._S}")
        self.resizable(False, False)

        self._build()

        # Generate immediately on spawn — no "?" mark
        self.after(100, self.generate)

        if self._tracking:
            threading.Thread(target=self._track_loop, daemon=True).start()

    def _defocus_entries(self, event):
        """If click target is not an Entry, move focus to the window so
        any active entry loses focus, triggers FocusOut → applies settings."""
        if not isinstance(event.widget, tk.Entry):
            self.focus()

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
            S // 2, S // 2, text="",
            fill=GOLD, font=("Courier New", fs, "bold"),
            anchor="center"
        )
        self.dot_id = self.cv.create_oval(
            S-11, 4, S-4, 11, fill=DIM, outline=""
        )

        self.cv.bind("<Enter>", lambda e: self.cv.itemconfig("bg_rect", outline=GOLD))
        self.cv.bind("<Leave>", lambda e: self.cv.itemconfig("bg_rect", outline=BORDER))

        if self.hwnd:
            # Tracked widget: normal drag + click
            self.cv.bind("<ButtonPress-1>",   self._on_press)
            self.cv.bind("<B1-Motion>",       self._on_drag)
            self.cv.bind("<ButtonRelease-1>", self._on_release)
        else:
            # Manual widget: edge-aware resize + drag
            self.cv.bind("<Motion>",          self._resize_cursor)
            self.cv.bind("<ButtonPress-1>",   self._smart_press)
            self.cv.bind("<B1-Motion>",       self._smart_motion)
            self.cv.bind("<ButtonRelease-1>", self._smart_release)
            self.cv.bind("<Leave>",           lambda e: (
                self.cv.itemconfig("bg_rect", outline=BORDER),
                self.cv.configure(cursor="")))

    EDGE = 8  # px from edge that counts as resize zone

    def _get_edge(self, x, y):
        """Return which edge/corner the cursor is on, or None."""
        S = self._S
        E = self.EDGE
        on_r = x >= S - E
        on_b = y >= S - E
        on_l = x <= E
        on_t = y <= E
        if on_r and on_b: return "se"
        if on_l and on_b: return "sw"
        if on_r and on_t: return "ne"
        if on_l and on_t: return "nw"
        if on_r:          return "e"
        if on_l:          return "w"
        if on_b:          return "s"
        if on_t:          return "n"
        return None

    _CURSORS = {
        "n": "top_side", "s": "bottom_side",
        "e": "right_side", "w": "left_side",
        "ne": "top_right_corner", "nw": "top_left_corner",
        "se": "bottom_right_corner", "sw": "bottom_left_corner",
    }

    def _resize_cursor(self, e):
        edge = self._get_edge(e.x, e.y)
        self.cv.configure(cursor=self._CURSORS.get(edge, ""))

    def _smart_press(self, e):
        self._edge = self._get_edge(e.x, e.y)
        if self._edge:
            self._resizing       = True
            self._resize_start_x = e.x_root
            self._resize_start_y = e.y_root
            self._resize_start_s = self._S
            self._resize_win_x   = self.winfo_x()
            self._resize_win_y   = self.winfo_y()
        else:
            self._resizing     = False
            self._drag_moved   = False
            self._drag_start_x = e.x_root
            self._drag_start_y = e.y_root
            self._drag_win_x   = self.winfo_x()
            self._drag_win_y   = self.winfo_y()
            self._dragging     = False  # only set True once motion starts

    def _smart_motion(self, e):
        if not self._resizing and not self._edge:
            self._dragging   = True
            self._drag_moved = True
        if self._resizing:
            dx = e.x_root - self._resize_start_x
            dy = e.y_root - self._resize_start_y
            edge = self._edge
            s0   = self._resize_start_s
            # Determine new size and new top-left based on edge
            if edge in ("e", "se", "ne"):   delta = dx
            elif edge in ("w", "sw", "nw"): delta = -dx
            elif edge == "s":               delta = dy
            elif edge == "n":               delta = -dy
            else:                           delta = max(dx, dy)
            new_s = max(40, min(200, s0 + delta))
            # Adjust position for edges that move the top-left
            nx, ny = self._resize_win_x, self._resize_win_y
            if edge in ("w", "sw", "nw"):
                nx = self._resize_win_x + (s0 - new_s)
            if edge in ("n", "ne", "nw"):
                ny = self._resize_win_y + (s0 - new_s)
            self._apply_size(new_s)
            self.geometry(f"{new_s}x{new_s}+{nx}+{ny}")
        elif self._dragging:
            dx = e.x_root - self._drag_start_x
            dy = e.y_root - self._drag_start_y
            self._drag_moved = True
            self.geometry(f"+{self._drag_win_x + dx}+{self._drag_win_y + dy}")

    def _smart_release(self, e):
        self._resizing = False
        self._dragging = False
        if not self._drag_moved and not self._edge:
            # Pure click on center — generate
            self.generate()
        self._edge = None

    def _apply_size(self, new_s):
        """Resize the widget canvas in place."""
        self._S = new_s
        pad = 3
        fs  = font_size_for(new_s)
        self.cv.configure(width=new_s, height=new_s)
        self.cv.coords("bg_rect", pad, pad, new_s-pad, new_s-pad)
        self.cv.coords(self.num_id, new_s//2, new_s//2)
        self.cv.itemconfig(self.num_id, font=("Courier New", fs, "bold"))
        self.cv.coords(self.dot_id, new_s-11, 4, new_s-4, 11)

    # ── TRACKING ──────────────────────────────────────
    def _track_loop(self):
        """Every 250 ms: reposition widget relative to table using stored offset."""
        while self._tracking:
            try:
                if not self._dragging:
                    r = get_window_rect(self.hwnd)
                    if r:
                        tx, ty, tw, th = r
                        new_s = widget_size_for(tw, th)
                        wx = tx + self._off_x
                        wy = ty + th + self._off_y
                        self.after(0, self._move_to, wx, wy, new_s)
            except Exception:
                pass
            time.sleep(0.25)

    def _move_to(self, wx, wy, new_s):
        try:
            if new_s != self._S:
                ratio = new_s / self._S
                self._off_x = int(self._off_x * ratio)
                self._off_y = int(self._off_y * ratio)
                self._S = new_s

                # Resize in place — never destroy canvas so timer threads
                # keep their cv/num_id/dot_id references valid
                pad = 3
                fs  = font_size_for(new_s)
                self.geometry(f"{new_s}x{new_s}")
                self.cv.configure(width=new_s, height=new_s)
                self.cv.coords("bg_rect", pad, pad, new_s-pad, new_s-pad)
                self.cv.coords(self.num_id, new_s//2, new_s//2)
                self.cv.itemconfig(self.num_id,
                                   font=("Courier New", fs, "bold"))
                self.cv.coords(self.dot_id,
                               new_s-11, 4, new_s-4, 11)

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
            col   = number_color(final, lo, hi, invert=self._invert)
            self.cv.itemconfig(self.num_id, text=str(final), fill=col)
            self._rolling = False
            self._flash(col)

        threading.Thread(target=_roll, daemon=True).start()

    def _flash(self, color):
        self.cv.itemconfig("bg_rect", outline=color)
        self.after(400, lambda: self.cv.itemconfig("bg_rect", outline=BORDER))

    # ── TIMER ─────────────────────────────────────────
    def _start_timer(self, secs):
        self._timer_gen += 1          # invalidate any running old threads
        my_gen = self._timer_gen
        self._timer_running = True
        try: self.cv.itemconfig(self.dot_id, fill=GREEN)
        except: pass
        def _loop2():
            self.generate()
            elapsed = 0.0
            while self._timer_running and self._timer_gen == my_gen:
                time.sleep(0.1)
                elapsed += 0.1
                if elapsed >= secs:
                    if self._timer_running and self._timer_gen == my_gen:
                        self.generate()
                    elapsed = 0.0
        threading.Thread(target=_loop2, daemon=True).start()

    def stop_timer(self):
        self._timer_gen += 1        # invalidate any running timer thread immediately
        self._timer_running = False
        try:
            self.cv.itemconfig(self.dot_id, fill=DIM)
        except Exception:
            pass

    # ── DRAG — updates offset, tracking stays active ──
    def _on_press(self, e):
        self._drag_moved   = False
        self._drag_start_x = e.x_root
        self._drag_start_y = e.y_root
        self._drag_win_x   = self.winfo_x()
        self._drag_win_y   = self.winfo_y()
        self._dragging     = True

    def _clamp_to_table(self, wx, wy):
        """Clamp widget position so it stays fully inside the table bounds."""
        if not self.hwnd:
            return wx, wy
        r = get_window_rect(self.hwnd)
        if not r:
            return wx, wy
        tx, ty, tw, th = r
        S = self._S
        wx = max(tx, min(wx, tx + tw - S))
        wy = max(ty, min(wy, ty + th - S))
        return wx, wy

    def _on_drag(self, e):
        self._drag_moved = True
        dx = e.x_root - self._drag_start_x
        dy = e.y_root - self._drag_start_y
        wx, wy = self._clamp_to_table(
            self._drag_win_x + dx,
            self._drag_win_y + dy
        )
        self.geometry(f"+{wx}+{wy}")

    def _on_release(self, e):
        self._dragging = False
        if not self._drag_moved:
            self.generate()
        else:
            if self.hwnd:
                r = get_window_rect(self.hwnd)
                if r:
                    tx, ty, tw, th = r
                    # Store clamped offset
                    wx, wy = self._clamp_to_table(self.winfo_x(), self.winfo_y())
                    self._off_x = wx - tx
                    self._off_y = wy - (ty + th)

    def destroy(self):
        self._tracking      = False
        self._timer_running = False
        self._timer_gen += 1
        super().destroy()

    def update_settings(self, invert):
        self._invert = invert


# ── CONTROL PANEL ────────────────────────────────────────
class ControlPanel(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("RNGees")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("320x420")
        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.wm_attributes("-topmost", False)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{sw//2 - 160}+{sh//2 - 210}")

        self.widgets: dict    = {}
        self._manual_n        = 0
        self._scan_active     = True
        self._rows: dict      = {}
        self._drawer_open     = False

        self._invert_gradient = tk.BooleanVar(value=False)
        self._lo_var          = tk.StringVar(value="1")
        self._hi_var          = tk.StringVar(value="100")
        self._interval_var    = tk.StringVar(value="0")
        self._hotkey_var      = tk.StringVar(value="v")
        self._hotkey_bound    = None

        self._build()
        self._bind_hotkey()
        # Clicking anywhere outside an entry defocuses it (hides cursor + applies)
        self.bind_all("<Button-1>", self._defocus_entries, add="+")

        if not HAS_KEYBOARD:
            self._log("pip install keyboard  → for global hotkey")
        if WIN32:
            self._log("Scanning for poker tables…")
            threading.Thread(target=self._scan_loop, daemon=True).start()
        else:
            self._log("pywin32 not found — manual mode only.")
            self._log("Install:  pip install pywin32")

    def _defocus_entries(self, event):
        """If click target is not an Entry, move focus to the window so
        any active entry loses focus, triggers FocusOut → applies settings."""
        if not isinstance(event.widget, tk.Entry):
            self.focus()

    # ── BUILD ─────────────────────────────────────────
    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=FELT_MID, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="RNGees", bg=FELT_MID, fg=GOLD,
                 font=("Courier New", 14, "bold"), padx=14).pack(side="left", pady=12)
        self._status_lbl = tk.Label(hdr, text="idle", bg=FELT_MID, fg=DIM,
                                    font=("Courier New", 7))
        self._status_lbl.pack(side="left")

        # ── BUTTONS + SETTINGS DRAWER ────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        btn_row = tk.Frame(self, bg=BG, pady=8)
        btn_row.pack(fill="x", padx=12)

        tk.Button(btn_row, text="+ ADD", bg=FELT_MID, fg=GOLD,
                  font=("Courier New", 9, "bold"), bd=0, relief="flat",
                  cursor="hand2", padx=10, pady=7,
                  activebackground="#254030", activeforeground=GOLD,
                  command=self._add_manual).pack(side="left", padx=3)

        self._drawer_arrow = tk.Button(btn_row, text="⚙ SETTINGS",
                                       bg=FELT_MID, fg=DIM,
                                       font=("Courier New", 9, "bold"),
                                       bd=0, relief="flat", cursor="hand2",
                                       padx=10, pady=7,
                                       activebackground="#254030",
                                       activeforeground=GOLD,
                                       command=self._toggle_drawer)
        self._drawer_arrow.pack(side="left", padx=3)

        # Drawer body (hidden by default)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        self._drawer_body = tk.Frame(self, bg=BG)
        self._build_drawer(self._drawer_body)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── WIDGET LIST ───────────────────────────────
        tk.Label(self, text="  ACTIVE WIDGETS", bg=BG, fg=DIM,
                 font=("Courier New", 8), anchor="w", pady=4).pack(fill="x")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        list_outer = tk.Frame(self, bg=BG)
        list_outer.pack(fill="both", expand=True)

        self._list_canvas = tk.Canvas(list_outer, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(list_outer, orient="vertical",
                          command=self._list_canvas.yview,
                          bg=FELT_MID, troughcolor=BG, bd=0, relief="flat")
        self._inner = tk.Frame(self._list_canvas, bg=BG)
        self._inner.bind("<Configure>",
                         lambda e: self._list_canvas.configure(
                             scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._list_canvas.configure(yscrollcommand=sb.set)
        self._list_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Log
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        self._log_box = tk.Text(self, height=4, bg="#050d08", fg=DIM,
                                font=("Courier New", 7), bd=0, state="disabled",
                                padx=8, pady=6, relief="flat",
                                insertbackground=GOLD)
        self._log_box.pack(fill="x")

    def _build_drawer(self, parent):
        """Build the settings fields inside the drawer frame."""
        sf = tk.Frame(parent, bg=BG, padx=16, pady=6)
        sf.pack(fill="x")

        def entry_row(label, var, suffix="", on_change=None):
            row = tk.Frame(sf, bg=BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=BG, fg=CREAM,
                     font=("Courier New", 9), width=10, anchor="w").pack(side="left")
            e = tk.Entry(row, textvariable=var, width=5, bg=FELT_MID, fg=CREAM,
                         font=("Courier New", 9), bd=0, insertbackground=CREAM,
                         justify="center", highlightthickness=1,
                         highlightbackground=BORDER)
            e.pack(side="left")
            cmd = on_change or self._apply_settings
            e.bind("<FocusOut>", lambda ev: cmd())
            e.bind("<Return>",   lambda ev: cmd())
            if suffix:
                tk.Label(row, text=f" {suffix}", bg=BG, fg=DIM,
                         font=("Courier New", 9)).pack(side="left")

        # Range: two entries on same row
        rng_row = tk.Frame(sf, bg=BG)
        rng_row.pack(fill="x", pady=2)
        tk.Label(rng_row, text="Range", bg=BG, fg=CREAM,
                 font=("Courier New", 9), width=10, anchor="w").pack(side="left")
        for var, sep in [(self._lo_var, " - "), (self._hi_var, "")]:
            e = tk.Entry(rng_row, textvariable=var, width=5, bg=FELT_MID, fg=CREAM,
                         font=("Courier New", 9), bd=0, insertbackground=CREAM,
                         justify="center", highlightthickness=1,
                         highlightbackground=BORDER)
            e.pack(side="left")
            e.bind("<FocusOut>", lambda ev: self._apply_settings())
            e.bind("<Return>",   lambda ev: self._apply_settings())
            if sep:
                tk.Label(rng_row, text=sep, bg=BG, fg=DIM,
                         font=("Courier New", 9)).pack(side="left")

        entry_row("Interval", self._interval_var, "seconds")
        entry_row("Hotkey",   self._hotkey_var,   on_change=self._bind_hotkey)

        # Checkboxes
        chk_f = tk.Frame(sf, bg=BG)
        chk_f.pack(fill="x", pady=(4, 0))

        def chk(text, var, cmd=None):
            tk.Checkbutton(chk_f, text=text, variable=var,
                           bg=BG, fg=CREAM, selectcolor=FELT_MID,
                           activebackground=BG, activeforeground=GOLD,
                           font=("Courier New", 8), bd=0,
                           command=cmd).pack(anchor="w", pady=1)

        chk("Invert gradient", self._invert_gradient, self._push_settings)

    def _toggle_drawer(self):
        self._drawer_open = not self._drawer_open
        if self._drawer_open:
            self._drawer_body.pack(fill="x")
            self._drawer_arrow.configure(text="⚙ SETTINGS ▼", fg=GOLD)
            self.geometry("320x580")
        else:
            self._drawer_body.pack_forget()
            self._drawer_arrow.configure(text="⚙ SETTINGS", fg=DIM)
            self.geometry("320x420")

    # ── SETTINGS ──────────────────────────────────────
    def _apply_settings(self):
        try:
            lo = int(self._lo_var.get())
            hi = int(self._hi_var.get())
        except ValueError:
            return
        try:
            interval = int(self._interval_var.get())
        except ValueError:
            interval = 0
        for w in list(self.widgets.values()):
            try:
                w._lo = lo
                w._hi = hi
                if interval > 0:
                    w._start_timer(interval)
                else:
                    w.stop_timer()
            except Exception:
                pass

    def _push_settings(self):
        inv = self._invert_gradient.get()
        for w in list(self.widgets.values()):
            try: w.update_settings(inv)
            except: pass

    # ── HOTKEY ────────────────────────────────────────
    def _bind_hotkey(self):
        key = self._hotkey_var.get().strip().lower()
        if not key:
            return

        # Unbind previous
        if HAS_KEYBOARD and self._hotkey_bound:
            try: keyboard.remove_hotkey(self._hotkey_bound)
            except Exception: pass
        elif self._hotkey_bound:
            try: self.unbind_all(f"<Key-{self._hotkey_bound}>")
            except Exception: pass

        self._hotkey_bound = key

        if HAS_KEYBOARD:
            # Global hotkey — fires even when another window is focused
            keyboard.add_hotkey(key, lambda: self.after(0, self._on_hotkey))
            self._log(f"Hotkey: '{key}' (global)")
        else:
            # Fallback: tkinter-only (requires panel focus)
            self.bind_all(f"<Key-{key}>", self._on_hotkey)
            self._log(f"Hotkey: '{key}' (install keyboard lib for global)")

    def _on_hotkey(self, event=None):
        self._apply_settings()
        self._gen_all()

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

        # X button only for manual widgets — auto-detected tables
        # are removed automatically when the table closes
        is_manual = isinstance(key, str)
        if is_manual:
            def _close_one():
                w = self.widgets.get(key)
                if w:
                    try: w.destroy()
                    except: pass
                self.widgets.pop(key, None)
                self._remove_row(key)
                self._refresh_status()

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

                gone = [k for k in list(self.widgets)
                        if isinstance(k, int) and k not in found_map]
                for k in gone:
                    try: self.widgets[k].destroy()
                    except: pass
                    self.widgets.pop(k, None)
                    self.after(0, self._remove_row, k)
                    self.after(0, self._log, "Table closed — widget removed")

                for hwnd, (title, tx, ty, tw, th) in found_map.items():
                    if hwnd not in self.widgets:
                        S  = widget_size_for(tw, th)
                        wx = tx + MARGIN
                        wy = ty + th - S - MARGIN
                        w  = RNGWidget(self, hwnd=hwnd,
                                       table_title=title, tw=tw, th=th,
                                       invert_gradient=self._invert_gradient.get())
                        w.geometry(f"+{wx}+{wy}")
                        # Apply current settings
                        try:
                            w._lo = int(self._lo_var.get())
                            w._hi = int(self._hi_var.get())
                            iv = int(self._interval_var.get())
                            if iv > 0:
                                w._start_timer(iv)
                        except Exception:
                            pass
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
        w = RNGWidget(self, hwnd=None, table_title=title,
                      invert_gradient=self._invert_gradient.get())
        w.geometry(f"+{ox}+{oy}")
        self.widgets[key] = w
        self._add_row(key, title)
        self._log(f"Added: {title}")
        self._refresh_status()

    def _gen_all(self):
        for w in list(self.widgets.values()):
            try: w.generate()
            except: pass

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
        print("  pip install pywin32  for auto-detection.")
        print("=" * 55)
    ControlPanel().mainloop()