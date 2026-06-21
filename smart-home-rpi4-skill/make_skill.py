"""
Package the smart-home-rpi4 skill into a .skill file.
Run from WSL:
  cd ~/workspace/smart-home-rpi4/smart-home-rpi4-skill
  python3 make_skill.py
"""
import zipfile
from pathlib import Path

here = Path(__file__).parent
out = here / "smart-home-rpi4.skill"

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(here / "SKILL.md", arcname="smart-home-rpi4/SKILL.md")

print(f"Done: {out}")
print("Drag this file into Cowork → Settings → Skills to install.")
