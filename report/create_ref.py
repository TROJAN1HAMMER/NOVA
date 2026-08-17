from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

doc = Document()
doc.styles['Normal'].font.name = 'Times New Roman'
doc.styles['Normal'].font.size = Pt(11)

# Configure headings
for i in range(1, 4):
    style = doc.styles[f'Heading {i}']
    style.font.name = 'Times New Roman'
    style.font.color.rgb = None
    if i == 1:
        style.font.size = Pt(16)
        style.font.bold = True
    elif i == 2:
        style.font.size = Pt(14)
        style.font.bold = True
    elif i == 3:
        style.font.size = Pt(12)
        style.font.bold = True

section = doc.sections[0]
section.page_height = Cm(29.7)
section.page_width = Cm(21.0)
section.left_margin = Cm(2.54)
section.right_margin = Cm(2.54)
section.top_margin = Cm(2.54)
section.bottom_margin = Cm(2.54)

doc.save('/Users/23MIS0012/Desktop/NOVA/report/reference.docx')
