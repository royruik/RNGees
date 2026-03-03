"""
GTO RNG — Window Detection Diagnostic
Run this WHILE GGPoker is open to see what windows are detected.

Run: python detect_windows.py
"""

try:
    import win32gui
    WIN32 = True
except ImportError:
    WIN32 = False
    print("ERROR: pywin32 not installed.")
    print("Run:  pip install pywin32")
    input("Press Enter to exit...")
    exit()

print("=" * 60)
print("  GTO RNG — Window Detection Diagnostic")
print("=" * 60)
print()
print("Scanning ALL visible windows on your screen...")
print()

all_windows = []

def _cb(hwnd, _):
    if not win32gui.IsWindowVisible(hwnd):
        return
    title = win32gui.GetWindowText(hwnd).strip()
    if not title:
        return
    try:
        rect = win32gui.GetWindowRect(hwnd)
        x, y, x2, y2 = rect
        w, h = x2 - x, y2 - y
        if w > 100 and h > 50:
            all_windows.append((hwnd, title, x, y, w, h))
    except:
        pass

win32gui.EnumWindows(_cb, None)

# ── Print ALL visible windows ──
print(f"{'HWND':<12} {'SIZE':<16} {'TITLE'}")
print("-" * 60)
for hwnd, title, x, y, w, h in sorted(all_windows, key=lambda r: r[2]):
    size = f"{w}x{h}"
    print(f"{hwnd:<12} {size:<16} {title[:40]}")

print()
print("=" * 60)
print()

# ── Now test GGPoker-specific keywords ──
KEYWORDS = ["ggpoker", "gg poker", "bust the bonus", "holdem", "poker"]

print("Windows matching GGPoker keywords:")
print()
matched = []
for hwnd, title, x, y, w, h in all_windows:
    t = title.lower()
    for kw in KEYWORDS:
        if kw in t:
            matched.append((hwnd, title, x, y, w, h, kw))
            break

if matched:
    for hwnd, title, x, y, w, h, kw in matched:
        print(f"  ✓ [{kw}]  '{title}'")
        print(f"      position: ({x}, {y})   size: {w}x{h}")
        print(f"      widget would go to: ({x + w - 90 - 6}, {y + 6})")
        print()
else:
    print("  ✗ No GGPoker windows found.")
    print()
    print("  Possible fixes:")
    print("  1. Make sure GGPoker tables are open and visible")
    print("  2. Check the full window list above and tell me")
    print("     which title your tables show — I'll add it as")
    print("     a keyword.")

print("=" * 60)
input("\nPress Enter to exit...")