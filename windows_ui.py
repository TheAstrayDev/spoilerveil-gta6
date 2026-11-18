import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import tkinter as tk

from shield_rules import Box


def bind(lib, name, result, *arguments):
    function = getattr(lib, name)
    function.restype = result
    function.argtypes = arguments
    return function


user = C.WinDLL("user32", use_last_error=True)
kernel = C.WinDLL("kernel32", use_last_error=True)
dwm = C.WinDLL("dwmapi", use_last_error=True)
dpi_aware = bind(user, "SetProcessDpiAwarenessContext", W.BOOL, C.c_void_p)
get_root = bind(user, "GetAncestor", W.HWND, W.HWND, W.UINT)
get_foreground = bind(user, "GetForegroundWindow", W.HWND)
get_pid = bind(user, "GetWindowThreadProcessId", W.DWORD, W.HWND, C.POINTER(W.DWORD))
get_bounds = bind(user, "GetWindowRect", W.BOOL, W.HWND, C.POINTER(W.RECT))
get_visual_bounds = bind(dwm, "DwmGetWindowAttribute", C.c_long, W.HWND, W.DWORD, C.c_void_p, W.DWORD)
get_style = bind(user, "GetWindowLongW", C.c_long, W.HWND, C.c_int)
set_style = bind(user, "SetWindowLongW", C.c_long, W.HWND, C.c_int, C.c_long)
set_pos = bind(user, "SetWindowPos", W.BOOL, W.HWND, W.HWND,
               C.c_int, C.c_int, C.c_int, C.c_int, W.UINT)
set_affinity = bind(user, "SetWindowDisplayAffinity", W.BOOL, W.HWND, W.DWORD)
open_process = bind(kernel, "OpenProcess", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
close_handle = bind(kernel, "CloseHandle", W.BOOL, W.HANDLE)
process_image = bind(kernel, "QueryFullProcessImageNameW", W.BOOL, W.HANDLE,
                     W.DWORD, W.LPWSTR, C.POINTER(W.DWORD))
monitor_callback = C.WINFUNCTYPE(W.BOOL, W.HMONITOR, W.HDC, C.POINTER(W.RECT), W.LPARAM)
enum_monitors = bind(user, "EnumDisplayMonitors", W.BOOL, W.HDC, C.POINTER(W.RECT),
                     monitor_callback, W.LPARAM)
FILL = "#112121"
KEY = "#010200"
FG = "#c5ded5"


def monitors():
    result = []

    @monitor_callback
    def collect(_monitor, _display, rect, _data):
        r = rect.contents
        result.append(Box(r.left, r.top, r.right, r.bottom))
        return True

    enum_monitors(None, None, collect, 0)
    return tuple(result)


def telegram_window():
    hwnd = get_foreground()
    if not hwnd:
        return None
    pid = W.DWORD()
    get_pid(hwnd, C.byref(pid))
    process = open_process(0x1000, False, pid.value)
    if not process:
        return None
    try:
        buf = C.create_unicode_buffer(32768)
        length = W.DWORD(len(buf))
        if not process_image(process, 0, buf, C.byref(length)):
            return None
        if Path(buf.value).stem.casefold() != "telegram":
            return None
    finally:
        close_handle(process)
    return window_bounds(hwnd)


def window_bounds(hwnd):
    rect = W.RECT()
    result = get_visual_bounds(hwnd, 9, C.byref(rect), C.sizeof(rect))
    if result != 0 and not get_bounds(hwnd, C.byref(rect)):
        return None
    if rect.right <= rect.left or rect.bottom <= rect.top:
        return None
    return hwnd, Box(rect.left, rect.top, rect.right, rect.bottom)


class Overlay:
    def __init__(self, parent, transparent):
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.configure(bg=KEY if transparent else FILL)
        if transparent:
            self.window.attributes("-transparentcolor", KEY)
        else:
            self.window.attributes("-alpha", .999)
        self.canvas = tk.Canvas(self.window, highlightthickness=0,
                                bg=KEY if transparent else FILL)
        self.canvas.pack(fill="both", expand=True)
        self.window.update_idletasks()
        self.hwnd = get_root(self.window.winfo_id(), 2)
        # Layered + click-through + tool window + never activate on click.
        styles = 0x80000 | 0x20 | 0x80 | 0x08000000
        set_style(self.hwnd, -20, get_style(self.hwnd, -20) | styles)
        if not set_affinity(self.hwnd, 0x11):
            self.window.destroy()
            raise OSError("Windows could not exclude the overlay from screen capture.")
        self.bounds = None
        self.visible = False
        self.photo = None
        self.boxes = None

    def fit(self, bounds):
        if not self.visible:
            self.window.deiconify()
            self.visible = True
        if bounds != self.bounds:
            self.bounds = bounds
            self.boxes = None
            set_pos(self.hwnd, C.c_void_p(-1), bounds.left, bounds.top,
                    bounds.right-bounds.left, bounds.bottom-bounds.top, 0x10 | 0x40)

    def text(self, text):
        self.boxes = None
        self.canvas.delete("all")
        self.photo = None
        self.canvas.create_text((self.bounds.right-self.bounds.left)/2,
                                (self.bounds.bottom-self.bounds.top)/2,
                                text=text, font=("Segoe UI", 16), fill=FG)

    def show_image(self, photo):
        self.boxes = None
        self.canvas.delete("all")
        self.photo = photo
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

    def show_boxes(self, boxes):
        if boxes == self.boxes:
            return
        self.boxes = boxes
        self.canvas.delete("all")
        for box in boxes:
            local = box.move(-self.bounds.left, -self.bounds.top)
            self.canvas.create_rectangle(*local.tuple(), fill=FILL, outline="")

    def hide(self):
        if self.visible:
            self.window.withdraw()
            self.canvas.delete("all")
            self.bounds = None
            self.boxes = None
            self.visible = False
            self.photo = None
