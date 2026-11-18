import asyncio
import math

from PIL import Image
from winrt.windows.foundation import IAsyncInfo
from winrt.windows.foundation.collections import IVectorView
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import Buffer

from shield_rules import Box, Line


class LocalOCR:
    def __init__(self):
        self.engines = []
        self.languages = []
        for language in OcrEngine.available_recognizer_languages:
            if language.language_tag.split("-")[0] in {"ru", "en"}:
                self.engines.append(OcrEngine.try_create_from_language(language))
                self.languages.append(language.language_tag)
        if not self.engines:
            engine = OcrEngine.try_create_from_user_profile_languages()
            if engine is None:
                raise RuntimeError("Install the Windows OCR component for English or Russian.")
            self.engines.append(engine)
            self.languages.append(engine.recognizer_language.language_tag)

    def read(self, image):
        return asyncio.run(self.read_async(image))

    async def read_async(self, image):
        limit = min(2460, OcrEngine.max_image_dimension)
        scale = min(1.0, limit / max(image.size))
        if scale < 1:
            image = image.resize(tuple(max(1, round(v*scale)) for v in image.size),
                                 Image.Resampling.LANCZOS)
        data = image.tobytes("raw", "BGRX")
        buffer = Buffer(len(data))
        buffer.length = len(data)
        memoryview(buffer)[:] = data
        bitmap = SoftwareBitmap.create_copy_from_buffer(
            buffer, BitmapPixelFormat.BGRA8, *image.size, BitmapAlphaMode.IGNORE
        )
        results = []
        try:
            for engine in self.engines:
                result = await engine.recognize_async(bitmap)
                rows = []
                for row in result.lines:
                    words = [word.bounding_rect for word in row.words]
                    if words:
                        rows.append(Line(row.text, Box(
                            math.floor(min(r.x for r in words)/scale),
                            math.floor(min(r.y for r in words)/scale),
                            math.ceil(max(r.x+r.width for r in words)/scale),
                            math.ceil(max(r.y+r.height for r in words)/scale),
                        )))
                results.append(rows)
        finally:
            bitmap.close()
        return results
