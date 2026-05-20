"""Сборка отчёта report.docx по ГОСТ 7.32-2017 о проекте VehicleLogger.

Запуск: python tools/build_report.py
Результат: report.docx в корне проекта.

Все стили заданы программно для соответствия ГОСТ 7.32-2017:
  Times New Roman 14 pt (12 для подписей и таблиц),
  межстрочный 1.5,
  поля 30/15/20/20 мм,
  абзацный отступ 1.25 см, выравнивание по ширине.
"""
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

from docx import Document
from docx.shared import Pt, Cm, Mm, Inches, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_BREAK
from docx.enum.section import WD_SECTION, WD_ORIENT
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsmap
from docx.oxml import OxmlElement
from docx.shared import Length

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "report.docx"
ABOUT = ROOT / "about"
PINOUT_IMG = ROOT / "firmware" / "temp_info" / "pin out live mini kit esp32.jpg"
TMP = ROOT / "tools" / "_report_tmp"
TMP.mkdir(parents=True, exist_ok=True)

FONT_MAIN = "Times New Roman"
SIZE_MAIN = Pt(14)
SIZE_SMALL = Pt(12)

# Счётчики (для подписей и реферата)
COUNTERS = {"figure": 0, "table": 0, "appendix": 0, "section": 0}

# Поле автоматического обновления (TOC), Word предложит обновить при открытии
def _xml(s):
    return OxmlElement(s)

def set_run_font(run, size=SIZE_MAIN, bold=False, italic=False):
    run.font.name = FONT_MAIN
    run.font.size = size
    run.font.bold = bold
    run.font.italic = italic
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(attr), FONT_MAIN)

def set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line=True,
                         line_spacing=1.5, space_after=0, space_before=0,
                         keep_with_next=False):
    pf = p.paragraph_format
    pf.alignment = align
    if first_line:
        pf.first_line_indent = Cm(1.25)
    else:
        pf.first_line_indent = Cm(0)
    pf.line_spacing = line_spacing
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    if keep_with_next:
        pPr = p._element.get_or_add_pPr()
        kwn = OxmlElement("w:keepNext")
        pPr.append(kwn)

def page_break(doc):
    p = doc.add_paragraph()
    r = p.add_run()
    r.add_break(WD_BREAK.PAGE)

def configure_page(doc):
    """Поля по ГОСТ 7.32-2017: 30 / 15 / 20 / 20 мм; A4 портрет."""
    for section in doc.sections:
        section.page_height = Mm(297)
        section.page_width = Mm(210)
        section.left_margin = Mm(30)
        section.right_margin = Mm(15)
        section.top_margin = Mm(20)
        section.bottom_margin = Mm(20)
        section.different_first_page_header_footer = True

def add_page_numbers(doc):
    """Нумерация страниц по центру нижнего поля. На первом листе номер не печатается."""
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    set_run_font(run, size=SIZE_SMALL)
    fldChar1 = OxmlElement("w:fldChar")
    fldChar1.set(qn("w:fldCharType"), "begin")
    instrText = OxmlElement("w:instrText")
    instrText.set(qn("xml:space"), "preserve")
    instrText.text = "PAGE   \\* MERGEFORMAT"
    fldChar2 = OxmlElement("w:fldChar")
    fldChar2.set(qn("w:fldCharType"), "end")
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    # На первой странице (титул) — без номера
    first_footer = section.first_page_footer
    first_p = first_footer.paragraphs[0] if first_footer.paragraphs else first_footer.add_paragraph()
    first_p.text = ""

def add_h1(doc, text, with_break=True, in_toc=True):
    """Заголовок раздела (прописными, по центру, полужирный, с разрывом перед)."""
    if with_break:
        page_break(doc)
    p = doc.add_paragraph()
    set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False,
                         space_before=0, space_after=12, keep_with_next=True)
    if in_toc:
        # Поле для оглавления — используем стиль "Heading 1" через outlineLvl
        pPr = p._element.get_or_add_pPr()
        outline = OxmlElement("w:outlineLvl")
        outline.set(qn("w:val"), "0")
        pPr.append(outline)
    r = p.add_run(text.upper())
    set_run_font(r, size=SIZE_MAIN, bold=True)
    return p

def add_h2(doc, text):
    """Подраздел: полужирный, с абзацного отступа, по левому краю."""
    p = doc.add_paragraph()
    set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, first_line=True,
                         space_before=6, space_after=6, keep_with_next=True)
    pPr = p._element.get_or_add_pPr()
    outline = OxmlElement("w:outlineLvl")
    outline.set(qn("w:val"), "1")
    pPr.append(outline)
    r = p.add_run(text)
    set_run_font(r, size=SIZE_MAIN, bold=True)
    return p

def add_h3(doc, text):
    """Пункт: полужирный, с абзацного отступа."""
    p = doc.add_paragraph()
    set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, first_line=True,
                         space_before=3, space_after=3, keep_with_next=True)
    pPr = p._element.get_or_add_pPr()
    outline = OxmlElement("w:outlineLvl")
    outline.set(qn("w:val"), "2")
    pPr.append(outline)
    r = p.add_run(text)
    set_run_font(r, size=SIZE_MAIN, bold=True)
    return p

def add_p(doc, text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line=True):
    """Обычный абзац."""
    p = doc.add_paragraph()
    set_paragraph_format(p, align=align, first_line=first_line)
    r = p.add_run(text)
    set_run_font(r, size=SIZE_MAIN)
    return p

def add_list_item(doc, text, level=0):
    p = doc.add_paragraph()
    set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line=False,
                         space_after=2)
    p.paragraph_format.left_indent = Cm(1.25 + 0.5 * level)
    r = p.add_run("— " + text)
    set_run_font(r, size=SIZE_MAIN)
    return p

def add_figure(doc, image_path, caption, width_cm=14.0):
    """Рисунок с подписью «Рисунок N — Название» снизу, по центру, 12 pt."""
    COUNTERS["figure"] += 1
    n = COUNTERS["figure"]
    if not Path(image_path).exists():
        return add_placeholder(doc, f"Рисунок {n} — {caption}",
                                f"ВСТАВИТЬ ИЗОБРАЖЕНИЕ: {Path(image_path).name}")
    pic_p = doc.add_paragraph()
    pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pic_p.paragraph_format.space_before = Pt(6)
    pic_p.paragraph_format.space_after = Pt(0)
    pic_p.paragraph_format.first_line_indent = Cm(0)
    run = pic_p.add_run()
    run.add_picture(str(image_path), width=Cm(width_cm))
    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_p.paragraph_format.space_before = Pt(2)
    cap_p.paragraph_format.space_after = Pt(8)
    cap_p.paragraph_format.first_line_indent = Cm(0)
    cr = cap_p.add_run(f"Рисунок {n} — {caption}")
    set_run_font(cr, size=SIZE_SMALL)
    return n

def add_placeholder(doc, title, description, height_cm=5.0):
    """Прямоугольная заглушка для будущего изображения."""
    COUNTERS["figure"] += 1
    n = COUNTERS["figure"]
    box = doc.add_paragraph()
    box.alignment = WD_ALIGN_PARAGRAPH.CENTER
    box.paragraph_format.space_before = Pt(6)
    box.paragraph_format.space_after = Pt(0)
    box.paragraph_format.first_line_indent = Cm(0)
    # Создаём таблицу 1x1 как прямоугольник
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tc = tbl.cell(0, 0)
    tc.width = Cm(14)
    tc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    # Высота
    tcPr = tc._tc.get_or_add_tcPr()
    trHeight = OxmlElement("w:trHeight")
    trHeight.set(qn("w:val"), str(int(height_cm * 567)))
    trHeight.set(qn("w:hRule"), "atLeast")
    tbl.rows[0]._tr.get_or_add_trPr().append(trHeight)
    # Серая заливка
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F2F2F2")
    tcPr.append(shd)
    tc.text = ""
    pp = tc.paragraphs[0]
    pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pp.paragraph_format.first_line_indent = Cm(0)
    r1 = pp.add_run("МЕСТО ДЛЯ ИЗОБРАЖЕНИЯ")
    set_run_font(r1, size=SIZE_SMALL, bold=True)
    pp2 = tc.add_paragraph()
    pp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pp2.paragraph_format.first_line_indent = Cm(0)
    r2 = pp2.add_run(description)
    set_run_font(r2, size=SIZE_SMALL, italic=True)
    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_p.paragraph_format.space_before = Pt(2)
    cap_p.paragraph_format.space_after = Pt(8)
    cap_p.paragraph_format.first_line_indent = Cm(0)
    cr = cap_p.add_run(f"Рисунок {n} — {title}")
    set_run_font(cr, size=SIZE_SMALL)
    return n

def add_table_caption(doc, caption):
    COUNTERS["table"] += 1
    n = COUNTERS["table"]
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.first_line_indent = Cm(0)
    r = p.add_run(f"Таблица {n} — {caption}")
    set_run_font(r, size=SIZE_SMALL)
    return n

def add_table(doc, headers, rows, caption, col_widths_cm=None):
    add_table_caption(doc, caption)
    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.style = "Light Grid Accent 1"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    if col_widths_cm:
        for col_idx, cw in enumerate(col_widths_cm):
            for cell in tbl.columns[col_idx].cells:
                cell.width = Cm(cw)
    # Заголовок
    for ci, h in enumerate(headers):
        cell = tbl.cell(0, ci)
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        r = p.add_run(h)
        set_run_font(r, size=SIZE_SMALL, bold=True)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    # Строки
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri + 1, ci)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.first_line_indent = Cm(0)
            r = p.add_run(str(val))
            set_run_font(r, size=SIZE_SMALL)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    # Пустой абзац после таблицы
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(6)
    spacer.paragraph_format.first_line_indent = Cm(0)
    return tbl

def add_toc_field(doc):
    """Поле «Содержание». При первом открытии Word предложит обновить — нажмите Да."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.first_line_indent = Cm(0)
    run = p.add_run()
    set_run_font(run, size=SIZE_MAIN)
    fldChar1 = OxmlElement("w:fldChar")
    fldChar1.set(qn("w:fldCharType"), "begin")
    instrText = OxmlElement("w:instrText")
    instrText.set(qn("xml:space"), "preserve")
    instrText.text = r'TOC \o "1-3" \h \z \u'
    fldChar2 = OxmlElement("w:fldChar")
    fldChar2.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:r")
    tx = OxmlElement("w:t")
    tx.text = "Содержание будет обновлено в Word: правой кнопкой → «Обновить поле»."
    placeholder.append(tx)
    fldChar3 = OxmlElement("w:fldChar")
    fldChar3.set(qn("w:fldCharType"), "end")
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run._r.append(placeholder)
    run._r.append(fldChar3)

# ─── Диаграммы через matplotlib ──────────────────────────────

def make_architecture_diagram(out_path):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 50)
    ax.axis("off")
    boxes = [
        (5,  20, 25, 18, "Устройство (ESP32)\n\nЧтение CAN-шины,\nGPS, инерциальный модуль", "#0A2540", "white"),
        (40, 20, 25, 18, "Серверная часть\n(.NET, SQLite)\n\nХранение данных,\nразграничение по компаниям", "#143D66", "white"),
        (75, 30, 22, 12, "Веб-панель\n(Vue 3)", "#F47C26", "white"),
        (75, 8,  22, 12, "Бот Telegram\n(в работе)", "#F47C26", "white"),
    ]
    for x, y, w, h, text, fill, fg in boxes:
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3",
                              linewidth=1.2, edgecolor=fill, facecolor=fill)
        ax.add_patch(box)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=10, color=fg, family="serif")
    # Стрелки
    arrows = [
        (30, 29, 40, 29, "Передача данных\n(HTTPS)"),
        (65, 32, 75, 36, ""),
        (65, 26, 75, 14, ""),
    ]
    for x1, y1, x2, y2, label in arrows:
        a = FancyArrowPatch((x1, y1), (x2, y2),
                             arrowstyle="-|>", mutation_scale=18,
                             linewidth=1.5, color="#0A2540")
        ax.add_patch(a)
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 2, label,
                    ha="center", fontsize=8, color="#0A2540", family="serif")
    plt.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

def make_auto_detect_diagram(out_path):
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 50)
    ax.axis("off")
    states = [
        (5,  20, 18, 12, "Старт\n500 кбит/с\nтолько приём", "#0A2540"),
        (40, 35, 18, 11, "J1939\nтолько приём", "#22A06B"),
        (75, 35, 20, 11, "OBD-II\nрежим передачи\nс запросами", "#F47C26"),
        (5,  3,  18, 11, "250 кбит/с\nтолько приём", "#0A2540"),
        (40, 3,  18, 11, "OBD-II\nпо умолчанию\n500 кбит/с", "#F47C26"),
    ]
    for x, y, w, h, text, fill in states:
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3",
                              linewidth=1.2, edgecolor=fill, facecolor=fill)
        ax.add_patch(box)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=9, color="white", family="serif")
    arrows = [
        (23, 26, 40, 38, "обнаружен 29-битный\nидентификатор"),
        (23, 23, 40, 8,  "3 секунды тишины"),
        (58, 40, 75, 40, "идут только\n11-битные кадры"),
        (23, 5,  40, 5,  "ещё 3 секунды\nтишины"),
    ]
    for x1, y1, x2, y2, label in arrows:
        a = FancyArrowPatch((x1, y1), (x2, y2),
                             arrowstyle="-|>", mutation_scale=16,
                             linewidth=1.3, color="#0A2540")
        ax.add_patch(a)
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 1.5, label,
                ha="center", fontsize=8, color="#0A2540", family="serif")
    plt.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

def make_boot_state_machine(out_path):
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set_xlim(0, 100); ax.set_ylim(0, 60)
    ax.axis("off")
    states = [
        (40, 50, 20, 8,  "Включение", "#0A2540"),
        (40, 35, 20, 8,  "Чтение настроек\nиз энергонезависимой\nпамяти", "#143D66"),
        (5,  18, 24, 10, "Режим точки доступа\n(первичная настройка)", "#F47C26"),
        (40, 18, 20, 10, "Подключение\nк сети WiFi", "#143D66"),
        (70, 18, 25, 10, "Рабочий режим:\nпередача данных", "#22A06B"),
        (5,  3,  90, 7,  "при потере связи 401/410 → возврат к точке доступа", "#D9474F"),
    ]
    for x, y, w, h, text, fill in states:
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3",
                              linewidth=1.2, edgecolor=fill, facecolor=fill)
        ax.add_patch(box)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=9, color="white", family="serif")
    arrows = [
        (50, 50, 50, 43, ""),
        (40, 39, 17, 28, "сети нет"),
        (50, 35, 50, 28, "сеть и ключ есть"),
        (60, 39, 82, 28, ""),
        (29, 22, 40, 22, "после ввода\nданных"),
        (60, 22, 70, 22, "получен ключ"),
    ]
    for x1, y1, x2, y2, label in arrows:
        a = FancyArrowPatch((x1, y1), (x2, y2),
                             arrowstyle="-|>", mutation_scale=14,
                             linewidth=1.2, color="#0A2540")
        ax.add_patch(a)
        if label:
            ax.text((x1 + x2) / 2 + 1, (y1 + y2) / 2 + 0.5, label,
                    ha="center", fontsize=8, color="#0A2540", family="serif")
    plt.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

# ─── Титульный лист ──────────────────────────────────────────

def render_title(doc):
    # Верхняя часть
    for text, size, bold, align in [
        ("Министерство образования и науки Российской Федерации", 14, False, WD_ALIGN_PARAGRAPH.CENTER),
        ("Образовательное учреждение", 14, False, WD_ALIGN_PARAGRAPH.CENTER),
        ("Кафедра ____________________________________________", 14, False, WD_ALIGN_PARAGRAPH.CENTER),
    ]:
        p = doc.add_paragraph()
        set_paragraph_format(p, align=align, first_line=False, space_after=4)
        r = p.add_run(text)
        set_run_font(r, size=Pt(size), bold=bold)
    # Центр: «ОТЧЁТ»
    for _ in range(6):
        sp = doc.add_paragraph()
        sp.paragraph_format.first_line_indent = Cm(0)
    p = doc.add_paragraph()
    set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, space_after=4)
    r = p.add_run("ОТЧЁТ")
    set_run_font(r, size=Pt(20), bold=True)
    p = doc.add_paragraph()
    set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, space_after=12)
    r = p.add_run("о выполненной работе по проекту")
    set_run_font(r, size=Pt(14))
    p = doc.add_paragraph()
    set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, space_after=4)
    r = p.add_run("VehicleLogger — система мониторинга состояния")
    set_run_font(r, size=Pt(18), bold=True)
    p = doc.add_paragraph()
    set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, space_after=4)
    r = p.add_run("коммерческого транспорта в реальном времени")
    set_run_font(r, size=Pt(18), bold=True)
    for _ in range(6):
        sp = doc.add_paragraph()
        sp.paragraph_format.first_line_indent = Cm(0)
    # Нижняя часть — таблица для подписей
    tbl = doc.add_table(rows=4, cols=2)
    tbl.autofit = False
    tbl.alignment = WD_TABLE_ALIGNMENT.RIGHT
    tbl.columns[0].width = Cm(6)
    tbl.columns[1].width = Cm(10)
    rows = [
        ("Выполнили:", "_____________________________"),
        ("",           "_____________________________"),
        ("Руководитель:", "_____________________________"),
        ("Оценка:",     "_____________________________"),
    ]
    for ri, (a, b) in enumerate(rows):
        for ci, txt in enumerate((a, b)):
            cell = tbl.cell(ri, ci)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.first_line_indent = Cm(0)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if ci == 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(txt)
            set_run_font(r, size=Pt(14))
    # Город и год — внизу
    for _ in range(6):
        sp = doc.add_paragraph()
        sp.paragraph_format.first_line_indent = Cm(0)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    r = p.add_run(f"Город · {datetime.now().year}")
    set_run_font(r, size=Pt(14))

# ─── Реферат ─────────────────────────────────────────────────

def render_abstract(doc):
    add_h1(doc, "Реферат")
    add_p(doc,
        "Отчёт содержит описание проектирования и реализации системы мониторинга состояния "
        "коммерческого транспорта в реальном времени. Система состоит из бортового устройства "
        "на микроконтроллере ESP32, серверной части на платформе .NET и веб-панели на каркасе "
        "Vue 3. Бортовое устройство снимает данные с автомобильной шины передачи данных и через "
        "беспроводную сеть передаёт их на сервер. Сервер хранит и обрабатывает данные, выдаёт "
        "их веб-панели для отображения. Архитектура поддерживает работу нескольких компаний на "
        "одной установке за счёт выделения каждой компании своего поддомена.")
    add_p(doc,
        "Ключевые слова: бортовое устройство, ESP32, шина передачи данных, SAE J1939, OBD-II, "
        "телеметрия, мультиарендность, поддомен, защищённое соединение, прошивка.")
    add_p(doc,
        "Объект работы — программно-аппаратный комплекс мониторинга транспорта. Предмет — "
        "методы автоматического определения протокола обмена с электронным блоком автомобиля и "
        "способы безопасной привязки устройства к учётной записи компании-владельца.")
    add_p(doc,
        "В ходе работы разработаны: схема подключения комплектующих, прошивка устройства с "
        "автоматическим определением скорости и протокола шины, программа первичной настройки "
        "через локальную точку доступа, серверная часть со схемой данных и набором программных "
        "интерфейсов, веб-панель для администратора компании. Проверена работоспособность "
        "системы на стенде с анализатором шины и эмулятором электронного блока автомобиля.")

# ─── Перечень сокращений ─────────────────────────────────────

def render_abbreviations(doc):
    add_h1(doc, "Перечень сокращений и обозначений")
    add_p(doc, "В отчёте используются следующие сокращения и обозначения:", first_line=False)
    rows = [
        ("CAN", "Controller Area Network — шина передачи данных в автомобиле, последовательная сеть передачи коротких сообщений между электронными блоками управления"),
        ("DTC", "Diagnostic Trouble Code — код неисправности, формируемый электронным блоком управления"),
        ("ESP32", "Микроконтроллер с двумя ядрами и встроенным беспроводным приёмопередатчиком; используется в бортовом устройстве"),
        ("I²C", "Двухпроводный последовательный интерфейс для связи между микросхемами на одной плате"),
        ("ISO 15765-4", "Международный стандарт, описывающий применение CAN для бортовой диагностики легковых автомобилей"),
        ("MAC", "Media Access Control — уникальный идентификатор сетевого устройства"),
        ("NTP", "Network Time Protocol — сетевой протокол точного времени"),
        ("NVS", "Non-Volatile Storage — энергонезависимая память микроконтроллера для хранения настроек"),
        ("OBD-II", "On-Board Diagnostics II — стандарт бортовой диагностики легковых автомобилей"),
        ("PGN", "Parameter Group Number — номер группы параметров в стандарте SAE J1939"),
        ("PID", "Parameter Identifier — идентификатор измеряемого параметра в стандарте OBD-II"),
        ("REST", "Representational State Transfer — архитектурный стиль построения программных интерфейсов на основе протокола HTTP"),
        ("RSSI", "Received Signal Strength Indicator — уровень принимаемого сигнала беспроводной сети, дБм"),
        ("SAE J1939", "Стандарт сети передачи данных, применяемый на грузовых автомобилях"),
        ("SPN", "Suspect Parameter Number — номер контролируемого параметра в стандарте SAE J1939"),
        ("TWAI", "Two-Wire Automotive Interface — название встроенного контроллера CAN в микроконтроллере ESP32"),
        ("UART", "Universal Asynchronous Receiver-Transmitter — последовательный интерфейс асинхронной передачи данных"),
    ]
    tbl = doc.add_table(rows=len(rows), cols=2)
    tbl.style = "Light Grid Accent 1"
    tbl.autofit = False
    for r_idx, (k, v) in enumerate(rows):
        c1 = tbl.cell(r_idx, 0); c1.width = Cm(3.5); c1.text = ""
        p = c1.paragraphs[0]; p.paragraph_format.first_line_indent = Cm(0)
        rk = p.add_run(k); set_run_font(rk, size=SIZE_SMALL, bold=True)
        c2 = tbl.cell(r_idx, 1); c2.width = Cm(13); c2.text = ""
        p2 = c2.paragraphs[0]; p2.paragraph_format.first_line_indent = Cm(0)
        rv = p2.add_run(v); set_run_font(rv, size=SIZE_SMALL)

# ─── Введение ────────────────────────────────────────────────

def render_intro(doc):
    add_h1(doc, "Введение")
    add_p(doc,
        "Современный автомобильный транспорт оснащён множеством электронных блоков управления, "
        "обменивающихся сообщениями по внутренней шине передачи данных. Чтение этих сообщений "
        "позволяет в реальном времени узнавать состояние двигателя, скорость, расход топлива, "
        "напряжение бортовой сети, а также активные коды неисправностей. На этом построены "
        "промышленные системы телематики, применяемые в управлении автопарками.")
    add_p(doc,
        "Импортные системы телематики дороги в обслуживании и в условиях ограниченного доступа "
        "к иностранному программному обеспечению становятся менее доступными. Поэтому стоит "
        "задача создания собственной системы мониторинга, построенной на доступных "
        "комплектующих и открытом программном обеспечении.")
    add_h2(doc, "Актуальность темы")
    add_p(doc,
        "На российском рынке коммерческого транспорта эксплуатируется около полутора миллионов "
        "грузовых автомобилей. По экспертным оценкам, средствами телематики оснащено менее "
        "четверти из них. Себестоимость комплектующих для собственного бортового устройства "
        "оказывается в несколько раз ниже стоимости коробочных решений, что делает разработку "
        "целесообразной.")
    add_h2(doc, "Цель работы")
    add_p(doc,
        "Разработать программно-аппаратный комплекс для сбора, передачи и отображения данных "
        "о состоянии транспортного средства, способный обслуживать несколько независимых "
        "компаний на одной установке.")
    add_h2(doc, "Задачи работы")
    for t in [
        "Изучить применяемые в автомобилях протоколы обмена данными и выбрать применимый набор параметров для мониторинга.",
        "Подобрать комплектующие и составить схему подключения бортового устройства.",
        "Разработать прошивку устройства с поддержкой грузовых и легковых автомобилей, с автоматическим определением протокола обмена.",
        "Разработать процедуру первичной настройки устройства, безопасную против ошибок установщика.",
        "Разработать серверную часть с разграничением данных по компаниям и веб-панель для отображения данных.",
        "Провести стендовые испытания и подтвердить работоспособность системы.",
    ]:
        add_list_item(doc, t)
    add_h2(doc, "Объект и предмет работы")
    add_p(doc,
        "Объект работы — программно-аппаратный комплекс мониторинга транспорта. Предмет — "
        "методы автоматического распознавания протокола обмена с автомобильной шиной и способы "
        "безопасной привязки устройства к учётной записи компании-владельца с защитой от "
        "ошибок при установке.")

# ─── Раздел 1. Общее описание системы ─────────────────────────

def render_section1(doc):
    add_h1(doc, "1 Общее описание системы")

    add_h2(doc, "1.1 Назначение системы и решаемые задачи")
    add_p(doc,
        "Система предназначена для непрерывного сбора данных о состоянии транспортного "
        "средства, передачи этих данных на сервер и отображения их сотруднику компании-"
        "владельца. Система решает следующие задачи:")
    for t in [
        "снятие основных параметров двигателя и движения — оборотов, скорости, температуры охлаждающей жидкости, давления масла, уровня топлива, напряжения бортовой сети;",
        "снятие активных кодов неисправностей электронного блока управления;",
        "определение местоположения и скорости транспортного средства с помощью спутниковой навигации;",
        "регистрация резких манёвров и ударов с помощью инерциального модуля;",
        "передача собранных данных на сервер по защищённому каналу;",
        "отображение данных сотруднику компании в виде графиков и таблиц;",
        "разграничение доступа: каждая компания видит только свои транспортные средства.",
    ]:
        add_list_item(doc, t)

    add_h2(doc, "1.2 Принцип работы и архитектура")
    add_p(doc,
        "Система состоит из трёх независимых компонентов, взаимодействующих между собой через "
        "набор программных интерфейсов. Бортовое устройство в кабине транспортного средства "
        "снимает данные и периодически передаёт их на сервер. Сервер хранит данные в базе и "
        "выдаёт их по запросу веб-панели. Сотрудник компании работает с веб-панелью через "
        "браузер.")
    arch_path = TMP / "arch.png"
    make_architecture_diagram(arch_path)
    add_figure(doc, arch_path, "Общая архитектура системы", width_cm=15)
    add_p(doc,
        "Особенностью архитектуры является поддержка работы нескольких компаний на одной "
        "установке. Каждая компания получает собственный поддомен на сайте сервиса; данные "
        "разных компаний хранятся в общей базе, но разграничиваются на уровне адресов веб-"
        "сайта и программных интерфейсов.")

    add_h2(doc, "1.3 Состав системы и распределение функций")
    rows = [
        ("Бортовое устройство", "Чтение CAN-шины (грузовик и легковой автомобиль), снятие "
         "координат и параметров движения, периодическая передача данных на сервер."),
        ("Сервер", "Приём данных от устройств, хранение, выдача по запросу, выдача программных "
         "интерфейсов для веб-панели, разграничение по компаниям."),
        ("Веб-панель", "Отображение данных в виде графиков и таблиц, управление устройствами и "
         "транспортными средствами, выдача кодов для привязки новых устройств."),
        ("Бот в мессенджере", "Уведомление водителя об отклонениях, ввод данных о заправках "
         "(этап в работе)."),
    ]
    add_table(doc, ["Компонент", "Функции"], rows, "Состав системы и распределение функций",
              col_widths_cm=[5, 11])

    add_figure(doc, ABOUT / "photo_2026-03-29_21-40-13.jpg",
               "Общий вид окна веб-дашборда тестового стенда firmware-test "
               "(акселерометр, гироскоп, спутниковая навигация, состояние шины передачи данных)",
               width_cm=15)

# ─── Раздел 2. Аппаратное обеспечение ─────────────────────────

def render_section2(doc):
    add_h1(doc, "2 Аппаратное обеспечение")

    add_h2(doc, "2.1 Микроконтроллер ESP32")
    add_p(doc,
        "Основу бортового устройства составляет модуль ESP-WROOM-32 на микроконтроллере "
        "ESP32. Микроконтроллер выбран по совокупности характеристик: два процессорных ядра "
        "архитектуры Xtensa с тактовой частотой до 240 МГц, 520 КБ оперативной памяти, "
        "встроенный беспроводной приёмопередатчик стандарта IEEE 802.11 b/g/n, встроенный "
        "контроллер CAN (в документации производителя именуется TWAI), большое число свободно "
        "программируемых выводов. По сравнению с младшей моделью ESP32-C3, указанной в "
        "исходной спецификации проекта, выбранная модель располагает большим числом выводов и "
        "двумя интерфейсами UART, что важно для подключения дополнительных датчиков.")

    add_figure(doc, ABOUT / "photo_2026-05-03_22-31-55.jpg",
               "Комплектующие до сборки: микроконтроллер ESP32 (две модификации платы), "
               "преобразователь сигналов CAN-шины, инерциальный модуль, модуль спутниковой "
               "навигации",
               width_cm=10)

    add_h2(doc, "2.2 Преобразователь сигналов автомобильной шины")
    add_p(doc,
        "Микроконтроллер ESP32 содержит логический контроллер CAN, однако работа с физическим "
        "уровнем шины требует отдельной микросхемы-преобразователя. В проекте используется "
        "модуль WCMCU-230 на микросхеме SN65HVD230, преобразующий логические уровни 3,3 В "
        "микроконтроллера в дифференциальные сигналы CAN-шины. Модуль работает в широком "
        "диапазоне скоростей (от 1 Кбит/с до 1 Мбит/с), что покрывает применяемые в "
        "автомобилях скорости 250 и 500 Кбит/с.")
    add_p(doc,
        "В ходе работы выяснилось, что часть модулей с маркировкой WCMCU-230, приобретённых на "
        "электронном рынке, содержит контрафактные микросхемы или микросхемы с другим режимом "
        "работы. Такие модули не позволяют выйти из состояния повышенной частоты ошибок и "
        "блокируют передачу. Решение этой проблемы описано в разделе 7.")

    add_h2(doc, "2.3 Модуль спутниковой навигации")
    add_p(doc,
        "Для определения координат и скорости движения используется модуль GY-GPSV3-NEO-M8N на "
        "приёмнике u-blox NEO-M8N. Модуль поддерживает работу с несколькими спутниковыми "
        "системами одновременно (GPS, ГЛОНАСС, Galileo, BeiDou), что повышает устойчивость "
        "определения координат в условиях ограниченного обзора. Модуль выдаёт данные в "
        "стандартном формате NMEA-0183 по интерфейсу UART.")

    add_h2(doc, "2.4 Инерциальный модуль")
    add_p(doc,
        "Для регистрации резких манёвров и ударов используется модуль MPU-6050. Модуль содержит "
        "трёхосевой акселерометр и трёхосевой гироскоп, передающий данные по интерфейсу I²C. "
        "По мгновенному ускорению можно судить о резком торможении и ударе, по угловой "
        "скорости — о манёвре с заносом.")

    add_h2(doc, "2.5 Схема подключения и распределение выводов")
    add_p(doc,
        "Распределение выводов микроконтроллера выполнено с учётом физического расположения "
        "выводов на используемой плате-носителе LIVE MINI KIT ESP32 (см. рисунок ниже). Каждый "
        "сенсор подключён по своему интерфейсу, что исключает конфликты на шинах.")
    add_figure(doc, PINOUT_IMG,
               "Расположение выводов платы-носителя LIVE MINI KIT ESP32",
               width_cm=9)
    rows = [
        ("GPIO 22", "WCMCU-230 CTX", "Передача в CAN-шину"),
        ("GPIO 21", "WCMCU-230 CRX", "Приём из CAN-шины"),
        ("GPIO 16", "NEO-M8N TX",   "Приём данных от модуля навигации (UART2)"),
        ("GPIO 17", "NEO-M8N RX",   "Передача в модуль навигации (UART2)"),
        ("GPIO 18", "MPU-6050 SDA", "Линия данных I²C"),
        ("GPIO 19", "MPU-6050 SCL", "Линия тактирования I²C"),
        ("GPIO 0",  "Кнопка BOOT",  "Удержание 5 с — сброс настроек беспроводной сети; 10 с — заводской сброс"),
        ("GPIO 2",  "Встроенный светодиод", "Индикация состояния устройства"),
        ("3,3 В",   "Питание модулей", "Общая шина питания"),
        ("GND",     "Общий провод", "Общая шина земли"),
    ]
    add_table(doc, ["Вывод", "Подключение", "Назначение"], rows,
              "Распределение выводов микроконтроллера ESP32",
              col_widths_cm=[2.5, 4.5, 9])
    add_figure(doc, ABOUT / "photo_2026-03-29_00-12-27.jpg",
               "Собранное устройство: микроконтроллер, преобразователь CAN-шины, "
               "модуль навигации с антенной",
               width_cm=10)

# ─── Раздел 3. Программное обеспечение устройства ─────────────

def render_section3(doc):
    add_h1(doc, "3 Программное обеспечение устройства")

    add_h2(doc, "3.1 Среда разработки")
    add_p(doc,
        "Прошивка устройства разрабатывается в среде PlatformIO на базе каркаса Arduino-ESP32. "
        "PlatformIO выбран потому что упрощает управление зависимостями (внешние библиотеки "
        "подключаются записью в конфигурационном файле), позволяет хранить файлы веб-страниц "
        "во встроенной файловой системе устройства и поддерживает сборку из командной строки. "
        "Каркас Arduino-ESP32 над встроенной операционной системой FreeRTOS, что снимает с "
        "разработчика обязанность управления потоками.")
    add_p(doc,
        "Используются библиотеки: ESPAsyncWebServer и AsyncTCP — для веб-сервера первичной "
        "настройки; ArduinoJson — для разбора и формирования сообщений в формате JSON; "
        "TinyGPSPlus — для разбора сообщений модуля навигации в формате NMEA. Стандартные "
        "библиотеки каркаса используются для работы с беспроводной сетью, защищённым "
        "соединением, энергонезависимой памятью, встроенной файловой системой, шиной I²C и "
        "контроллером CAN.")

    add_h2(doc, "3.2 Чтение данных автомобильной шины")
    add_p(doc,
        "В автомобильной шине применяются два разных протокола, различающихся по формату "
        "сообщений и по модели взаимодействия. Прошивка поддерживает оба и автоматически "
        "определяет, какой используется в подключённом автомобиле.")

    add_h3(doc, "3.2.1 Протокол грузовых автомобилей SAE J1939")
    add_p(doc,
        "Стандарт SAE J1939 применяется на грузовых автомобилях, автобусах и сельскохозяйственной "
        "технике. Сообщения передаются по шине широковещательно — каждый электронный блок "
        "управления отправляет свои данные с заданной периодичностью, без явного запроса. "
        "Идентификатор сообщения имеет длину 29 бит и включает в себя приоритет, номер группы "
        "параметров и адрес отправителя. Содержание сообщения формируется из 8 байт данных, "
        "разбираемых на отдельные параметры по утверждённой стандартом схеме.")
    add_p(doc,
        "В прошивке устройства реализован разбор десяти основных групп параметров, "
        "перечисленных в таблице ниже. Параметры записываются в общую структуру данных "
        "автомобиля, к каждому полю прикладывается отметка времени последнего обновления — "
        "это позволяет на стороне сервера и веб-панели отличать актуальные данные от "
        "устаревших.")
    rows = [
        ("61444", "EEC1",  "Обороты двигателя",                     "0,125 об/мин"),
        ("65265", "CCVS",  "Скорость движения",                     "1/256 км/ч"),
        ("65262", "ET1",   "Температура охлаждающей жидкости",       "1 °C, смещение −40"),
        ("65263", "EFLP1", "Давление масла, уровень топлива",        "4 кПа / 0,4 %"),
        ("65271", "EP1",   "Напряжение бортовой сети",               "0,05 В"),
        ("65266", "LFE",   "Расход топлива",                         "0,05 л/ч"),
        ("61443", "EEC2",  "Нагрузка двигателя",                     "1 %"),
        ("65248", "VD",    "Общий пробег",                           "0,125 км"),
        ("65253", "HOURS", "Моточасы двигателя",                     "0,05 ч"),
        ("65226", "DM1",   "Активные коды неисправностей",           "—"),
    ]
    add_table(doc, ["Номер группы", "Имя", "Параметр", "Цена единицы"], rows,
              "Группы параметров стандарта SAE J1939, разбираемые прошивкой",
              col_widths_cm=[2.5, 2.0, 8.0, 3.5])

    add_h3(doc, "3.2.2 Протокол легковых автомобилей OBD-II")
    add_p(doc,
        "Стандарт OBD-II применяется на легковых автомобилях, выпущенных с 2008 года и позже. "
        "В отличие от SAE J1939 электронные блоки управления не передают данные сами, а "
        "отвечают на запросы. Идентификатор сообщения имеет длину 11 бит, скорость шины — "
        "500 Кбит/с. Запрос отправляется на широковещательный адрес 0x7DF и содержит код "
        "режима и идентификатор запрашиваемого параметра. Ответ приходит на идентификаторы из "
        "диапазона 0x7E8–0x7EF, в зависимости от того, какой блок отвечает.")
    add_p(doc,
        "В прошивке реализован опрос семи параметров режима 1 «Текущие данные». Опрос идёт по "
        "очереди — устройство по очереди запрашивает каждый из параметров и ждёт ответа. "
        "Период опроса задан в сто миллисекунд, что даёт обновление каждого параметра "
        "примерно семь раз в секунду — достаточно для построения графиков и оценки динамики "
        "движения.")
    rows = [
        ("0x04", "Нагрузка двигателя",          "A × 100 / 255",      "%"),
        ("0x05", "Температура охлаждающей жидкости", "A − 40",        "°C"),
        ("0x0C", "Обороты двигателя",            "(A × 256 + B) / 4",  "об/мин"),
        ("0x0D", "Скорость движения",            "A",                   "км/ч"),
        ("0x2F", "Уровень топлива",              "A × 100 / 255",       "%"),
        ("0x42", "Напряжение бортовой сети",     "(A × 256 + B) / 1000","В"),
        ("0x5E", "Расход топлива",                "(A × 256 + B) / 20", "л/ч"),
    ]
    add_table(doc, ["Идентификатор", "Параметр", "Формула расчёта", "Единица"], rows,
              "Параметры режима 1 стандарта OBD-II, опрашиваемые прошивкой",
              col_widths_cm=[3.5, 5.0, 5.0, 2.5])

    add_h3(doc, "3.2.3 Автоматическое определение скорости и протокола")
    add_p(doc,
        "Перед началом работы устройство не знает, к какому автомобилю оно подключено. Для "
        "определения скорости шины и применяемого протокола реализована схема состояний, "
        "показанная на рисунке ниже. Принцип работы такой: устройство сначала подключается "
        "к шине в режиме «только приём» на скорости 500 Кбит/с (наиболее частая для легковых "
        "автомобилей) и три секунды слушает. Если за это время приходят сообщения с 29-битным "
        "идентификатором — значит автомобиль использует SAE J1939, и устройство остаётся в "
        "режиме приёма. Если приходят только сообщения с 11-битным идентификатором — это "
        "OBD-II, и устройство переключается в режим «приём с подтверждением» для отправки "
        "запросов. Если за три секунды ничего не приходит, устройство переключается на "
        "скорость 250 Кбит/с и ещё три секунды слушает — это покроет грузовые автомобили, на "
        "которых работает SAE J1939. Если и здесь тишина, устройство возвращается на скорость "
        "500 Кбит/с и переходит в режим запросов по OBD-II — это поведение применяется "
        "для автомобилей с электронным блоком, отвечающим только по запросу.")
    diag_path = TMP / "auto_detect.png"
    make_auto_detect_diagram(diag_path)
    add_figure(doc, diag_path, "Схема автоматического определения скорости и протокола шины", width_cm=15)

    add_h2(doc, "3.3 Первичная настройка устройства")

    add_h3(doc, "3.3.1 Точка доступа на устройстве")
    add_p(doc,
        "При первом включении устройство не имеет данных о беспроводной сети, к которой надо "
        "подключиться. В этом случае оно создаёт собственную точку доступа с именем "
        "«VehicleLogger-XXXXXXXX», где XXXXXXXX — последние восемь шестнадцатеричных символов "
        "уникального идентификатора микроконтроллера. Пароль точки доступа фиксирован и "
        "наносится на корпус устройства. Установщик подключает к этой точке смартфон, после "
        "чего в браузере открывается страница первичной настройки.")
    add_p(doc,
        "Точка доступа сопровождается своим сервером доменных имён, отвечающим на любые "
        "запросы адресом самого устройства. Это вынуждает любые попытки браузера обратиться к "
        "сторонним сайтам перенаправляться на страницу настройки. Подобная схема, известная "
        "под названием «страница принудительной встречи», часто используется в публичных "
        "беспроводных сетях.")

    add_h3(doc, "3.3.2 Веб-страница ввода параметров")
    add_p(doc,
        "Веб-страница содержит четыре поля для ввода. Имя беспроводной сети выбирается из "
        "выпадающего списка, формируемого автоматическим сканированием эфира. Пароль "
        "указывается обычным полем ввода. Поддомен компании и шестизначный код привязки "
        "выдаются администратором компании заранее.")
    add_figure(doc, ABOUT / "photo_2026-05-03_23-14-30.jpg",
               "Внешний вид страницы первичной настройки в браузере смартфона",
               width_cm=8)

    add_h3(doc, "3.3.3 Передача параметров на сервер и обработка ошибок")
    add_p(doc,
        "После нажатия кнопки «Подключить и привязать» устройство сначала пробует подключиться "
        "к указанной беспроводной сети. При неуспехе об этом сообщается на той же странице "
        "настройки, без сохранения параметров. При успешном подключении формируется запрос "
        "на сервер по адресу указанного поддомена. В теле запроса передаются: серийный номер "
        "устройства, заводской секрет (256 бит, шестнадцатеричной строкой), шестизначный код "
        "привязки. Сервер проверяет все три значения и при успехе возвращает уникальный ключ "
        "доступа, который устройство сохраняет в энергонезависимой памяти.")
    rows = [
        ("200", "Привязка выполнена",          "Сохранить полученный ключ, перезагрузиться в рабочий режим"),
        ("400", "Неверный или просроченный код","Сообщить установщику, остаться в режиме настройки"),
        ("403", "Неверный секрет или чужая компания", "Сообщить о повреждении заводских данных"),
        ("404", "Поддомен или устройство не найдены", "Сообщить установщику, проверить введённый поддомен"),
        ("409", "Устройство уже привязано", "Требуется отвязка администратором текущей компании"),
        ("410", "Устройство снято с обслуживания", "Прекратить попытки привязки"),
    ]
    add_table(doc, ["Код ответа", "Значение", "Действие устройства"], rows,
              "Коды ответа сервера на запрос привязки и реакция устройства",
              col_widths_cm=[2.5, 6, 8])

    add_h2(doc, "3.4 Рабочий режим")

    add_h3(doc, "3.4.1 Подключение к беспроводной сети")
    add_p(doc,
        "В рабочем режиме устройство автоматически подключается к сохранённой беспроводной "
        "сети. При потере связи прошивка повторяет попытки подключения; после пятой неудачной "
        "попытки подряд устройство сохраняет ключ доступа, но возвращается в режим точки "
        "доступа, чтобы установщик мог ввести параметры новой сети. Сами параметры доступа к "
        "серверу при этом сохраняются — повторная привязка не требуется.")

    add_h3(doc, "3.4.2 Передача данных о состоянии автомобиля")
    add_p(doc,
        "Данные передаются на сервер каждые пять секунд (период задаётся сервером при привязке "
        "и может быть скорректирован). Запрос отправляется методом POST по адресу "
        "/api/telemetry. В заголовке передаётся ключ доступа в формате «Authorization: Bearer "
        "ХХХХХ». Тело запроса формируется в формате JSON и содержит идентификатор устройства, "
        "временную метку и объект с актуальными значениями параметров.")
    add_p(doc,
        "Временная метка формируется во всемирном координированном времени, по стандарту ISO "
        "8601 с буквой Z на конце. Время устройство получает по сетевому протоколу точного "
        "времени NTP при первом подключении к сети и периодически синхронизирует. Это важно: "
        "без корректного времени сервер посчитает данные устаревшими и не отобразит их.")

    add_h3(doc, "3.4.3 Поддержание соединения и обработка отказов")
    add_p(doc,
        "Помимо передачи данных, устройство раз в минуту отправляет на сервер короткое "
        "сообщение поддержания связи — это позволяет серверу различать рабочее устройство и "
        "устройство в режиме сна. Сервер может в любой момент вернуть код 401, означающий "
        "что ключ доступа отозван, или код 410 — устройство снято с обслуживания. В обоих "
        "случаях прошивка стирает ключ доступа из памяти и возвращается в режим точки "
        "доступа: дальнейшая работа требует новой привязки с новым шестизначным кодом от "
        "администратора компании.")

# ─── Раздел 4. Серверная часть ────────────────────────────────

def render_section4(doc):
    add_h1(doc, "4 Серверная часть")

    add_h2(doc, "4.1 Программная платформа и база данных")
    add_p(doc,
        "Серверная часть выполнена на платформе .NET 10 с применением каркаса ASP.NET Core. "
        "Эта платформа выбрана за наличие готовых средств работы с программными интерфейсами, "
        "за развитую систему авторизации и за высокую скорость разработки. В качестве "
        "системы управления базами данных в прототипе используется встроенная база SQLite, "
        "обслуживаемая через библиотеку Entity Framework Core. В промышленной эксплуатации "
        "база может быть заменена на PostgreSQL без изменения кода — каркас Entity Framework "
        "Core поддерживает несколько систем управления базами данных через настройку.")

    add_h2(doc, "4.2 Архитектура мультиарендности через поддомены")
    add_p(doc,
        "Многоарендность в системе реализована через выделение каждой компании собственного "
        "поддомена базового адреса. Например, компания «АКМЕ» получает поддомен «acme.домен», "
        "компания «Вольво» — «volvo.домен». Сервер принимает входящие запросы на все "
        "поддомены и по значению заголовка Host определяет, к данным какой компании "
        "относится запрос.")
    add_p(doc,
        "Внутри сервера выполняется промежуточная обработка запроса: имя поддомена "
        "проверяется на наличие в базе компаний; если компания не найдена, возвращается "
        "ошибка. Если найдена — её идентификатор подмешивается во все последующие операции "
        "запроса. Это обеспечивает изоляцию данных на уровне URL: даже при наличии действующего "
        "ключа доступа от одной компании запрос к данным другой компании возвращает отказ.")
    add_p(doc,
        "Главный администратор платформы работает на основном домене без поддомена. У него "
        "есть права на создание новых компаний с выдачей первоначальных полномочий "
        "администратора компании, на просмотр сводной статистики и на удаление компаний без "
        "устройств. Администратор компании работает на своём поддомене и не видит данные "
        "других компаний.")

    add_h2(doc, "4.3 Программный интерфейс")
    add_p(doc,
        "Сервер предоставляет программный интерфейс в стиле REST: каждой ресурсной точке "
        "соответствует адрес, к которому обращаются с одним из стандартных методов HTTP. "
        "Полный перечень точек входа приведён в приложении Б; здесь даётся группировка по "
        "назначению.")
    rows = [
        ("Без авторизации",
         "POST /api/devices/enroll, POST /api/telemetry, POST /api/device/ping",
         "Используются устройствами; для последних двух обязателен заголовок авторизации с ключом."),
        ("Администратор компании",
         "GET /api/devices, POST /api/enrollment-codes, POST /api/devices/{id}/unclaim, "
         "POST /api/devices/{id}/rotate-key, GET /api/vehicles, GET /api/vehicles/{id}/telemetry",
         "Управление парком устройств и транспортных средств; защищены маркером JWT."),
        ("Главный администратор",
         "POST /api/tenants, GET /api/tenants, DELETE /api/tenants/{id}",
         "Управление компаниями; доступно только на основном домене."),
    ]
    add_table(doc, ["Группа", "Адреса", "Назначение"], rows,
              "Группировка программных интерфейсов сервера",
              col_widths_cm=[4, 8, 4])

# ─── Раздел 5. Веб-панель ─────────────────────────────────────

def render_section5(doc):
    add_h1(doc, "5 Веб-панель")

    add_h2(doc, "5.1 Технологии и общая структура")
    add_p(doc,
        "Веб-панель построена на каркасе Vue 3 в связке с инструментом сборки Vite. Каркас "
        "Vue 3 выбран за компактный размер собранного приложения, развитую систему компонентов "
        "и удобную работу с реактивными данными. Vite обеспечивает быстрый запуск и "
        "пересборку приложения в режиме разработки.")
    add_p(doc,
        "Веб-панель работает как одностраничное приложение: при первом обращении "
        "браузер загружает все нужные ресурсы, а дальше обращается к серверу только за "
        "данными. Веб-панель собирается в статические файлы и раздаётся тем же сервером, что и "
        "программный интерфейс — это упрощает развёртывание.")

    add_h2(doc, "5.2 Основные страницы")
    add_p(doc,
        "Веб-панель содержит ряд разделов, доступных в зависимости от роли пользователя:")
    for t in [
        "страница входа с проверкой имени и пароля;",
        "сводная панель с показателями: число подключённых устройств, число активных транспортных средств, общий расход топлива за сутки;",
        "список транспортных средств компании с состоянием связи у каждого;",
        "страница транспортного средства с графиками изменения параметров за выбранный период;",
        "список устройств компании с возможностью отвязки и принудительной смены ключа доступа;",
        "выдача и отзыв шестизначных кодов привязки для новых устройств;",
        "у главного администратора — список компаний и страница их создания;",
        "встроенный справочный раздел с описанием системы и пошаговой инструкцией для прошивки.",
    ]:
        add_list_item(doc, t)
    add_placeholder(doc, "Главная страница веб-панели",
                     "Скриншот сводной панели администратора компании на поддомене (графики, "
                     "число устройств, число транспортных средств, расход топлива)")
    add_placeholder(doc, "Страница транспортного средства",
                     "Скриншот страницы фуры с графиками оборотов, скорости, температуры и "
                     "расхода топлива за выбранный период")
    add_placeholder(doc, "Список устройств компании",
                     "Скриншот списка устройств: серийные номера, состояние связи, кнопки "
                     "отвязки и принудительной смены ключа")
    add_placeholder(doc, "Выдача кодов привязки",
                     "Скриншот окна с выданным шестизначным кодом и таймером до истечения")
    add_placeholder(doc, "Список компаний (главный администратор)",
                     "Скриншот списка зарегистрированных компаний с их поддоменами и числом "
                     "устройств")

# ─── Раздел 6. Безопасность ───────────────────────────────────

def render_section6(doc):
    add_h1(doc, "6 Безопасность")

    add_h2(doc, "6.1 Защита канала передачи данных")
    add_p(doc,
        "Все обращения устройства к серверу выполняются по защищённому каналу — протоколу "
        "HTTPS. Для группового поддомена *.домен выпущен групповой сертификат, выданный "
        "центром сертификации Let's Encrypt. Это позволяет устройству доверять серверу при "
        "обращении на любой из поддоменов без необходимости менять прошивку под каждую "
        "компанию.")

    add_h2(doc, "6.2 Ключи доступа")
    add_p(doc,
        "Ключ доступа к программному интерфейсу имеет длину 256 бит и формируется на сервере "
        "при привязке устройства. На устройстве ключ хранится в открытом виде в "
        "энергонезависимой памяти; на сервере хранится только хеш ключа, рассчитанный по "
        "алгоритму SHA-256. При подозрении на компрометацию администратор компании может "
        "запросить смену ключа: сервер сгенерирует новый ключ, заменит хеш в базе, при "
        "ближайшем запросе устройство получит ответ 401 и автоматически выполнит повторную "
        "привязку для получения нового ключа.")

    add_h2(doc, "6.3 Многофакторная защита первичной привязки")
    add_p(doc,
        "Привязка устройства к компании требует одновременного выполнения трёх условий:")
    for t in [
        "физический доступ к устройству — без подключения смартфона к точке доступа устройства, привязка невозможна;",
        "знание поддомена компании — публичная, но осмысленно вводимая информация;",
        "шестизначный код привязки от администратора компании — действителен в течение тридцати минут и применим только один раз.",
    ]:
        add_list_item(doc, t)
    add_p(doc,
        "Дополнительно при привязке проверяется заводской секрет устройства — это исключает "
        "подделку запроса от стороннего устройства с известным серийным номером. Сочетание "
        "трёх факторов делает невозможной случайную или злонамеренную привязку устройства к "
        "чужой компании.")

    add_h2(doc, "6.4 Изоляция данных компаний")
    add_p(doc,
        "Все запросы, выполняемые с маркером JWT, фильтруются по идентификатору компании, "
        "определяемому по поддомену. Маркер сам по себе содержит идентификатор компании, к "
        "которой принадлежит пользователь. При несовпадении компании в маркере и в "
        "поддомене сервер возвращает ошибку 403 с кодом «tenant_mismatch». Этот механизм "
        "защищает данные одной компании от случайного или преднамеренного просмотра "
        "сотрудниками другой компании.")

# ─── Раздел 7. Проблемы при разработке ────────────────────────

def render_section7(doc):
    add_h1(doc, "7 Проблемы при разработке и их решения")
    add_p(doc,
        "В ходе работы был встречен ряд нетривиальных проблем. Ниже перечислены основные из "
        "них с описанием решения. Этот раздел даёт представление о реальной сложности "
        "разработки систем такого класса и о принятых в процессе решениях.")

    add_h2(doc, "7.1 Подделка микросхемы преобразователя CAN-шины")
    add_p(doc,
        "На раннем этапе сборки стенда не удавалось получить ни одного входящего сообщения с "
        "шины. Диагностика по счётчикам ошибок показала, что устройство постоянно "
        "находится в состоянии «error passive» с заполненным счётчиком ошибок передачи. "
        "Замена модуля WCMCU-230 на образец из другой партии немедленно решила проблему. "
        "Дополнительная проверка под микроскопом показала разные маркировки микросхем "
        "при одинаковой надписи на плате. Часть модулей содержит контрафактные микросхемы, "
        "не способные корректно работать на шине. Решение: при покупке проверять происхождение "
        "модулей, держать в запасе несколько единиц, а при подозрениях — оперативно "
        "переключать на резервный модуль.")

    add_h2(doc, "7.2 Многообразие скоростей и протоколов автомобильных шин")
    add_p(doc,
        "При обзоре существующих систем выяснилось, что одна и та же модель устройства "
        "должна работать как с грузовыми автомобилями (стандарт SAE J1939, скорость "
        "250 Кбит/с), так и с легковыми (стандарт OBD-II, скорость 500 Кбит/с). Поскольку "
        "при подключении к разъёму внутри автомобиля устройство не имеет способа узнать "
        "марку и модель машины, оно должно определять протокол самостоятельно.")
    add_p(doc,
        "Решение — конечный автомат с автоматическим переключением, описанный в "
        "подразделе 3.2.3 настоящего отчёта. Этот же автомат покрывает редкий случай, "
        "когда автомобиль использует SAE J1939 на скорости 500 Кбит/с — он также будет "
        "обнаружен по типу идентификатора в сообщениях.")
    add_figure(doc, ABOUT / "photo_2026-04-25_00-11-33.jpg",
               "Стенд с анализатором CAN-шины USBCAN-2A для проверки декодеров: "
               "слева — анализатор, в центре — переходник OBD-II, справа — устройство",
               width_cm=12)
    add_p(doc,
        "Для отладки декодеров без подключения к реальному автомобилю собран стенд с "
        "промышленным анализатором CAN-шины USBCAN-2A. На стороне настольного компьютера "
        "написаны программы на языке Python, имитирующие поведение электронного блока: одна "
        "программа отправляет десять групп параметров стандарта SAE J1939 с реалистичными "
        "значениями для движения грузовика на холостом ходу; другая отвечает на запросы по "
        "OBD-II значениями, характерными для движения легкового автомобиля.")

    add_h2(doc, "7.3 Несоответствие схемы протокола при первичной интеграции с сервером")
    add_p(doc,
        "При первой попытке привязки устройства к серверу запрос с устройства завершался "
        "ошибкой «SSL invalid record». Анализ показал: сервер находится за обратным "
        "прокси-сервером, который добавляет защищённое соединение перед серверной частью. "
        "Сама серверная часть работает по обычному протоколу. В ответе на запрос привязки "
        "сервер возвращал адрес для последующих запросов со схемой «http://», тогда как "
        "ожидался «https://». Устройство по полученному адресу пыталось установить "
        "защищённое соединение на 80-й порт обычного протокола, что и приводило к ошибке.")
    add_p(doc,
        "Решение — на стороне устройства всегда подменять схему протокола в полученном адресе "
        "на «https://», независимо от того, что вернул сервер. На стороне сервера в "
        "перспективе следует учитывать заголовок «X-Forwarded-Proto», устанавливаемый "
        "обратным прокси-сервером, и возвращать корректную схему.")

    add_h2(doc, "7.4 Метка порядка байтов в конфигурационном файле")
    add_p(doc,
        "При попытке собрать прошивку через PlatformIO выдавалась ошибка: «File contains no "
        "section headers. file: platformio.ini, line: 1». Просмотр содержимого файла "
        "показал ожидаемое содержимое, но в шестнадцатеричном виде в начале файла "
        "присутствовали три байта EF BB BF — служебная метка порядка байтов (BOM) формата "
        "UTF-8.")
    add_p(doc,
        "Причина: при создании файла из оболочки PowerShell стандартная команда экспорта "
        "(параметр «-Encoding utf8») добавляет в начало файла метку порядка байтов. Парсер "
        "PlatformIO, написанный на языке Python, такую метку не ожидал и трактовал её как "
        "часть имени первой секции, из-за чего не находил ни одной валидной секции. "
        "Решение: запись файла через стандартную библиотеку .NET (метод "
        "System.IO.File.WriteAllText с явным указанием кодировки UTF-8 без метки порядка "
        "байтов).")

    add_h2(doc, "7.5 Защита от ошибочной привязки к чужой компании")
    add_p(doc,
        "Поскольку установщик вводит название поддомена компании вручную, возможны опечатки. "
        "Если опечатка ведёт на несуществующий поддомен — устройство получит ошибку и "
        "повторит ввод. Опасен случай, когда опечатка случайно совпадает с поддоменом другой "
        "компании: тогда есть риск ошибочно привязать устройство к чужой компании.")
    add_p(doc,
        "Решение — шестизначный код привязки, выдаваемый администратором компании. Код "
        "сохраняется в базе с привязкой к идентификатору конкретной компании. При обработке "
        "запроса сервер ищет код только в рамках компании, чьему поддомену соответствует "
        "запрос. Совпадение шестизначного кода у двух компаний крайне маловероятно (один "
        "случай на миллион), а при наличии срока действия (тридцать минут) и однократного "
        "применения — практически невозможно. Опечатка в поддомене приводит к коду ответа "
        "400 «invalid_code», после чего установщик повторяет ввод. Привязка к чужой "
        "компании при опечатке исключена.")

    add_h2(doc, "7.6 Поддержка нескольких точек доступа в одной прошивке")
    add_p(doc,
        "При разработке и стендовой проверке устройство нужно поочерёдно подключать к "
        "стационарной беспроводной сети в помещении и к точке доступа смартфона, имитирующей "
        "сеть в автомобиле. Перепрошивка устройства при каждом переключении неэффективна. "
        "Решение — поддержка хранения нескольких имён сетей в энергонезависимой памяти и "
        "автоматический выбор доступной (используется библиотека WiFiMulti, входящая в каркас "
        "Arduino-ESP32). В рабочем режиме это также повышает устойчивость связи: при "
        "подключении к транспортной сети предприятия фура может перемещаться между "
        "несколькими известными точками доступа.")

# ─── Заключение ──────────────────────────────────────────────

def render_conclusion(doc):
    add_h1(doc, "Заключение")
    add_p(doc,
        "В ходе работы спроектирован и реализован программно-аппаратный комплекс для "
        "мониторинга состояния коммерческого транспорта. Достигнуты следующие результаты:")
    for t in [
        "собран макет бортового устройства на микроконтроллере ESP32 с подключёнными модулями преобразователя CAN-шины, спутниковой навигации и инерциального модуля;",
        "разработана прошивка устройства с поддержкой двух стандартов автомобильной шины — SAE J1939 для грузовиков и OBD-II для легковых, с автоматическим определением протокола;",
        "разработана процедура первичной настройки через локальную точку доступа с многофакторной защитой от ошибок;",
        "развёрнута серверная часть на платформе .NET с разграничением данных по компаниям через выделение каждой компании отдельного поддомена;",
        "разработана веб-панель администратора компании на каркасе Vue 3;",
        "проверена работоспособность всей системы на стенде с промышленным анализатором CAN-шины.",
    ]:
        add_list_item(doc, t)
    add_p(doc,
        "Из запланированных задач остались нереализованными этапы интеграции данных "
        "спутниковой навигации и инерциального модуля в передаваемый пакет, индикация "
        "состояния через светодиод, обработка аппаратной кнопки сброса, программа заводской "
        "записи серийного номера и секрета, буферизация данных при потере связи и "
        "обновление прошивки по сети.")
    add_p(doc,
        "Возможные направления развития системы: добавление детекции событий по инерциальному "
        "модулю (резкие торможения, удары, опрокидывания), формирование маршрутных листов "
        "по данным спутниковой навигации, разработка бота в мессенджере для водителей с "
        "вводом данных о заправках и получением уведомлений, развёртывание системы в "
        "тестовом автопарке для сбора реальных данных и обкатки.")

# ─── Список источников ───────────────────────────────────────

def render_references(doc):
    add_h1(doc, "Список использованных источников")
    refs = [
        "SAE International. SAE J1939 — Recommended Practice for a Serial Control and Communications Vehicle Network. — Warrendale: SAE, 2018. — 64 c.",
        "ISO 15765-4:2016. Road vehicles — Diagnostic communication over Controller Area Network (DoCAN) — Part 4: Requirements for emissions-related systems. — Geneva: ISO, 2016.",
        "ISO 11898-1:2015. Road vehicles — Controller area network (CAN) — Part 1: Data link layer and physical signalling. — Geneva: ISO, 2015.",
        "ISO 11898-2:2016. Road vehicles — Controller area network (CAN) — Part 2: High-speed medium access unit. — Geneva: ISO, 2016.",
        "Espressif Systems. ESP32 Series Datasheet, версия 4.6. — Шанхай, 2024.",
        "Espressif Systems. ESP-IDF Programming Guide. TWAI Driver. — Электронный ресурс: https://docs.espressif.com/projects/esp-idf/en/latest/api-reference/peripherals/twai.html",
        "Texas Instruments. SN65HVD230 3.3-V CAN Bus Transceivers. Datasheet (rev. M). — Даллас: Texas Instruments, 2019.",
        "u-blox. NEO-M8 series. u-blox 8 / u-blox M8 concurrent GNSS modules. Data sheet, версия документа 7. — Тальвиль, 2019.",
        "InvenSense. MPU-6000 and MPU-6050 Product Specification (rev. 3.4). — Саннивейл, 2013.",
        "Fielding R. et al. RFC 9110: HTTP Semantics. — Internet Engineering Task Force, 2022.",
        "ГОСТ 7.32-2017. Система стандартов по информации, библиотечному и издательскому делу. Отчёт о научно-исследовательской работе. Структура и правила оформления. — Москва: Стандартинформ, 2017.",
        "ГОСТ Р 7.0.5-2008. Система стандартов по информации, библиотечному и издательскому делу. Библиографическая ссылка. Общие требования и правила составления. — Москва: Стандартинформ, 2008.",
    ]
    for i, r in enumerate(refs, 1):
        p = doc.add_paragraph()
        set_paragraph_format(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line=False,
                             space_after=2)
        p.paragraph_format.left_indent = Cm(0.7)
        p.paragraph_format.first_line_indent = Cm(-0.7)
        run = p.add_run(f"{i}. {r}")
        set_run_font(run, size=SIZE_MAIN)

# ─── Приложения ──────────────────────────────────────────────

def render_appendix_a(doc):
    add_h1(doc, "Приложение А. Распиновка платы")
    add_p(doc,
        "Полное распределение выводов микроконтроллера ESP-WROOM-32 на плате-носителе "
        "LIVE MINI KIT ESP32, использованной в макете устройства.", first_line=False)
    rows = [
        ("GPIO 22", "Передача в CAN-шину (TWAI TX)",        "WCMCU-230 CTX"),
        ("GPIO 21", "Приём из CAN-шины (TWAI RX)",          "WCMCU-230 CRX"),
        ("GPIO 16", "UART2 RX, приём от модуля навигации",  "NEO-M8N TX"),
        ("GPIO 17", "UART2 TX, передача в модуль навигации","NEO-M8N RX"),
        ("GPIO 18", "I²C SDA, линия данных",                 "MPU-6050 SDA"),
        ("GPIO 19", "I²C SCL, линия тактирования",           "MPU-6050 SCL"),
        ("GPIO 0",  "Кнопка BOOT (на плате)",                "5 с — сброс настроек беспроводной сети, 10 с — заводской сброс"),
        ("GPIO 2",  "Встроенный светодиод",                  "Индикация состояния"),
        ("3,3 В",   "Питание модулей",                        "Общая шина"),
        ("GND",     "Общий провод",                           "Общая шина земли"),
    ]
    add_table(doc, ["Вывод", "Назначение", "Подключение / описание"], rows,
              "Полное распределение выводов микроконтроллера",
              col_widths_cm=[2.5, 6.5, 7])

def render_appendix_b(doc):
    add_h1(doc, "Приложение Б. Перечень программных интерфейсов")
    add_p(doc, "В приложении приведён сводный перечень точек входа сервера.", first_line=False)
    rows = [
        ("POST", "/api/devices/enroll", "Без авторизации", "Первичная привязка устройства; в теле — серийный номер, заводской секрет, код привязки."),
        ("POST", "/api/telemetry",      "Bearer",          "Передача данных о состоянии транспортного средства каждые 5 секунд."),
        ("POST", "/api/device/ping",    "Bearer",          "Сообщение поддержания связи каждую минуту."),
        ("POST", "/api/auth/login",     "Без авторизации", "Вход пользователя по логину и паролю; возвращает маркер JWT."),
        ("GET",  "/api/auth/context",   "Без авторизации", "Сведения о текущем хосте и компании, к нему относящейся."),
        ("POST", "/api/enrollment-codes", "JWT админ компании", "Выдача нового шестизначного кода привязки."),
        ("GET",  "/api/enrollment-codes", "JWT админ компании", "Список активных кодов привязки компании."),
        ("DELETE","/api/enrollment-codes/{id}", "JWT админ компании", "Отзыв ранее выданного кода."),
        ("GET",  "/api/devices",        "JWT админ компании", "Список устройств компании."),
        ("POST", "/api/devices",        "JWT админ компании", "Регистрация нового устройства в базе."),
        ("POST", "/api/devices/{id}/unclaim",    "JWT админ компании", "Отвязка устройства от компании."),
        ("POST", "/api/devices/{id}/rotate-key", "JWT админ компании", "Принудительная смена ключа доступа."),
        ("PUT",  "/api/devices/{id}/vehicle",    "JWT админ компании", "Назначение устройства на конкретное транспортное средство."),
        ("GET",  "/api/vehicles",                "JWT админ компании", "Список транспортных средств компании."),
        ("GET",  "/api/vehicles/{id}",           "JWT админ компании", "Данные конкретного транспортного средства."),
        ("GET",  "/api/vehicles/{id}/telemetry", "JWT админ компании", "История параметров для построения графиков."),
        ("GET",  "/api/vehicles/{id}/alerts",    "JWT админ компании", "Активные оповещения по транспортному средству."),
        ("GET",  "/api/vehicles/{id}/refuels",   "JWT админ компании", "История заправок."),
        ("GET",  "/api/dashboard",               "JWT админ компании", "Сводная статистика компании."),
        ("POST", "/api/tenants",                 "JWT главный админ",  "Регистрация новой компании."),
        ("GET",  "/api/tenants",                 "JWT главный админ",  "Список компаний."),
        ("DELETE","/api/tenants/{id}",           "JWT главный админ",  "Удаление компании без устройств."),
        ("GET",  "/api/health",                  "Без авторизации",    "Проверка работоспособности сервера."),
    ]
    add_table(doc, ["Метод", "Адрес", "Авторизация", "Назначение"], rows,
              "Сводный перечень программных интерфейсов сервера",
              col_widths_cm=[1.5, 5.5, 3.5, 5.5])

def render_appendix_c(doc):
    add_h1(doc, "Приложение В. Схема состояний прошивки устройства")
    add_p(doc, "На схеме показана последовательность состояний прошивки устройства при "
               "включении и переходы между ними.", first_line=False)
    img = TMP / "boot_states.png"
    make_boot_state_machine(img)
    add_figure(doc, img, "Схема состояний прошивки бортового устройства", width_cm=16)

# ─── Главная функция сборки ──────────────────────────────────

def build():
    doc = Document()
    # Базовый стиль документа: Times New Roman 14 с 1.5 интервалом
    style = doc.styles["Normal"]
    style.font.name = FONT_MAIN
    style.font.size = SIZE_MAIN
    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(attr), FONT_MAIN)
    style.paragraph_format.line_spacing = 1.5
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.first_line_indent = Cm(1.25)

    # Поля и нумерация
    configure_page(doc)
    add_page_numbers(doc)

    # Титульный лист, реферат, содержание
    render_title(doc)
    render_abstract(doc)

    add_h1(doc, "Содержание", in_toc=False)
    add_toc_field(doc)

    render_abbreviations(doc)
    render_intro(doc)

    # Основная часть
    render_section1(doc)
    render_section2(doc)
    render_section3(doc)
    render_section4(doc)
    render_section5(doc)
    render_section6(doc)
    render_section7(doc)

    # Заключение, источники, приложения
    render_conclusion(doc)
    render_references(doc)
    render_appendix_a(doc)
    render_appendix_b(doc)
    render_appendix_c(doc)

    doc.save(str(OUT))
    print(f"saved: {OUT}  (рисунков: {COUNTERS['figure']}, таблиц: {COUNTERS['table']})")

if __name__ == "__main__":
    build()