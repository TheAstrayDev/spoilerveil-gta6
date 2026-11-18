# SpoilerVeil for GTA VI

Keep using Telegram and browsing the web without seeing every GTA VI discussion. SpoilerVeil filters game-related text locally on Windows and in your browser. You can add your own phrases as spoiler vocabulary changes.

**[Download the latest release](https://github.com/TheAstrayDev/spoilerveil-gta6/releases/latest)**

| Where | What SpoilerVeil does |
| --- | --- |
| Telegram Desktop | Reads the active window and covers matches. Live mode keeps scrolling and clicks in Telegram itself. |
| Other Windows apps | **Entire screen** mode scans visible text across your monitors. |
| Telegram Web and other sites | The extension hides matching messages and posts, as well as some spoiler-related pages or chats. It hides media in Telegram Web by default. |

## Windows setup

1. Download the **Windows x64** ZIP from the latest release and extract it. It contains a portable, unsigned executable.
2. Open **SpoilerVeil.exe**, choose **Telegram Desktop only** or **Entire screen**, and click **Enable protection**.
3. Open Telegram Desktop. Leave **Check Telegram frames before display** off for smooth scrolling. Turn it on when you prefer a pre-checked view and can tolerate slower updates.
4. Add custom words and phrases one per line, then click **Save rules**.

The portable build supports Windows 11 x64 and targets Windows 10 x64 version 2004 or later. Python is bundled. Text recognition uses the English and Russian OCR components installed in Windows. After the first scan, the app shows the available OCR languages. Add missing components under **Settings → Time & language → Language & region**.

## Browser setup

Download and extract the **browser extension** ZIP. Reload any pages you want to filter after installing the extension.

- **Chrome and Edge.** Open `chrome://extensions` or `edge://extensions`, enable **Developer mode**, click **Load unpacked**, and select the directory containing `manifest.json`.
- **Firefox 142 or later.** Open `about:debugging#/runtime/this-firefox`, click **Load Temporary Add-on**, and select `manifest.json`. Firefox removes this temporary add-on when it restarts. [Mozilla’s installation instructions](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Your_first_WebExtension#installing)

Open the SpoilerVeil toolbar menu to manage rules, pause website filtering, or show Telegram Web media again. Both versions start with the same dictionary. Custom rules are stored separately.

## Privacy and limitations

SpoilerVeil keeps screen captures and recognized text in memory. The app and extension send no screen captures, chat content, or telemetry over the network. Neither connects to a Telegram account. The extension needs access to ordinary web pages so it can filter the text on them.

Fast mode covers text after OCR, so a message can appear briefly. When using the pre-checked view, switching to Telegram can still expose the window for a moment. Keyword filtering can miss indirect references, speech, and text the OCR engine cannot read. Turn off **message previews** in Telegram if you want to keep spoilers out of notification banners.

The optional character and location rules can hide unrelated uses of the same names. You can turn those rules off while keeping the game-title filter enabled.

## Run or build from source

Use 64-bit Python 3.14 on Windows. Dependency versions are pinned to the public release build.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe spoilerveil.py
```

The self-test uses synthetic English and Russian text.

```powershell
.\.venv\Scripts\python.exe spoilerveil.py --self-test
```

Build both release ZIPs and their SHA-256 checksums into `dist\`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe scripts\build_release.py 1.0.0
```

Third-party notices for the Windows executable are in [licenses](licenses/).
