import argparse
import hashlib
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]


def archive(target, entries):
    with ZipFile(target, "w", ZIP_DEFLATED, compresslevel=5) as bundle:
        for path, name in entries:
            bundle.write(path, name)
    with ZipFile(target) as bundle:
        corrupt_entry = bundle.testzip()
        if corrupt_entry:
            raise RuntimeError(f"Invalid ZIP entry: {corrupt_entry}")


def build(version):
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"} or struct.calcsize("P") != 8:
        raise SystemExit("Build the release with 64-bit Python on x64 Windows.")
    temp = ROOT / ".build"
    destination = ROOT / "dist"
    temp.mkdir(exist_ok=True)
    destination.mkdir(exist_ok=True)
    app_dir = temp / "app"

    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--onefile", "--windowed", "--noupx",
        "--noconfirm", "--name", "SpoilerVeil", "--distpath", str(app_dir),
        "--workpath", str(temp / "work"), "--specpath", str(temp),
        "--add-data", str(ROOT / "browser" / "defaults.js") + ":browser",
        str(ROOT / "spoilerveil.py"),
    ], cwd=ROOT, check=True)

    windows_zip = destination / f"SpoilerVeil-{version}-windows-x64.zip"
    browser_zip = destination / f"SpoilerVeil-{version}-browser-extension.zip"
    exe = app_dir / "SpoilerVeil.exe"
    windows_files = [(exe, exe.name), (ROOT / "README.md", "README.md")]
    windows_files.extend(
        (path, path.relative_to(ROOT).as_posix())
        for path in sorted((ROOT / "licenses").iterdir()) if path.is_file()
    )
    browser_files = [
        (path, path.name) for path in sorted((ROOT / "browser").iterdir())
        if path.is_file() and path.suffix in {".css", ".html", ".js", ".json"}
    ]
    archive(windows_zip, windows_files)
    archive(browser_zip, browser_files)

    checksums = []
    for path in (windows_zip, browser_zip):
        with path.open("rb") as asset:
            digest = hashlib.file_digest(asset, "sha256").hexdigest()
        checksums.append(f"{digest}  {path.name}\n")
    (destination / "SHA256SUMS.txt").write_text("".join(checksums), encoding="utf-8", newline="\n")
    print(f"Release files written to {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the Windows and browser release ZIPs.")
    parser.add_argument("version", help="Release number in the form MAJOR.MINOR.PATCH.")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.version):
        parser.error("version must use MAJOR.MINOR.PATCH, such as 1.0.0")
    build(args.version)
