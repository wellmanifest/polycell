"""Szkielet nowego kontraktu: python tools/polycell/new_cell.py invoice.total python [--ns shop]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from model import ROOT  # noqa: E402

name, owner = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "python")
ns = sys.argv[sys.argv.index("--ns") + 1] if "--ns" in sys.argv else "shop"
p = ROOT / "contracts/cells" / f"{name}.cell.yaml"
if p.exists():
    raise SystemExit(f"exists: {p}")
p.write_text(f"""schema: wellmanifest.polycell.cell/v1
urn: urn:wm:cell:{ns}:{name}:v1
name: {name}
version: 0.1.0
owner: {owner}
summary: TODO opis jednym zdaniem
effects: [pure]
input:
  value: string
output:
  result: string
nl:
  pl: ["TODO fraza po polsku"]
  en: ["TODO english phrase"]
menu: {{category: TODO, label: {name}, interactionType: modal_form}}
examples:
  - name: basic
    input: {{value: "a"}}
    output: {{result: "a"}}
""", encoding="utf-8")
print(f"created {p.relative_to(ROOT)} -> edit, then: make gen && make prompt CELL={name}")
