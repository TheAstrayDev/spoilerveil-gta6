from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from shield_rules import Box, Filter, masked_lines
from windows_capture import capture
from windows_ocr import LocalOCR
from windows_ui import FG, FILL, Overlay, dpi_aware, monitors, telegram_window


CONFIG = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SpoilerShield" / "settings.json"
BG, SUBTLE, ACCENT = "#121b1c", "#9bb2ac", "#a8eed1"
TELEGRAM_INTERVAL = .14
DESKTOP_INTERVAL = .28
BACKGROUND_INTERVAL = .90


@dataclass(frozen=True)
class Request:
    generation: int
    bounds: Box
    matcher: Filter
    telegram: bool = False
    strict: bool = False
    omit: Box | None = None


@dataclass
class Result:
    request: Request
    masks: tuple
    mirror: Image.Image | None
    languages: str


class Scan:
    def __init__(self):
        self.ocr = None
        self.cache = OrderedDict()

    def analyze(self, image, bounds, matcher, telegram=False, strict=False):
        digest = hashlib.blake2b(image.tobytes(), digest_size=16).digest()
        key = (bounds, telegram, strict)
        previous = self.cache.get(key)
        if previous and previous[:2] == (digest, matcher):
            self.cache.move_to_end(key)
            return previous[2]
        groups = self.ocr.read(image)
        masks = [box for rows in groups for box in masked_lines(rows, matcher)]
        mirror = None
        width, height = image.size
        view = Box(0, 0, width, height)
        header_hit = False
        if telegram:
            # Telegram's chat header sits above the message list, right of the chat sidebar.
            header_hit = any(
                row.bounds.left >= min(250, width*.255)
                and 28 <= row.bounds.top <= min(112, height*.16)
                and matcher.matches(row.text)
                for rows in groups for row in rows
            )
            if header_hit:
                masks = [view]
        visible_masks = [clipped for box in masks if (clipped := box.intersection(view))]
        if strict:
            mirror = image.copy()
            draw = ImageDraw.Draw(mirror)
            for box in visible_masks:
                draw.rectangle(box.tuple(), fill=FILL)
            if header_hit:
                font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
                font = ImageFont.truetype(str(font_dir / "segoeui.ttf"), 20)
                draw.text((width//2, height//2), "Chat hidden by SpoilerVeil", fill=FG, font=font, anchor="mm")
        result = (tuple(dict.fromkeys(box.move(bounds.left, bounds.top) for box in visible_masks)), mirror)
        self.cache[key] = (digest, matcher, result)
        self.cache.move_to_end(key)
        if len(self.cache) > 6:
            self.cache.popitem(last=False)
        return result

    def run(self, request):
        if self.ocr is None:
            self.ocr = LocalOCR()
        image = capture(request.bounds)
        if request.omit:
            box = request.omit.intersection(request.bounds)
            if box:
                omit = box.move(-request.bounds.left, -request.bounds.top)
                image.paste(FILL, omit.tuple())
        masks, mirror = self.analyze(image, request.bounds, request.matcher,
                                     request.telegram, request.strict)
        return Result(request, masks, mirror, " + ".join(self.ocr.languages))


def union(bounds):
    result = bounds[0]
    for box in bounds[1:]:
        result = result.union(box)
    return result


def outside(box, excluded):
    cut = box.intersection(excluded) if excluded else None
    if cut is None:
        return (box,)
    bands = (
        Box(box.left, box.top, box.right, cut.top),
        Box(box.left, cut.bottom, box.right, box.bottom),
        Box(box.left, cut.top, cut.left, cut.bottom),
        Box(cut.right, cut.top, box.right, cut.bottom),
    )
    return tuple(band for band in bands if min(band.size) > 0)


def paint(overlay, boxes):
    if boxes:
        overlay.fit(union(boxes))
        overlay.show_boxes(boxes)
    else:
        overlay.hide()


class Control:
    def __init__(self, root):
        self.root = root
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-ocr")
        self.scan = Scan()
        self.pending = None
        self.active = False
        self.generation = 0
        self.telegram_due = self.desktop_due = self.monitors_due = 0
        self.current_telegram = None
        self.displays = ()
        self.display_cursor = 0
        self.desktop_masks = {}
        self.mirror = self.mask = self.telegram_mask = None
        self.shown_frame = None
        self.status = tk.StringVar(value="Protection off")
        saved = self.load_settings()
        self.mode = tk.StringVar(value="telegram" if saved.get("mode") == "telegram" else "all")
        self.strict = tk.BooleanVar(value=saved.get("strict", False) is True)
        self.related = tk.BooleanVar(value=saved.get("related", True) is not False)
        self.matcher = Filter(str(saved.get("extra","")), self.related.get())
        self.build(str(saved.get("extra",""))[:12000])
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(45, self.tick)

    def load_settings(self):
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def build(self, extra):
        self.root.title("SpoilerVeil")
        self.root.configure(bg=BG)
        self.root.minsize(495, 478)
        frame = tk.Frame(self.root, bg=BG, padx=26, pady=22)
        frame.pack(fill="both", expand=True)
        label = lambda text, size, color=FG, **kw: tk.Label(
            frame, text=text, bg=BG, fg=color, font=("Segoe UI", size), **kw
        )
        label("SpoilerVeil", 27).pack(anchor="w")
        label("Windows · On-device screen filtering", 10, SUBTLE).pack(anchor="w", pady=(0, 17))
        for value, text in [
            ("all", "Entire screen, including Telegram Desktop"),
            ("telegram", "Telegram Desktop only"),
        ]:
            tk.Radiobutton(frame, text=text, value=value, variable=self.mode, anchor="w",
                           command=self.change_mode, fg=FG, bg=BG, selectcolor="#233332",
                           activebackground=BG, activeforeground=ACCENT,
                           font=("Segoe UI", 10)).pack(fill="x")
        tk.Checkbutton(frame, text="Check Telegram frames before display (adds a delay)",
                       variable=self.strict, command=self.change_mode, fg=FG, bg=BG,
                       selectcolor="#233332", activebackground=BG, activeforeground=ACCENT,
                       font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 0))
        tk.Checkbutton(frame, text="Also match character and location names",
                       variable=self.related, fg=FG, bg=BG, selectcolor="#233332",
                       activebackground=BG, activeforeground=ACCENT,
                       font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 11))
        label("Custom words and phrases", 11).pack(anchor="w")
        self.extra = tk.Text(frame, height=4, width=53, bg="#1d2c2c", fg=FG,
                             insertbackground=FG, relief="flat", padx=9, pady=7,
                             undo=True, font=("Segoe UI", 10))
        self.extra.insert("1.0", extra)
        self.extra.pack(fill="both", expand=True, pady=(5, 3))
        label("One word or phrase per line.", 9, SUBTLE).pack(anchor="w")
        actions = tk.Frame(frame, bg=BG)
        actions.pack(fill="x", pady=(16, 10))
        self.toggle = tk.Button(actions, text="Enable protection", command=self.toggle_scan,
                                bg=ACCENT, fg="#172625", relief="flat",
                                font=("Segoe UI Semibold", 11), padx=13, pady=5)
        self.toggle.pack(side="left")
        tk.Button(actions, text="Save rules", command=self.save_settings,
                  bg="#243736", fg=FG, activebackground="#33514e", activeforeground=FG,
                  relief="flat", font=("Segoe UI", 10), padx=11, pady=5).pack(side="left", padx=8)
        tk.Label(frame, textvariable=self.status, fg=ACCENT, bg=BG, justify="left",
                 wraplength=440, font=("Segoe UI", 10)).pack(anchor="w")

    def save_settings(self):
        extra = self.extra.get("1.0", "end-1c")[:12000]
        self.matcher = Filter(extra, self.related.get())
        self.change_mode()
        payload = {"extra": extra, "related": self.related.get(), "mode": self.mode.get(),
                   "strict": self.strict.get()}
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            draft = CONFIG.with_suffix(".tmp")
            draft.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            draft.replace(CONFIG)
        except OSError:
            self.status.set("Windows could not save your settings. The rules apply until you close the app.")
            return
        self.status.set("Rules saved")

    def change_mode(self):
        if self.active:
            self.ensure_mirror()
            self.clear_masks()

    def ensure_mirror(self):
        if self.strict.get() and self.mirror is None:
            try:
                self.mirror = Overlay(self.root, transparent=False)
            except (OSError, tk.TclError):
                self.strict.set(False)
                self.set_status("Frame checking is unavailable. Live filtering is on.")

    def clear_masks(self):
        self.generation += 1
        self.telegram_due = self.desktop_due = 0
        self.current_telegram = self.shown_frame = None
        self.desktop_masks.clear()
        self.mask.hide()
        self.telegram_mask.hide()
        if self.mirror:
            self.mirror.hide()

    def set_status(self, value):
        if self.status.get() != value:
            self.status.set(value)

    def toggle_scan(self):
        if self.active:
            self.active = False
            self.clear_masks()
            self.toggle.configure(text="Enable protection")
            self.status.set("Protection off")
            return
        try:
            if self.mask is None:
                self.mask = Overlay(self.root, transparent=True)
            if self.telegram_mask is None:
                self.telegram_mask = Overlay(self.root, transparent=True)
        except (OSError, tk.TclError) as error:
            self.status.set(str(error))
            return
        self.matcher = Filter(self.extra.get("1.0", "end-1c")[:12000], self.related.get())
        self.clear_masks()
        self.active = True
        self.toggle.configure(text="Disable protection")
        self.status.set("Starting text recognition…")
        self.ensure_mirror()

    def refresh_target(self, now):
        if now >= self.monitors_due:
            displays = monitors()
            self.monitors_due = now + 1
            if displays != self.displays:
                self.displays = displays
                self.display_cursor = 0
                self.clear_masks()
        window = telegram_window()
        bounds = window and self.displays and window[1].intersection(union(self.displays))
        target = (window[0], bounds) if bounds else None
        if target != self.current_telegram:
            self.generation += 1
            self.current_telegram = target
            self.shown_frame = None
            self.telegram_due = now
            self.desktop_due = now + .22 if target else now
            self.telegram_mask.hide()
            if target and self.strict.get():
                self.mirror.fit(target[1])
                self.mirror.text("Checking the Telegram window…")
            elif self.mirror:
                self.mirror.hide()
            self.paint_desktop()

    def paint_desktop(self):
        excluded = self.current_telegram[1] if self.current_telegram else None
        boxes = tuple(part for masks in self.desktop_masks.values() for box in masks
                      for part in outside(box, excluded))
        paint(self.mask, boxes)

    def apply_scan(self, now):
        if self.pending is None or not self.pending[1].done():
            return
        request, future = self.pending
        self.pending = None
        if request.generation != self.generation:
            return
        try:
            result = future.result()
        except Exception as error:
            self.set_status(f"Text recognition unavailable. {error}")
            if request.telegram:
                self.telegram_due = now + 1.5
                if request.strict:
                    self.shown_frame = None
                    self.mirror.text("Telegram is hidden. Text recognition is unavailable.")
            else:
                self.desktop_due = now + 1.5
            return
        if request.strict:
            if result.mirror is not self.shown_frame:
                photo = ImageTk.PhotoImage(result.mirror, master=self.root)
                self.mirror.show_image(photo)
                self.shown_frame = result.mirror
        elif request.telegram:
            paint(self.telegram_mask, result.masks)
        else:
            self.desktop_masks[request.bounds] = result.masks
            self.paint_desktop()
        self.set_status("Protection on  ·  " + result.languages)

    def schedule(self, now):
        if self.pending is not None:
            return
        target = self.current_telegram[1] if self.current_telegram else None
        request = None
        # In full-screen mode, still inspect other areas but never OCR Telegram twice.
        if self.mode.get() == "all":
            displays = [display for display in self.displays
                        if not target or display.intersection(target) != display]
            if displays and now >= self.desktop_due:
                display = displays[self.display_cursor % len(displays)]
                self.display_cursor += 1
                self.desktop_due = now + (BACKGROUND_INTERVAL if target else DESKTOP_INTERVAL)
                request = Request(self.generation, display, self.matcher, omit=target)
        if request is None and target and now >= self.telegram_due:
            self.telegram_due = now + TELEGRAM_INTERVAL
            request = Request(self.generation, target, self.matcher, telegram=True,
                              strict=self.strict.get())
        if request:
            self.pending = (request, self.executor.submit(self.scan.run, request))
        elif not target and self.mode.get() == "telegram":
            self.set_status("Protection on  ·  Open Telegram Desktop")

    def poll(self):
        now = time.monotonic()
        self.refresh_target(now)
        self.apply_scan(now)
        self.schedule(now)

    def tick(self):
        if self.active:
            self.poll()
        elif self.pending is not None and self.pending[1].done():
            self.pending = None
        self.root.after(35, self.tick)

    def close(self):
        self.active = False
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def self_test():
    assert Filter().matches("Обсуждение Г.Т.А.\u200b 6")
    assert Filter().matches("GTA Ⅵ")
    assert not Filter().matches("Обсуждение пятой части")
    assert Filter("Выдуманный код").matches("Тест — выдуманный-код.")
    image = Image.new("RGB", (720, 200), "#fcfcfc")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("segoeui.ttf", 36)
    draw.text((28,25), "GTA VI - DEMO", fill="#111111", font=font)
    draw.text((28,108), "ГТА 6 — ПРОВЕРКА", fill="#111111", font=font)
    scan = Scan()
    scan.ocr = LocalOCR()
    groups = scan.ocr.read(image)
    matches = [box for rows in groups for box in masked_lines(rows, Filter())]
    if not any(box.top < 85 for box in matches):
        raise RuntimeError("OCR missed the English test text.")
    if "ru" in scan.ocr.languages and not any(box.bottom > 115 for box in matches):
        raise RuntimeError("OCR missed the Russian test text.")
    print("Local OCR test passed:", ", ".join(scan.ocr.languages))


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    dpi_aware(ctypes.c_void_p(-4))
    root = tk.Tk()
    Control(root)
    root.mainloop()


if __name__ == "__main__":
    main()
