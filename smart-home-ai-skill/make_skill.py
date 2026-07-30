"""
Package the smart-home-ai skill into a .skill file.
Run from WSL:
  cd ~/workspace/smart_home_AI/smart-home-ai-skill
  python3 make_skill.py
"""
import zipfile
from pathlib import Path

here = Path(__file__).parent
out = here / "smart-home-ai.skill"

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(here / "SKILL.md", arcname="smart-home-ai/SKILL.md")

print(f"Done: {out}")
print("Drag this file into Cowork → Settings → Skills to install.")
