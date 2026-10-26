import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from app.config import settings
from app.models.schemas import Plan, DocumentSection, TableData

logger = logging.getLogger("service.document")

# Corporate Color Palette
COLOR_PRIMARY = RGBColor(31, 78, 121)    # Deep Navy
COLOR_SECONDARY = RGBColor(46, 64, 83)   # Dark Slate
COLOR_MUTED = RGBColor(100, 116, 139)    # Muted Gray
COLOR_WHITE = RGBColor(255, 255, 255)    # White
HEX_PRIMARY = "1F4E79"
HEX_SHADING_LIGHT = "F0F4F8"
HEX_ZEBRA = "F8FAFC"
HEX_BORDER = "CBD5E1"

def set_cell_background(cell, hex_color: str):
    """Sets background shading of a docx table cell via XML."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets internal padding for a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

class DocumentService:
    """
    Enterprise-grade Microsoft Word (.docx) document generator.
    Applies corporate typography, custom palettes, native tables, and callouts.
    """
    def __init__(self):
        self.output_dir = settings.absolute_storage_dir

    def generate_docx(self, plan: Plan, sections: List[DocumentSection]) -> str:
        """
        Builds and saves a polished .docx file.
        Returns the absolute filepath of the generated document.
        """
        logger.info(f"Building polished Word document for: '{plan.document_title}'")
        doc = docx.Document()

        # Set page margins (1 inch all around)
        for section in doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)

            # Footer
            footer = section.footer
            footer_p = footer.paragraphs[0]
            footer_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            f_run = footer_p.add_run(f"{plan.document_title} | Fluid AI Autonomous Agent")
            f_run.font.name = "Calibri"
            f_run.font.size = Pt(8.5)
            f_run.font.color.rgb = COLOR_MUTED

        # --- 1. COVER / TITLE BANNER ---
        title_p = doc.add_paragraph()
        title_p.paragraph_format.space_before = Pt(12)
        title_p.paragraph_format.space_after = Pt(4)
        run_title = title_p.add_run(plan.document_title)
        run_title.font.name = "Calibri"
        run_title.font.size = Pt(24)
        run_title.font.bold = True
        run_title.font.color.rgb = COLOR_PRIMARY

        # Subtitle / Document Type
        subtitle_p = doc.add_paragraph()
        subtitle_p.paragraph_format.space_after = Pt(6)
        run_sub = subtitle_p.add_run(f"Formal Document: {plan.document_type}")
        run_sub.font.name = "Calibri"
        run_sub.font.size = Pt(12)
        run_sub.font.italic = True
        run_sub.font.color.rgb = COLOR_SECONDARY

        # Metadata line
        meta_p = doc.add_paragraph()
        meta_p.paragraph_format.space_after = Pt(16)
        date_str = datetime.now().strftime("%B %d, %Y")
        run_meta = meta_p.add_run(f"Prepared by: Autonomous Agent Engine  •  Date: {date_str}  •  Status: Final / Approved")
        run_meta.font.name = "Calibri"
        run_meta.font.size = Pt(9.5)
        run_meta.font.color.rgb = COLOR_MUTED

        # Horizontal separator rule
        self._add_horizontal_rule(doc)

        # --- 2. STRATEGIC ASSUMPTIONS PANEL ---
        if plan.assumptions:
            self._add_assumptions_panel(doc, plan.assumptions, plan.is_ambiguous)

        # --- 3. SYNTHESIZED DOCUMENT SECTIONS ---
        for sec in sections:
            # Section Heading (Heading 1)
            h_p = doc.add_paragraph()
            h_p.paragraph_format.space_before = Pt(18)
            h_p.paragraph_format.space_after = Pt(6)
            h_p.paragraph_format.keep_with_next = True
            h_run = h_p.add_run(f"{sec.section_id}. {sec.title}")
            h_run.font.name = "Calibri"
            h_run.font.size = Pt(15)
            h_run.font.bold = True
            h_run.font.color.rgb = COLOR_PRIMARY

            # Section Content Paragraphs
            if sec.content:
                paragraphs = sec.content.split("\n\n")
                for p_text in paragraphs:
                    clean_p = p_text.strip()
                    if not clean_p:
                        continue
                    
                    # Handle bullet points
                    if clean_p.startswith("- ") or clean_p.startswith("* "):
                        bullet_items = clean_p.split("\n")
                        for b_item in bullet_items:
                            b_clean = re.sub(r"^[-*]\s*", "", b_item).strip()
                            if b_clean:
                                bp = doc.add_paragraph(style='List Bullet')
                                bp.paragraph_format.space_after = Pt(3)
                                b_run = bp.add_run(b_clean)
                                b_run.font.name = "Calibri"
                                b_run.font.size = Pt(10.5)
                    else:
                        p = doc.add_paragraph()
                        p.paragraph_format.line_spacing = 1.15
                        p.paragraph_format.space_after = Pt(6)
                        p_run = p.add_run(clean_p)
                        p_run.font.name = "Calibri"
                        p_run.font.size = Pt(10.5)

            # Native Structured Table (if present)
            if sec.table and sec.table.headers:
                self._render_table(doc, sec.table)

            # Callout Box (if present)
            if sec.callout:
                self._render_callout(doc, sec.callout)

        # Save document with timestamped unique filename
        safe_title = re.sub(r"[^a-zA-Z0-9_\- ]", "", plan.document_title).strip().replace(" ", "_")
        safe_title = safe_title[:40]
        filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        file_path = self.output_dir / filename

        doc.save(str(file_path))
        logger.info(f"Word document saved successfully at: {file_path}")
        return str(file_path)

    def _add_horizontal_rule(self, doc):
        """Adds a subtle horizontal divider line."""
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(14)
        p_border = parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="8" w:space="1" w:color="{HEX_PRIMARY}"/></w:pBdr>')
        p._p.get_or_add_pPr().append(p_border)

    def _add_assumptions_panel(self, doc, assumptions: List[str], is_ambiguous: bool):
        """Creates an executive assumptions callout box."""
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, HEX_SHADING_LIGHT)
        set_cell_margins(cell, top=140, bottom=140, left=200, right=200)

        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(4)
        badge = "Conflict & Ambiguity Resolution" if is_ambiguous else "Operational Assumptions"
        hdr_run = p.add_run(f"Strategic Baseline ({badge})")
        hdr_run.font.name = "Calibri"
        hdr_run.font.size = Pt(11)
        hdr_run.font.bold = True
        hdr_run.font.color.rgb = COLOR_PRIMARY

        for a in assumptions:
            ap = cell.add_paragraph(style='List Bullet')
            ap.paragraph_format.space_after = Pt(2)
            arun = ap.add_run(a)
            arun.font.name = "Calibri"
            arun.font.size = Pt(9.5)

        # Spacing after table
        sp_p = doc.add_paragraph()
        sp_p.paragraph_format.space_after = Pt(8)

    def _render_table(self, doc, table_data: TableData):
        """Renders an executive-styled Word table."""
        num_rows = len(table_data.rows) + 1
        num_cols = len(table_data.headers)

        table = doc.add_table(rows=num_rows, cols=num_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Header Row
        hdr_cells = table.rows[0].cells
        for col_idx, header_text in enumerate(table_data.headers):
            cell = hdr_cells[col_idx]
            set_cell_background(cell, HEX_PRIMARY)
            set_cell_margins(cell, top=120, bottom=120, left=140, right=140)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(str(header_text))
            run.font.name = "Calibri"
            run.font.size = Pt(10)
            run.font.bold = True
            run.font.color.rgb = COLOR_WHITE

        # Data Rows
        for r_idx, row_values in enumerate(table_data.rows):
            row_cells = table.rows[r_idx + 1].cells
            shading_color = HEX_ZEBRA if (r_idx % 2 == 1) else "FFFFFF"
            for c_idx in range(num_cols):
                cell = row_cells[c_idx]
                val = row_values[c_idx] if c_idx < len(row_values) else ""
                set_cell_background(cell, shading_color)
                set_cell_margins(cell, top=90, bottom=90, left=130, right=130)
                p = cell.paragraphs[0]
                run = p.add_run(str(val))
                run.font.name = "Calibri"
                run.font.size = Pt(9.5)
                run.font.color.rgb = COLOR_SECONDARY

        # Spacing after table
        sp_p = doc.add_paragraph()
        sp_p.paragraph_format.space_after = Pt(6)

    def _render_callout(self, doc, callout_text: str):
        """Renders a styled callout / highlight box."""
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, "F8FAFC")
        set_cell_margins(cell, top=100, bottom=100, left=160, right=160)

        # Left border highlight in primary color
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{HEX_PRIMARY}"/>'
            f'<w:top w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'<w:bottom w:val="none"/>'
            f'</w:tcBorders>'
        )
        cell._tc.get_or_add_tcPr().append(borders)

        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        tag = p.add_run("Executive Takeaway: ")
        tag.font.name = "Calibri"
        tag.font.size = Pt(9.5)
        tag.font.bold = True
        tag.font.color.rgb = COLOR_PRIMARY

        content = p.add_run(callout_text)
        content.font.name = "Calibri"
        content.font.size = Pt(9.5)
        content.font.italic = True
        content.font.color.rgb = COLOR_SECONDARY

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

document_service = DocumentService()
