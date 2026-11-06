"""Print Design_Rationale.html to a white A4 PDF with MathJax equations typeset (headless Microsoft Edge).

Writes Report/Design_Rationale.pdf. The HTML itself is not changed: a print copy with an extra
stylesheet is written to Report/_print/ and printed from there.
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "Design_Rationale.html"
TMP = HERE / "_print"
TMP.mkdir(exist_ok=True)
OUT = HERE / "Design_Rationale.pdf"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

PRINT_CSS = """
<style id="print-overrides">
:root, :root[data-theme] {
  --paper: #ffffff; --sheet: #ffffff; --ink: #18212f; --muted: #5b6678; --rule: #d9e0ea; --grid: #ffffff;
  --accent: #1d4ed8; --decision: #8a5a00; --decision-soft: #fbf1dc; --ok: #17803d; --ok-soft: #e3f4e9;
  color-scheme: light;
}
@page { size: A4; margin: 15mm 14mm 16mm 14mm; }
html, body { background: #ffffff !important; background-image: none !important; }
body { font-size: 10.5pt; line-height: 1.5; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.wrap { max-width: none; padding: 0; gap: 14px; }
.wrap, .sheet, header.title, .decision { display: block; }
.wrap > * + * { margin-top: 16px; }
.sheet > * + *, header.title > * + * { margin-top: 10px; }
.decision > * + * { margin-top: 4px; }
.sheet { border: none; border-top: 1px solid var(--rule); border-radius: 0; padding: 14px 0 0 0; }
h1 { font-size: 26pt; }
h2 { font-size: 16pt; break-after: avoid; }
h3 { font-size: 12.5pt; break-after: avoid; }
p, .lede, .note, ul.plain { max-width: none; }
.eq, .decision, table tr, .given, .chart { break-inside: avoid; }
.tbl, .eq { overflow: visible; }
.eq mjx-container[display="true"] > svg { max-width: 100%; height: auto; }
table { font-size: 9.5pt; }
td.n { white-space: normal; }
td:first-child { min-width: 30%; }
.decision p { font-size: 10pt; }
nav.toc { font-size: 9.5pt; }
a { color: var(--accent); text-decoration: none; }
</style>
"""

html = SRC.read_text(encoding="utf-8")
html = html.replace('<html lang="en">', '<html lang="en" data-theme="light">', 1)
html = html.replace("</head>", PRINT_CSS + "</head>", 1)
copy = TMP / "Design_Rationale_print.html"
copy.write_text(html, encoding="utf-8")

cmd = [str(EDGE), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
       "--virtual-time-budget=40000", f"--print-to-pdf={OUT}", copy.as_uri()]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
print("edge exit", r.returncode, r.stderr[-400:] if r.stderr else "")
print("pdf", OUT, OUT.stat().st_size if OUT.exists() else "missing")
