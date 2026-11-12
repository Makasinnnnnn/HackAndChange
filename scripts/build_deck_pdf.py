"""Create a PDF from the presentation's verified renders, preserving the editable PPTX separately."""

from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "output/presentation/alfa-route-rehearsal-v2.pdf"
slides = sorted((ROOT / ".private/deck").glob("slide-*.png"))
if len(slides) != 9:
    raise SystemExit("Expected the nine rendered slides")
pdf = canvas.Canvas(str(output), pagesize=(960, 540))
pdf.setTitle("Альфа-Маршрут — версия для репетиции")
for index, slide in enumerate(slides):
    pdf.drawImage(ImageReader(str(slide)), 0, 0, width=960, height=540)
    if index == 0:
        pdf.linkURL("https://github.com/Makasinnnnnn/HackAndChange", (52, 182, 880, 216), relative=0)
    pdf.showPage()
pdf.save()
print(f"Created {output.name}: {len(slides)} pages")
