"""Make the fake demo files, and (optionally) copy them to this PC's Desktop.

    python demo/make_demo_files.py            # (re)build the files in demo/desktop/
    python demo/make_demo_files.py --install  # also copy them to ~/Desktop

--install never overwrites: a file that already exists on the Desktop is skipped.
Everything here is fake ("Alex Demo"); nothing private.  Owner: Demo, tests & safety.
"""
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent / "desktop"

CV_LINES = [
    ("Alex Demo", 40),
    ("Curriculum Vitae", 24),
    ("", 16),
    ("alex.demo@example.com  |  Vilnius", 16),
    ("", 16),
    ("EXPERIENCE", 20),
    ("2025-now   Junior Developer, Example Studio", 16),
    ("2024       Intern, Hackathon Club", 16),
    ("", 16),
    ("EDUCATION", 20),
    ("2022-2026  BSc Computer Science, Example University", 16),
    ("", 16),
    ("SKILLS", 20),
    ("Python, JavaScript, talking to computers from my phone", 16),
    ("", 16),
    ("(Fake CV for the HomeCall demo.)", 14),
]

DRAFT = """Old draft - DO NOT USE

This is an old draft of my essay. The final version is in Documents.
(Fake file for the HomeCall demo: the AI is asked to delete it, and the phone
asks Yes/No first.)
"""

NOTES = """# Notes

- Buy milk
- Call grandma on Sunday
- Hackathon demo: practise twice, charge the phone
- Wi-Fi password for the cabin is on the fridge, NOT in this file

(Fake notes for the HomeCall demo.)
"""


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def make_cv(path: Path) -> None:
    img = Image.new("RGB", (1240, 1754), "white")  # A4 at 150 dpi
    draw = ImageDraw.Draw(img)
    y = 120
    for text, size in CV_LINES:
        if text:
            draw.text((120, y), text, fill="black", font=_font(size * 2))
        y += size * 3
    img.save(path, "PDF", resolution=150)


def build() -> list[Path]:
    HERE.mkdir(exist_ok=True)
    files = [HERE / "CV_Alex_Demo.pdf", HERE / "Old draft - essay.txt", HERE / "notes.md"]
    make_cv(files[0])
    files[1].write_text(DRAFT, encoding="utf-8")
    files[2].write_text(NOTES, encoding="utf-8")
    return files


def install(files: list[Path]) -> None:
    desktop = Path.home() / "Desktop"
    for f in files:
        target = desktop / f.name
        if target.exists():
            print(f"  skip  {target} (already there)")
        else:
            shutil.copy2(f, target)
            print(f"  copy  {target}")


if __name__ == "__main__":
    made = build()
    print("Built:", ", ".join(f.name for f in made))
    if "--install" in sys.argv:
        install(made)
