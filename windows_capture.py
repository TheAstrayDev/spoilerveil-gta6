import ctypes as C
from ctypes import wintypes as W

from PIL import Image

from windows_ui import bind, user


class BitmapHeader(C.Structure):
    _fields_ = [
        ("size", W.DWORD), ("width", W.LONG), ("height", W.LONG),
        ("planes", W.WORD), ("bits", W.WORD), ("compression", W.DWORD),
        ("image_size", W.DWORD), ("x_meters", W.LONG), ("y_meters", W.LONG),
        ("colors", W.DWORD), ("important_colors", W.DWORD),
    ]


gdi = C.WinDLL("gdi32", use_last_error=True)
get_dc = bind(user, "GetDC", W.HDC, W.HWND)
release_dc = bind(user, "ReleaseDC", C.c_int, W.HWND, W.HDC)
create_dc = bind(gdi, "CreateCompatibleDC", W.HDC, W.HDC)
delete_dc = bind(gdi, "DeleteDC", W.BOOL, W.HDC)
create_dib = bind(gdi, "CreateDIBSection", W.HBITMAP, W.HDC, C.POINTER(BitmapHeader),
                  W.UINT, C.POINTER(C.c_void_p), W.HANDLE, W.DWORD)
select_object = bind(gdi, "SelectObject", W.HGDIOBJ, W.HDC, W.HGDIOBJ)
delete_object = bind(gdi, "DeleteObject", W.BOOL, W.HGDIOBJ)
copy_pixels = bind(gdi, "BitBlt", W.BOOL, W.HDC, C.c_int, C.c_int, C.c_int, C.c_int,
                   W.HDC, C.c_int, C.c_int, W.DWORD)
flush_gdi = bind(gdi, "GdiFlush", W.BOOL)
COPY_LAYERED_WINDOWS = 0x00CC0020 | 0x40000000


def capture(bounds):
    """Copy the visible rectangle without capturing pixels from other monitors."""
    width, height = bounds.size
    if width < 1 or height < 1 or width * height > 36_000_000:
        raise ValueError("Unsupported capture area size.")
    source = get_dc(None)
    if not source:
        raise C.WinError(C.get_last_error())
    destination = bitmap = previous = None
    try:
        destination = create_dc(source)
        if not destination:
            raise C.WinError(C.get_last_error())
        # An uncompressed, top-down BGRX bitmap simplifies copying into Pillow.
        header = BitmapHeader(C.sizeof(BitmapHeader), width, -height, 1, 32)
        bits = C.c_void_p()
        bitmap = create_dib(source, C.byref(header), 0, C.byref(bits), None, 0)
        if not bitmap:
            raise C.WinError(C.get_last_error())
        previous = select_object(destination, bitmap)
        if not previous or previous == C.c_void_p(-1).value:
            previous = None
            raise C.WinError(C.get_last_error())
        if not copy_pixels(destination, 0, 0, width, height, source, bounds.left,
                           bounds.top, COPY_LAYERED_WINDOWS):
            raise C.WinError(C.get_last_error())
        flush_gdi()
        pixels = C.string_at(bits, width * height * 4)
        return Image.frombytes("RGB", (width, height), pixels, "raw", "BGRX")
    finally:
        if previous:
            select_object(destination, previous)
        if bitmap:
            delete_object(bitmap)
        if destination:
            delete_dc(destination)
        release_dc(None, source)
