"""Build the common editable practice report; refresh fields in Word afterwards."""

from __future__ import annotations

import argparse
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor


FONT = "Times New Roman"
BLACK = RGBColor(0, 0, 0)
CONTROL_ID = 100


def el(local_name, **attrs):
    node = OxmlElement("w:" + local_name)
    for key, value in attrs.items():
        node.set(qn("w:" + key), str(value))
    return node


def configure_style(style, size=14, *, bold=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
                    indent=12.5, line=1.5, caps=False, before=0, after=0):
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = BLACK
    style.font.all_caps = caps
    rpr = style.element.get_or_add_rPr()
    cs_size = rpr.find(qn("w:szCs"))
    if cs_size is not None:
        cs_size.set(qn("w:val"), str(size * 2))
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = el("rFonts")
        rpr.insert(0, fonts)
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn("w:" + key), FONT)
    for key in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn("w:" + key), None)
    lang = rpr.find(qn("w:lang"))
    if lang is None:
        rpr.append(el("lang", val="ru-RU"))
    pf = style.paragraph_format
    pf.alignment = align
    pf.first_line_indent = Mm(indent)
    pf.line_spacing = line
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    style.element.attrib.pop(qn("w:customStyle"), None)
    for item in list(style.element.findall(qn("w:autoRedefine"))):
        style.element.remove(item)


def new_style(doc, name, **kw):
    style = doc.styles[name] if name in doc.styles else doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = doc.styles["Normal"]
    configure_style(style, **kw)
    return style


def numbering(doc):
    root = doc.part.numbering_part.element
    aid = max([int(n.get(qn("w:abstractNumId"))) for n in root.findall(qn("w:abstractNum"))] + [0]) + 1
    nid = max([int(n.get(qn("w:numId"))) for n in root.findall(qn("w:num"))] + [0]) + 1
    abstract = el("abstractNum", abstractNumId=aid)
    abstract.append(el("multiLevelType", val="multilevel"))
    for level in range(3):
        item = el("lvl", ilvl=level)
        item.extend([el("start", val=1), el("numFmt", val="decimal"),
                     el("pStyle", val=f"Heading{level + 1}"),
                     el("lvlText", val=".".join(f"%{i + 1}" for i in range(level + 1)) + "."),
                     el("lvlJc", val="left"), el("suff", val="space")])
        item.append(el("pPr"))
        abstract.append(item)
    root.append(abstract)
    instance = el("num", numId=nid)
    instance.append(el("abstractNumId", val=aid))
    root.append(instance)
    for level in range(3):
        ppr = doc.styles[f"Heading {level + 1}"].element.get_or_add_pPr()
        prop = el("numPr")
        prop.extend([el("ilvl", val=level), el("numId", val=nid)])
        ppr.append(prop)


def text_control(paragraph, tag, label, text="____________________", *, multiline=False):
    global CONTROL_ID
    CONTROL_ID += 1
    control = el("sdt")
    props = el("sdtPr")
    props.extend([el("alias", val=label), el("tag", val=tag), el("id", val=CONTROL_ID),
                  el("text", multiLine="1" if multiline else "0")])
    content = el("sdtContent")
    run = el("r")
    run.append(el("t"))
    run[-1].text = text
    content.append(run)
    control.extend([props, content])
    paragraph._p.append(control)
    return control


def field(paragraph, code, cached="1", *, bookmark=None):
    if bookmark:
        paragraph._p.append(el("bookmarkStart", id=bookmark[0], name=bookmark[1]))
    for node in [el("fldChar", fldCharType="begin"), el("instrText"),
                 el("fldChar", fldCharType="separate"), el("t"),
                 el("fldChar", fldCharType="end")]:
        run = el("r")
        if node.tag == qn("w:instrText"):
            node.set(qn("xml:space"), "preserve")
            node.text = " " + code + " "
        if node.tag == qn("w:t"):
            node.text = cached
        run.append(node)
        paragraph._p.append(run)
    if bookmark:
        paragraph._p.append(el("bookmarkEnd", id=bookmark[0]))


def response(doc, label, tag, lines=2):
    p = doc.add_paragraph(style="Field label")
    p.add_run(label).bold = True
    for i in range(lines):
        p = doc.add_paragraph(style="Response")
        text_control(p, f"{tag}_{i + 1}", label, "____________________________________________________", multiline=True)


def heading(doc, text, level=1, *, new_page=False):
    p = doc.add_paragraph(text, style=f"Heading {level}")
    p.paragraph_format.page_break_before = new_page
    return p


def figure_slot(doc, label, tag, number, bookmark_name):
    p = doc.add_paragraph(label, style="Field label")
    p.paragraph_format.keep_with_next = True
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Mm(160)
    table.cell(0, 0).width = Mm(160)
    table.rows[0].height = Mm(60)
    table.rows[0].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    table.rows[0]._tr.get_or_add_trPr().append(el("cantSplit"))
    props = table._tbl.tblPr
    borders = el("tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        borders.append(el(side, val="single", sz=4, color="B7B7B7"))
    props.append(borders)
    margins = el("tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        margins.append(el(side, w=100, type="dxa"))
    props.append(margins)
    cell = table.cell(0, 0)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    p = cell.paragraphs[0]
    p.style = "Picture placeholder"
    p.paragraph_format.keep_with_next = True
    control = text_control(p, tag, label, "Вставить собственный рисунок")
    control.find(qn("w:sdtPr")).remove(control.find(qn("w:sdtPr")).find(qn("w:text")))
    p = doc.add_paragraph(style="Caption")
    p.add_run("Рисунок ")
    field(p, r"SEQ Рисунок \* ARABIC", str(number), bookmark=(number, bookmark_name))
    p.add_run(" — " + label)


def data_table(doc, title, number, labels, widths, tag, *, fixed_labels=None):
    p = doc.add_paragraph(style="Table caption")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.add_run("Таблица ")
    field(p, r"SEQ Таблица \* ARABIC", str(number))
    p.add_run(" — " + title)
    p.paragraph_format.keep_with_next = True
    table = doc.add_table(rows=4, cols=len(labels))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    borders = el("tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        borders.append(el(side, val="single", sz=4, color="B7B7B7"))
    table._tbl.tblPr.append(borders)
    margins = el("tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        margins.append(el(side, w=85, type="dxa"))
    table._tbl.tblPr.append(margins)
    for j, width in enumerate(widths):
        table.columns[j].width = Mm(width)
        for row in table.rows:
            row.cells[j].width = Mm(width)
    table.rows[0]._tr.get_or_add_trPr().append(el("tblHeader"))
    for i, row in enumerate(table.rows):
        row.height, row.height_rule = Mm(12), WD_ROW_HEIGHT_RULE.AT_LEAST
        row._tr.get_or_add_trPr().append(el("cantSplit"))
        for j, cell in enumerate(row.cells):
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            p.style = "Table text"
            if i == 0:
                p.add_run(labels[j]).bold = True
            elif fixed_labels and j == 0:
                p.add_run(fixed_labels[i - 1])
            else:
                text_control(p, f"{tag}_{i}_{j + 1}", labels[j], "____________", multiline=True)
    return table


def black_text(doc):
    """Use the report font and black text, including fields and list markers."""
    for name in ("Hyperlink", "FollowedHyperlink"):
        if name not in doc.styles:
            doc.styles.add_style(name, WD_STYLE_TYPE.CHARACTER, builtin=True)
        doc.styles[name].element.attrib.pop(qn("w:customStyle"), None)
    for style in doc.styles:
        rpr = style.element.get_or_add_rPr()
        if rpr.find(qn("w:color")) is None:
            rpr.append(el("color", val="000000"))
    defaults = doc.styles.element.find(qn("w:docDefaults"))
    if defaults is None:
        defaults = el("docDefaults")
        doc.styles.element.insert(0, defaults)
    rdefault = defaults.find(qn("w:rPrDefault"))
    if rdefault is None:
        rdefault = el("rPrDefault")
        defaults.append(rdefault)
    rpr = rdefault.find(qn("w:rPr"))
    if rpr is None:
        rpr = el("rPr")
        rdefault.append(rpr)
    if rpr.find(qn("w:color")) is None:
        rpr.append(el("color", val="000000"))
    for level in doc.part.numbering_part.element.iter(qn("w:lvl")):
        if level.find(qn("w:rPr")) is None:
            level.append(el("rPr"))
    for part in doc.part.package.parts:
        root = getattr(part, "element", None)
        if root is not None:
            for run in root.iter(qn("w:r")):
                if run.find(qn("w:rPr")) is None:
                    run.insert(0, el("rPr"))
            for props in root.iter(qn("w:rPr")):
                fonts = props.find(qn("w:rFonts"))
                if fonts is None:
                    fonts = el("rFonts")
                    props.insert(0, fonts)
                fonts.attrib.clear()
                for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                    fonts.set(qn("w:" + attr), FONT)
                if props.find(qn("w:color")) is None:
                    props.append(el("color", val="000000"))
            for color in root.iter(qn("w:color")):
                color.attrib.clear()
                color.set(qn("w:val"), "000000")


def build(output: Path):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.left_margin, sec.right_margin = Mm(30), Mm(20)
    sec.top_margin = sec.bottom_margin = Mm(20)
    sec.footer_distance = Mm(10)
    sec.different_first_page_header_footer = True
    configure_style(doc.styles["Normal"])
    configure_style(doc.styles["Title"], size=16, bold=True, caps=True, indent=0,
                    align=WD_ALIGN_PARAGRAPH.CENTER, after=16)
    # The bundled default template contains a blue border in its Title style.
    # A formal report has no decorative rule under its title.
    for border in list(doc.styles["Title"].element.get_or_add_pPr().findall(qn("w:pBdr"))):
        doc.styles["Title"].element.get_or_add_pPr().remove(border)
    for level in range(1, 4):
        configure_style(doc.styles[f"Heading {level}"], size=16 if level == 1 else 14,
                        bold=True, caps=level == 1, indent=0, before=12, after=8,
                        align=WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.JUSTIFY)
        doc.styles[f"Heading {level}"].paragraph_format.keep_with_next = True
    new_style(doc, "Cover field", indent=0, before=3, after=5)
    new_style(doc, "Field label", indent=0, before=9, after=2)
    new_style(doc, "Response", indent=12.5)
    new_style(doc, "Picture placeholder", size=12, indent=0, line=1,
              align=WD_ALIGN_PARAGRAPH.CENTER)
    configure_style(doc.styles["Caption"], size=12, indent=0, line=1,
                    align=WD_ALIGN_PARAGRAPH.CENTER, before=4, after=8)
    new_style(doc, "Table text", size=12, indent=0, line=1,
              align=WD_ALIGN_PARAGRAPH.CENTER)
    new_style(doc, "Table caption", size=12, indent=0, line=1,
              align=WD_ALIGN_PARAGRAPH.LEFT, before=10, after=5)
    configure_style(doc.styles["Footer"], size=12, indent=0, line=1,
                    align=WD_ALIGN_PARAGRAPH.CENTER)
    numbering(doc)
    settings = doc.settings.element
    settings.append(el("updateFields", val="true"))
    settings.append(el("doNotHyphenateCaps"))
    sec.footer.paragraphs[0].style = "Footer"
    field(sec.footer.paragraphs[0], "PAGE", "2")

    p = doc.add_paragraph(style="Cover field")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run('Университет "Синергия"')
    p.paragraph_format.space_after = Mm(26)
    doc.add_paragraph("Отчет о выполнении", style="Title")
    for tag, label in [("practice_name", "Название практики"),
                       ("student", "ФИО студента"), ("group", "Группа"),
                       ("variant", "Номер варианта"), ("domain", "Предметная область")]:
        p = doc.add_paragraph(style="Cover field")
        p.add_run(label + ": ")
        text_control(p, tag, label)

    heading(doc, "Исходные условия", new_page=True)
    data_table(doc, "предметная область и исходные материалы", 1,
               ["Сведения", "Данные своего варианта"], [65, 95], "inputs",
               fixed_labels=["Предметная область", "Исходные файлы и данные", "Стенд или источник данных"])
    data_table(doc, "среда выполнения и необходимые параметры", 2,
               ["Программа или компонент", "Версия", "Необходимые параметры"], [62, 30, 68], "environment")
    data_table(doc, "замены данных образца на данные своего варианта", 3,
               ["В образце", "В своём варианте", "Где используется"], [52, 56, 52], "mapping")

    heading(doc, "Выполнение и проверка", new_page=True)
    heading(doc, "Этап выполнения работы", level=2)
    response(doc, "Требуемое подтверждение выполнения этапа", "evidence", 2)
    response(doc, "Исходные данные и ожидаемый результат", "initial", 2)
    response(doc, "Выполненные действия", "actions", 3)
    response(doc, "Фактический результат и проверка", "actual", 2)
    response(doc, "Вывод по этапу и объяснение расхождений", "step_conclusion", 2)

    doc.add_page_break()
    p = doc.add_paragraph()
    p.add_run("Исходное состояние приведено на рис. ")
    field(p, r"REF fig_initial \h", "1")
    p.add_run(", полученный результат — на рис. ")
    field(p, r"REF fig_result \h", "2")
    p.add_run(".")
    figure_slot(doc, "Исходное состояние", "figure_initial", 1, "fig_initial")
    figure_slot(doc, "Результат выполнения", "figure_result", 2, "fig_result")

    heading(doc, "Итоговая проверка и сдача", new_page=True)
    data_table(doc, "итоговые результаты проверки", 4,
               ["Проверяемый результат", "Ожидаемый результат", "Фактический результат", "Вывод"],
               [43, 42, 43, 32], "check")
    response(doc, "Состав передаваемых материалов", "submission_files", 2)
    response(doc, "Ссылка на репозиторий проекта", "repository", 2)
    p = doc.add_paragraph("Указать полную ссылку, доступную проверяющему. Если репозиторий не предусмотрен заданием, указать это в поле.")
    response(doc, "Невыполненные требования и причины при наличии", "limitations", 2)

    properties = doc.core_properties
    properties.title = "Отчет о выполнении"
    properties.subject = "Учебная и производственная практика"
    properties.author = properties.last_modified_by = ""
    properties.comments = properties.keywords = ""
    black_text(doc)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    print(output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
