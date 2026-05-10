"""Build VehicleLogger presentation.pptx with proper styling."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

# Colors
NAVY    = RGBColor(0x0A, 0x25, 0x40)
NAVY2   = RGBColor(0x14, 0x3D, 0x66)
ORANGE  = RGBColor(0xF4, 0x7C, 0x26)
LIGHT   = RGBColor(0xF5, 0xF7, 0xFA)
DARK    = RGBColor(0x1A, 0x1A, 0x1A)
MID     = RGBColor(0x5A, 0x6A, 0x7A)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
SUCCESS = RGBColor(0x22, 0xA0, 0x6B)
DANGER  = RGBColor(0xD9, 0x47, 0x4F)
BORDER  = RGBColor(0xD0, 0xD7, 0xDE)
PHOTOBG = RGBColor(0xEC, 0xF1, 0xF6)
CODEBG  = RGBColor(0x1E, 0x29, 0x36)

FONT = "Segoe UI"
FONT_MONO = "Consolas"

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]

def solid(shape, color):
    f = shape.fill; f.solid(); f.fore_color.rgb = color

def noline(shape):
    shape.line.fill.background()

def line(shape, color, width_pt=1.0):
    ln = shape.line; ln.color.rgb = color; ln.width = Pt(width_pt)

def add_rect(slide, x, y, w, h, fill, line_color=None, line_w=0):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    solid(s, fill)
    if line_color is None: noline(s)
    else: line(s, line_color, line_w)
    s.shadow.inherit = False
    return s

def add_text(slide, text, x, y, w, h,
             size=14, bold=False, color=DARK, font=FONT,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.name = font; r.font.size = Pt(size)
    r.font.bold = bold; r.font.color.rgb = color
    return tb

def add_bullets(slide, items, x, y, w, h, size=15, color=DARK, bullet_color=ORANGE):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True; tf.margin_left = Inches(0.1)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(8)
        rb = p.add_run(); rb.text = "▸  "
        rb.font.name = FONT; rb.font.size = Pt(size)
        rb.font.color.rgb = bullet_color; rb.font.bold = True
        rt = p.add_run(); rt.text = item
        rt.font.name = FONT; rt.font.size = Pt(size); rt.font.color.rgb = color
    return tb

def add_numbered(slide, items, x, y, w, h, size=15, color=DARK):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True; tf.margin_left = Inches(0.1)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        rn = p.add_run(); rn.text = f"{i+1}.  "
        rn.font.name = FONT; rn.font.size = Pt(size)
        rn.font.color.rgb = ORANGE; rn.font.bold = True
        rt = p.add_run(); rt.text = item
        rt.font.name = FONT; rt.font.size = Pt(size); rt.font.color.rgb = color
    return tb

def header_band(slide, title, subtitle=None):
    add_rect(slide, 0, 0, SW, Inches(0.08), ORANGE)
    add_text(slide, title, Inches(0.6), Inches(0.25), SW - Inches(1.2), Inches(0.7),
             size=28, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
    if subtitle:
        add_text(slide, subtitle, Inches(0.6), Inches(0.85), SW - Inches(1.2), Inches(0.4),
                 size=14, color=MID, anchor=MSO_ANCHOR.TOP)
    sep_y = Inches(1.4) if subtitle else Inches(1.05)
    add_rect(slide, Inches(0.6), sep_y, Inches(0.5), Inches(0.04), ORANGE)
    return Inches(1.7) if subtitle else Inches(1.35)

def footer_band(slide, page_num, total):
    add_rect(slide, Inches(0.6), SH - Inches(0.55), SW - Inches(1.2), Inches(0.012), BORDER)
    add_text(slide, "VehicleLogger · 2026", Inches(0.6), SH - Inches(0.45), Inches(4), Inches(0.3),
             size=10, color=MID)
    add_text(slide, f"{page_num} / {total}", SW - Inches(2.6), SH - Inches(0.45), Inches(2), Inches(0.3),
             size=10, color=MID, align=PP_ALIGN.RIGHT)

def photo_placeholder(slide, x, y, w, h, caption):
    bx = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    solid(bx, PHOTOBG); line(bx, NAVY2, 1.5); bx.shadow.inherit = False
    spPr = bx.line._get_or_add_ln()
    prstDash = etree.SubElement(spPr, qn("a:prstDash"))
    prstDash.set("val", "dash")
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p1 = tf.paragraphs[0]; p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run(); r1.text = "📷"
    r1.font.name = FONT; r1.font.size = Pt(40); r1.font.color.rgb = NAVY2
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER; p2.space_before = Pt(8)
    r2 = p2.add_run(); r2.text = caption
    r2.font.name = FONT; r2.font.size = Pt(13); r2.font.color.rgb = MID; r2.font.italic = True

def add_table(slide, headers, rows, x, y, w, h, col_widths=None, first_col_bold=False):
    cols = len(headers); nrows = len(rows) + 1
    tbl = slide.shapes.add_table(nrows, cols, x, y, w, h).table
    if col_widths:
        for i, cw in enumerate(col_widths): tbl.columns[i].width = cw
    for ci, htext in enumerate(headers):
        cell = tbl.cell(0, ci); solid(cell, NAVY)
        cell.margin_top = cell.margin_bottom = Inches(0.06)
        cell.margin_left = cell.margin_right = Inches(0.12)
        tf = cell.text_frame; tf.word_wrap = True
        tf.paragraphs[0].text = ""
        r = tf.paragraphs[0].add_run(); r.text = htext
        r.font.name = FONT; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = WHITE
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri + 1, ci)
            solid(cell, WHITE if ri % 2 == 0 else LIGHT)
            cell.margin_top = cell.margin_bottom = Inches(0.05)
            cell.margin_left = cell.margin_right = Inches(0.12)
            tf = cell.text_frame; tf.word_wrap = True
            tf.paragraphs[0].text = ""
            r = tf.paragraphs[0].add_run(); r.text = str(val)
            r.font.name = FONT; r.font.size = Pt(12); r.font.color.rgb = DARK
            if first_col_bold and ci == 0:
                r.font.bold = True; r.font.color.rgb = NAVY
    return tbl

def add_code_block(slide, text, x, y, w, h, size=11):
    add_rect(slide, x, y, w, h, CODEBG)
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.15)
    tf.margin_top = tf.margin_bottom = Inches(0.1)
    for i, ltext in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run(); r.text = ltext
        r.font.name = FONT_MONO; r.font.size = Pt(size); r.font.color.rgb = WHITE

SLIDES = []
def page(fn): SLIDES.append(fn); return fn

@page
def s1(idx, total):
    slide = prs.slides.add_slide(BLANK)
    add_rect(slide, 0, 0, SW, SH, NAVY)
    add_rect(slide, 0, 0, Inches(0.4), SH, ORANGE)
    add_rect(slide, Inches(0.4), Inches(2.6), Inches(2), Inches(0.06), ORANGE)
    add_text(slide, "VehicleLogger", Inches(1), Inches(2.7), Inches(11), Inches(1.2),
             size=68, bold=True, color=WHITE)
    add_text(slide, "Система мониторинга фур в реальном времени",
             Inches(1), Inches(3.9), Inches(11), Inches(0.6), size=24, color=ORANGE)
    add_text(slide, "ESP32 · CAN-шина (J1939 / OBD-II) · .NET + Vue 3 · Multi-tenant",
             Inches(1), Inches(4.5), Inches(11), Inches(0.5), size=16, color=WHITE)
    add_text(slide, "КУРСОВОЙ ПРОЕКТ", Inches(1), SH - Inches(1.3), Inches(8), Inches(0.4),
             size=11, color=ORANGE, bold=True)
    add_text(slide, "Сергей Лавриненко · Тимур · 2026",
             Inches(1), SH - Inches(0.95), Inches(11), Inches(0.5), size=15, color=WHITE)

@page
def s2(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "О проекте", "Зачем это нужно")
    cw, ch = Inches(5.9), Inches(4.1)
    add_rect(slide, Inches(0.6), by, cw, ch, LIGHT, BORDER, 0.5)
    add_text(slide, "Проблема", Inches(0.85), by + Inches(0.2), cw, Inches(0.5),
             size=20, bold=True, color=DANGER)
    add_bullets(slide, [
        "Владельцы автопарков не видят, что происходит с фурой между рейсами",
        "Расход, обороты, ошибки ECU, маршрут — контроль «по бумажке» от водителя",
        "Западные системы (Wialon, Omnicomm) дороги или недоступны",
    ], Inches(0.85), by + Inches(0.85), cw - Inches(0.5), ch - Inches(1.0), size=14)
    add_rect(slide, Inches(6.85), by, cw, ch, LIGHT, BORDER, 0.5)
    add_text(slide, "Решение", Inches(7.1), by + Inches(0.2), cw, Inches(0.5),
             size=20, bold=True, color=SUCCESS)
    add_bullets(slide, [
        "ESP32 в кабине читает CAN-шину, шлёт телеметрию по WiFi",
        "Веб-панель — графики и алерты для админа компании",
        "Telegram-бот — заправки и алерты для водителя",
        "Open-source стек, ~2000 ₽ железо vs ~30 000 ₽ у конкурентов",
    ], Inches(7.1), by + Inches(0.85), cw - Inches(0.5), ch - Inches(1.0), size=14)
    photo_placeholder(slide, Inches(3.5), by + ch + Inches(0.15), Inches(6), Inches(0.85),
                       "ФОТО: устройство в фуре / иллюстрация")
    footer_band(slide, idx, total)

@page
def s3(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Архитектура системы")
    bw, bh = Inches(3.4), Inches(1.6); cy = by + Inches(0.4)
    add_rect(slide, Inches(0.7), cy, bw, bh, NAVY)
    add_text(slide, "ESP32 в кабине", Inches(0.7), cy + Inches(0.15), bw, Inches(0.4),
             size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, "CAN · GPS · IMU\nC++ / Arduino-ESP32",
             Inches(0.7), cy + Inches(0.65), bw, Inches(0.9),
             size=13, color=ORANGE, align=PP_ALIGN.CENTER)
    add_rect(slide, Inches(4.95), cy, bw, bh, NAVY2)
    add_text(slide, "Backend", Inches(4.95), cy + Inches(0.15), bw, Inches(0.4),
             size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, ".NET 10 + EF Core\nSQLite (prod: PostgreSQL)\nWildcard *.nonconf.ru",
             Inches(4.95), cy + Inches(0.6), bw, Inches(1.0),
             size=13, color=ORANGE, align=PP_ALIGN.CENTER)
    bw3, bh3 = Inches(3.4), Inches(0.7)
    add_rect(slide, Inches(9.2), cy, bw3, bh3, ORANGE)
    add_text(slide, "Web-панель (Vue 3)", Inches(9.2), cy, bw3, bh3,
             size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    add_rect(slide, Inches(9.2), cy + Inches(0.9), bw3, bh3, ORANGE)
    add_text(slide, "Telegram-бот", Inches(9.2), cy + Inches(0.9), bw3, bh3,
             size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    def arrow(x1, y1, x2, y2):
        cn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
        cn.line.color.rgb = NAVY; cn.line.width = Pt(2)
        ln = cn.line._get_or_add_ln()
        tail = etree.SubElement(ln, qn("a:tailEnd"))
        tail.set("type", "triangle"); tail.set("w", "med"); tail.set("h", "med")
    arrow(Inches(4.1), cy + Inches(0.8), Inches(4.95), cy + Inches(0.8))
    arrow(Inches(8.35), cy + Inches(0.5), Inches(9.2), cy + Inches(0.35))
    arrow(Inches(8.35), cy + Inches(1.1), Inches(9.2), cy + Inches(1.25))
    add_text(slide, "HTTPS\n/api/telemetry",
             Inches(4.1), cy - Inches(0.3), Inches(0.85), Inches(0.5),
             size=9, color=MID, align=PP_ALIGN.CENTER)
    note_y = cy + bh + Inches(0.4)
    add_rect(slide, Inches(0.7), note_y, SW - Inches(1.4), Inches(2), LIGHT, BORDER, 0.5)
    add_text(slide, "Мультитенантность", Inches(1), note_y + Inches(0.2),
             Inches(6), Inches(0.4), size=16, bold=True, color=NAVY)
    add_bullets(slide, [
        "Каждая компания получает свой поддомен <sub>.nonconf.ru",
        "Wildcard-сертификат *.nonconf.ru, общий бэкенд",
        "Тенант резолвится по Host-заголовку — изоляция данных на уровне URL",
        "nonconf.ru — super-admin (создание новых компаний)",
    ], Inches(1), note_y + Inches(0.7), SW - Inches(2), Inches(1.2), size=13)
    footer_band(slide, idx, total)

@page
def s4(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Стек технологий и распределение работ")
    rows = [
        ("Устройство (ESP32)", "C++, Arduino-ESP32, PlatformIO", "Сергей"),
        ("CAN-протоколы",      "SAE J1939, ISO 15765-4 (OBD-II)",  "Сергей"),
        ("Бэкенд",             ".NET 10, ASP.NET Core, EF Core",   "Тимур"),
        ("База данных",        "SQLite (prototype) / PostgreSQL (prod)", "Тимур"),
        ("Веб-панель",         "Vue 3 + Vite, TypeScript",         "Тимур"),
        ("Telegram-бот",       "В работе (Telegram Bot API)",      "Тимур"),
        ("Деплой",             "nonconf.ru, wildcard *.nonconf.ru", "Тимур"),
    ]
    add_table(slide, ["Компонент", "Стек", "Кто делал"], rows,
              Inches(0.7), by + Inches(0.3), SW - Inches(1.4), Inches(4.6),
              col_widths=[Inches(3.2), Inches(6.5), Inches(2.2)], first_col_bold=True)
    footer_band(slide, idx, total)

@page
def s5(idx, total):
    slide = prs.slides.add_slide(BLANK)
    add_rect(slide, 0, 0, SW, SH, NAVY)
    add_rect(slide, 0, Inches(2.8), SW, Inches(1.4), ORANGE)
    add_text(slide, "ЭТАП 1", Inches(0.6), Inches(2.0), Inches(8), Inches(0.7),
             size=32, bold=True, color=ORANGE)
    add_text(slide, "Среда и диагностика",
             Inches(0.6), Inches(3.0), SW - Inches(1.2), Inches(1.0),
             size=48, bold=True, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
    add_text(slide, "Hardware setup, проверка модулей, тестовый стенд с веб-дашбордом",
             Inches(0.6), Inches(4.5), SW - Inches(1.2), Inches(0.5), size=16, color=WHITE)

@page
def s6(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Железо устройства")
    rows = [
        ("Контроллер",   "ESP-WROOM-32",      "Двухъядерный, Wi-Fi, встроенный TWAI"),
        ("CAN-трансивер","WCMCU-230 (SN65HVD230)", "Подключение к шине автомобиля"),
        ("GPS",          "GY-GPSV3-NEO-M8N",  "Координаты, скорость по UART"),
        ("IMU",          "MPU-6050",          "Резкое торможение, удар (I²C)"),
        ("Питание",      "12V → 3.3V LDO",    "От прикуривателя или OBD-II"),
    ]
    add_table(slide, ["Компонент", "Модуль", "Назначение"], rows,
              Inches(0.7), by + Inches(0.2), Inches(7.6), Inches(3.5),
              col_widths=[Inches(2.0), Inches(2.5), Inches(3.1)], first_col_bold=True)
    photo_placeholder(slide, Inches(8.6), by + Inches(0.2), Inches(4.0), Inches(3.5),
                       "ФОТО: ESP32 с подключёнными модулями")
    add_rect(slide, Inches(0.7), by + Inches(3.95), SW - Inches(1.4), Inches(0.8), ORANGE)
    add_text(slide, "Стоимость комплектующих: ~1800 ₽  (vs ~30 000 ₽ у конкурентов)",
             Inches(0.7), by + Inches(3.95), SW - Inches(1.4), Inches(0.8),
             size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    footer_band(slide, idx, total)

@page
def s7(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Распиновка ESP32")
    rows = [
        ("GPIO 22", "WCMCU-230 CTX",   "TWAI TX"),
        ("GPIO 21", "WCMCU-230 CRX",   "TWAI RX"),
        ("GPIO 16", "NEO-M8N TX",      "UART2 RX"),
        ("GPIO 17", "NEO-M8N RX",      "UART2 TX"),
        ("GPIO 18", "MPU-6050 SDA",    "I²C Data"),
        ("GPIO 19", "MPU-6050 SCL",    "I²C Clock"),
        ("GPIO 0",  "Кнопка BOOT",     "5 сек = WiFi reset, 10 сек = factory"),
        ("GPIO 2",  "LED",             "Индикация состояния"),
    ]
    add_table(slide, ["GPIO", "Подключение", "Интерфейс"], rows,
              Inches(0.7), by + Inches(0.2), Inches(7.6), Inches(4.5),
              col_widths=[Inches(1.5), Inches(2.7), Inches(3.4)], first_col_bold=True)
    photo_placeholder(slide, Inches(8.6), by + Inches(0.2), Inches(4.0), Inches(4.5),
                       "ФОТО: подключения с подписями")
    footer_band(slide, idx, total)

@page
def s8(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Диагностика модулей",
                      "Прошивка проверяет каждый сенсор на старте")
    code = ("==== VehicleLogger — Диагностика v1.0 ====\n\n"
            "TEST 1: Wi-Fi          → OK    (RSSI -45 dBm)\n"
            "TEST 2: I²C / MPU-6050 → OK    (WHO_AM_I 0x68, ax/ay/az)\n"
            "TEST 3: CAN / TWAI     → OK    (driver @ 500 kbit/s)\n"
            "TEST 4: GPS / NEO-M8N  → OK    (NMEA, 8 спутников)\n\n"
            ">>> Все модули работают! <<<")
    add_code_block(slide, code, Inches(0.7), by + Inches(0.2),
                    Inches(7.5), Inches(3.5), size=14)
    photo_placeholder(slide, Inches(8.5), by + Inches(0.2), Inches(4.1), Inches(3.5),
                       "СКРИН: вывод диагностики в Serial Monitor")
    add_text(slide, "Если какой-то модуль не работает — сразу видно по boot-логу, без отладчика.",
             Inches(0.7), by + Inches(3.9), SW - Inches(1.4), Inches(0.5),
             size=14, color=MID, align=PP_ALIGN.CENTER)
    footer_band(slide, idx, total)

@page
def s9(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Тестовый стенд firmware-test/",
                      "Веб-дашборд для отладки без Serial Monitor")
    add_bullets(slide, [
        "LittleFS для статики (HTML / CSS / JS) на ESP32",
        "WebSocket — данные обновляются каждые 200 мс",
        "Sky-plot спутников, графики SNR в реальном времени",
        "Карточка «Показатели автомобиля»: RPM, скорость, давление",
        "Параллельный проект — production firmware остаётся минимальным",
    ], Inches(0.7), by + Inches(0.3), Inches(6.5), Inches(4), size=15)
    photo_placeholder(slide, Inches(7.5), by + Inches(0.2), Inches(5.2), Inches(2.4),
                       "СКРИН: главная страница дашборда")
    photo_placeholder(slide, Inches(7.5), by + Inches(2.8), Inches(5.2), Inches(2.0),
                       "СКРИН: sky-plot GPS")
    footer_band(slide, idx, total)

@page
def s10(idx, total):
    slide = prs.slides.add_slide(BLANK)
    add_rect(slide, 0, 0, SW, SH, NAVY)
    add_rect(slide, 0, Inches(2.8), SW, Inches(1.4), ORANGE)
    add_text(slide, "ЭТАП 2", Inches(0.6), Inches(2.0), Inches(8), Inches(0.7),
             size=32, bold=True, color=ORANGE)
    add_text(slide, "Декодеры CAN",
             Inches(0.6), Inches(3.0), SW - Inches(1.2), Inches(1.0),
             size=48, bold=True, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
    add_text(slide, "J1939 для грузовиков, OBD-II для легковых, авто-определение",
             Inches(0.6), Inches(4.5), SW - Inches(1.2), Inches(0.5), size=16, color=WHITE)

@page
def s11(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Два мира CAN-шины")
    rows = [
        ("ID",        "29-бит (extended)",          "11-бит (standard)"),
        ("Скорость",  "250 кбит/с",                  "500 кбит/с"),
        ("Модель",    "Broadcast — ECU сам шлёт",   "Запрос-ответ на 0x7DF"),
        ("Где",       "Грузовики (MAN, Volvo, Scania)", "Легковые ≥ 2008 г."),
        ("Адресация", "Source Address в ID",         "ECU отвечают на 0x7E8–0x7EF"),
    ]
    add_table(slide, ["", "SAE J1939", "OBD-II (ISO 15765-4)"], rows,
              Inches(0.7), by + Inches(0.3), SW - Inches(1.4), Inches(4),
              col_widths=[Inches(2.0), Inches(4.95), Inches(4.95)], first_col_bold=True)
    add_rect(slide, Inches(0.7), by + Inches(4.6), SW - Inches(1.4), Inches(0.55), SUCCESS)
    add_text(slide, "Прошивка поддерживает оба протокола и определяет автоматически",
             Inches(0.7), by + Inches(4.6), SW - Inches(1.4), Inches(0.55),
             size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    footer_band(slide, idx, total)

@page
def s12(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Декодер J1939",
                      "10 стандартных PGN + DM1 (диагностические коды)")
    rows = [
        ("61444", "EEC1",  "Обороты двигателя",       "0.125 об/мин"),
        ("65265", "CCVS",  "Скорость",                "1/256 км/ч"),
        ("65262", "ET1",   "Температура ОЖ",          "1 °C, offset −40"),
        ("65263", "EFLP1", "Давление масла, топливо", "4 кПа / 0.4 %"),
        ("65271", "EP1",   "Напряжение бортсети",     "0.05 В"),
        ("65266", "LFE",   "Расход топлива",          "0.05 л/ч"),
        ("61443", "EEC2",  "Нагрузка двигателя",      "1 %"),
        ("65248", "VD",    "Общий пробег",            "0.125 км"),
        ("65253", "HOURS", "Моточасы",                "0.05 ч"),
        ("65226", "DM1",   "Активные DTC (SPN+FMI)",  "single-frame"),
    ]
    add_table(slide, ["PGN", "Имя", "Параметр", "Точность"], rows,
              Inches(0.7), by + Inches(0.2), SW - Inches(1.4), Inches(4.5),
              col_widths=[Inches(1.4), Inches(1.6), Inches(5.5), Inches(3.4)],
              first_col_bold=True)
    add_text(slide, "Таблица PGN живёт в PROGMEM (~500 байт Flash) — обновление через OTA.",
             Inches(0.7), by + Inches(4.85), SW - Inches(1.4), Inches(0.4),
             size=13, color=MID, align=PP_ALIGN.CENTER)
    footer_band(slide, idx, total)

@page
def s13(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "OBD-II поллер для легковых",
                      "J1939 на легковой не работает — нужен запрос-ответ")
    rows = [
        ("0x04", "Engine load",    "A × 100 / 255",    "%"),
        ("0x05", "Coolant temp",   "A − 40",            "°C"),
        ("0x0C", "RPM",            "(A·256 + B) / 4",   "об/мин"),
        ("0x0D", "Speed",          "A",                 "км/ч"),
        ("0x2F", "Fuel level",     "A × 100 / 255",     "%"),
        ("0x42", "Voltage",        "(A·256 + B) / 1000","В"),
        ("0x5E", "Fuel rate",      "(A·256 + B) / 20",  "л/ч"),
    ]
    add_table(slide, ["PID", "Параметр", "Формула", "Ед."], rows,
              Inches(0.7), by + Inches(0.2), Inches(7.6), Inches(3.7),
              col_widths=[Inches(1.2), Inches(2.2), Inches(2.7), Inches(1.5)],
              first_col_bold=True)
    box_y = by + Inches(0.2); box_h = Inches(3.7)
    add_rect(slide, Inches(8.6), box_y, Inches(4.0), box_h, LIGHT, BORDER, 0.5)
    add_text(slide, "Как это работает", Inches(8.85), box_y + Inches(0.15),
             Inches(3.5), Inches(0.4), size=15, bold=True, color=NAVY)
    add_bullets(slide, [
        "ESP шлёт запрос на 0x7DF (functional broadcast)",
        "Раз в 100 мс по очереди для каждого PID",
        "Ловит ответы на 0x7E8–0x7EF",
        "Парсит [len, 0x41, PID, A, B…]",
    ], Inches(8.8), box_y + Inches(0.6), Inches(3.7), Inches(3.0), size=12)
    footer_band(slide, idx, total)

@page
def s14(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Авто-определение шины",
                      "Один и тот же бинарник работает на любом авто")
    bw, bh = Inches(2.6), Inches(0.9); yc = by + Inches(0.5)
    def state_box(x, y, w, h, label, color=NAVY):
        add_rect(slide, x, y, w, h, color)
        add_text(slide, label, x, y, w, h, size=13, bold=True, color=WHITE,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    def label(x, y, w, h, text, color=ORANGE, size=11):
        add_text(slide, text, x, y, w, h, size=size, bold=True, color=color, align=PP_ALIGN.CENTER)
    state_box(Inches(0.6),  yc, bw, bh, "BOOT\nlisten @ 500 kbit/s")
    state_box(Inches(5.4),  yc, bw, bh, "J1939\nlisten-only", SUCCESS)
    state_box(Inches(9.7),  yc, bw, bh, "OBD-II\nNORMAL + poll 0x7DF", ORANGE)
    state_box(Inches(0.6),  yc + Inches(2), bw, bh, "listen @ 250 kbit/s")
    state_box(Inches(5.4),  yc + Inches(2), bw, bh, "Default OBD-II\n@ 500 kbit/s", ORANGE)
    def arrow(x1, y1, x2, y2, color=NAVY):
        cn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
        cn.line.color.rgb = color; cn.line.width = Pt(2)
        ln = cn.line._get_or_add_ln()
        tail = etree.SubElement(ln, qn("a:tailEnd")); tail.set("type", "triangle")
    arrow(Inches(3.2), yc + Inches(0.45), Inches(5.4), yc + Inches(0.45))
    label(Inches(3.3), yc - Inches(0.05), Inches(2), Inches(0.4), "29-бит ID seen", SUCCESS)
    arrow(Inches(1.9), yc + Inches(0.9), Inches(1.9), yc + Inches(2))
    label(Inches(2.0), yc + Inches(1.2), Inches(2), Inches(0.4), "3 сек тишина", DANGER)
    arrow(Inches(3.2), yc + Inches(2.45), Inches(5.4), yc + Inches(2.45))
    label(Inches(3.3), yc + Inches(2), Inches(2), Inches(0.4), "ещё 3 сек тишина", DANGER)
    arrow(Inches(8), yc + Inches(0.45), Inches(9.7), yc + Inches(0.45))
    label(Inches(8.1), yc - Inches(0.05), Inches(1.6), Inches(0.4), "только 11-бит", ORANGE)
    note_y = yc + Inches(3.4)
    add_rect(slide, Inches(0.7), note_y, SW - Inches(1.4), Inches(0.9), LIGHT, BORDER, 0.5)
    add_text(slide, "В J1939 ESP сидит в LISTEN_ONLY (не ACK-ает). В OBD-II — NORMAL "
             "режим, шлёт запросы и принимает ACK от ECU. Переключение режима без перезагрузки.",
             Inches(0.85), note_y, SW - Inches(1.6), Inches(0.9),
             size=13, color=DARK, anchor=MSO_ANCHOR.MIDDLE)
    footer_band(slide, idx, total)

@page
def s15(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Верификация: USBCAN-2A стенд",
                      "Проверка всех декодеров без реальной машины")
    add_bullets(slide, [
        "USBCAN-2A — двухканальный анализатор CAN-шины с PC через USB",
        "Каналы CH0+CH1 в режиме NORMAL — ACK-ают друг друга",
        "ESP подключён в режиме LISTEN_ONLY — видит весь обмен",
        "Python-скрипты на стороне PC генерируют трафик:",
    ], Inches(0.7), by + Inches(0.3), Inches(6.7), Inches(2.5), size=14)
    box_y = by + Inches(2.7)
    add_rect(slide, Inches(0.7), box_y, Inches(6.7), Inches(2.0), LIGHT, BORDER, 0.5)
    add_text(slide, "tools/j1939_send.py", Inches(0.95), box_y + Inches(0.1),
             Inches(6.2), Inches(0.4), size=14, bold=True, color=NAVY, font=FONT_MONO)
    add_text(slide, "Генерирует 9 PGN с реалистичными значениями фуры на холостом",
             Inches(0.95), box_y + Inches(0.45), Inches(6.2), Inches(0.4), size=12, color=DARK)
    add_text(slide, "tools/obd2_emu.py", Inches(0.95), box_y + Inches(0.95),
             Inches(6.2), Inches(0.4), size=14, bold=True, color=NAVY, font=FONT_MONO)
    add_text(slide, "Эмулирует ECU Volvo S80, отвечает на запросы 0x7DF",
             Inches(0.95), box_y + Inches(1.3), Inches(6.2), Inches(0.4), size=12, color=DARK)
    photo_placeholder(slide, Inches(7.7), by + Inches(0.2), Inches(5.0), Inches(4.5),
                       "ФОТО: ESP32 + USBCAN-2A на столе")
    footer_band(slide, idx, total)

@page
def s16(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Результат: все 9 PGN на дашборде", "Сквозной тест прошёл")
    tile_w = Inches(2.95); tile_h = Inches(1.4); ty = by + Inches(0.3)
    def kpi(x, label, value, color=ORANGE):
        add_rect(slide, x, ty, tile_w, tile_h, NAVY)
        add_text(slide, value, x, ty + Inches(0.1), tile_w, Inches(0.7),
                 size=32, bold=True, color=color, align=PP_ALIGN.CENTER)
        add_text(slide, label, x, ty + Inches(0.85), tile_w, Inches(0.5),
                 size=13, color=WHITE, align=PP_ALIGN.CENTER)
    kpi(Inches(0.7),   "кадров декодировано", "33 000", ORANGE)
    kpi(Inches(3.85),  "за секунд",           "20",     SUCCESS)
    kpi(Inches(7.0),   "PGN распарсено",      "9 / 9",  SUCCESS)
    kpi(Inches(10.15), "ошибок декодера",     "0",      SUCCESS)
    box_y = ty + tile_h + Inches(0.3)
    add_rect(slide, Inches(0.7), box_y, Inches(6.5), Inches(3), LIGHT, BORDER, 0.5)
    add_text(slide, "Параметры показаны корректно",
             Inches(0.95), box_y + Inches(0.15), Inches(6), Inches(0.4),
             size=14, bold=True, color=NAVY)
    add_bullets(slide, [
        "RPM = 800   (холостой ход)",
        "Speed = 0   (стоит)",
        "Coolant = 85 °C",
        "Oil pressure = 300 kPa",
        "Fuel level = 65 %",
        "Battery = 24.5 В",
    ], Inches(0.95), box_y + Inches(0.55), Inches(6.0), Inches(2.4),
       size=13, bullet_color=SUCCESS)
    photo_placeholder(slide, Inches(7.5), box_y, Inches(5.2), Inches(3),
                       "СКРИН: дашборд с заполненной\nкарточкой «Показатели автомобиля»")
    footer_band(slide, idx, total)

@page
def s17(idx, total):
    slide = prs.slides.add_slide(BLANK)
    add_rect(slide, 0, 0, SW, SH, NAVY)
    add_rect(slide, 0, Inches(2.8), SW, Inches(1.4), ORANGE)
    add_text(slide, "ЭТАП 3", Inches(0.6), Inches(2.0), Inches(8), Inches(0.7),
             size=32, bold=True, color=ORANGE)
    add_text(slide, "Provisioning",
             Inches(0.6), Inches(3.0), SW - Inches(1.2), Inches(1.0),
             size=48, bold=True, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
    add_text(slide, "Мультитенантность, captive portal, привязка устройства к компании",
             Inches(0.6), Inches(4.5), SW - Inches(1.2), Inches(0.5), size=16, color=WHITE)

@page
def s18(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Мультитенантность через поддомены",
                      "Изоляция данных на уровне URL")
    rows = [
        ("nonconf.ru",          "Super-admin платформы",   "Все компании, регистрация новых"),
        ("acme.nonconf.ru",     "Admin компании ACME",     "Только свои фуры/устройства"),
        ("volvo.nonconf.ru",    "Admin компании Volvo",    "Только свои фуры/устройства"),
        ("91.188.212.119.nip.io","Симулятор / отладка",     "Legacy, без тенанта"),
    ]
    add_table(slide, ["URL", "Кто заходит", "Что видит"], rows,
              Inches(0.7), by + Inches(0.3), SW - Inches(1.4), Inches(2.5),
              col_widths=[Inches(3.5), Inches(3.5), Inches(4.9)], first_col_bold=True)
    box_y = by + Inches(3.2)
    add_rect(slide, Inches(0.7), box_y, SW - Inches(1.4), Inches(2), LIGHT, BORDER, 0.5)
    add_text(slide, "Как работает изоляция", Inches(0.95), box_y + Inches(0.15),
             Inches(8), Inches(0.4), size=15, bold=True, color=NAVY)
    add_bullets(slide, [
        "Wildcard-сертификат *.nonconf.ru (Let's Encrypt)",
        "Middleware на бэкенде резолвит tenant_id из Host-заголовка",
        "Все SQL-запросы фильтруются по tenant_id автоматически",
        "Запрос на acme.nonconf.ru с JWT компании Volvo → 403 tenant_mismatch",
    ], Inches(0.95), box_y + Inches(0.55), SW - Inches(1.9), Inches(1.4), size=13)
    footer_band(slide, idx, total)

@page
def s19(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Поток установки устройства",
                      "Атомарная привязка через 6-значный код")
    add_numbered(slide, [
        "Админ компании в ЛК → «Добавить устройство» → выдаётся код 428193 (TTL 30 мин, single-use)",
        "Установщик подключает ESP32 в фуру → автоматически поднимается SoftAP «VehicleLogger-XXXX»",
        "Подключение телефоном (пароль setup1234) → captive portal на 192.168.4.1",
        "Ввод: WiFi-сеть + пароль + поддомен компании + 6-значный код",
        "ESP подключается к WiFi → POST https://<sub>.nonconf.ru/api/devices/enroll",
        "Backend проверяет serial+secret+code → выдаёт API-ключ",
        "ESP сохраняет ключ в NVS → перезагружается → рабочий режим",
    ], Inches(0.7), by + Inches(0.2), SW - Inches(1.4), Inches(4.5), size=14)
    add_rect(slide, Inches(0.7), by + Inches(4.85), SW - Inches(1.4), Inches(0.55), SUCCESS)
    add_text(slide, "Один запрос. Никакого QR. Никакого поллинга.",
             Inches(0.7), by + Inches(4.85), SW - Inches(1.4), Inches(0.55),
             size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    footer_band(slide, idx, total)

@page
def s20(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Captive portal на ESP32",
                      "SoftAP + DNS catch-all + минимальный веб-сервер")
    add_bullets(slide, [
        "Wi-Fi точка доступа «VehicleLogger-XXXXXXXX»",
        "DNS catch-all: любой запрос → редирект на 192.168.4.1",
        "AsyncWebServer + LittleFS, HTML-страница ~6 КБ",
        "JSON API: /api/scan, /api/setup, /api/status, /api/info",
        "State machine: ввод → connect WiFi → POST /enroll → результат",
        "Маппинг ошибок: invalid_code / invalid_subdomain / already_claimed",
        "Каждая ошибка имеет своё сообщение для установщика на UI",
    ], Inches(0.7), by + Inches(0.3), Inches(7.0), Inches(4.5), size=14)
    photo_placeholder(slide, Inches(7.9), by + Inches(0.2), Inches(4.7), Inches(4.5),
                       "СКРИН: captive portal на телефоне\nс заполненными полями")
    footer_band(slide, idx, total)

@page
def s21(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Backend Тимура",
                      "Реализована наша спецификация 1:1")
    cw = Inches(4.0); ch = Inches(4.7); cy = by + Inches(0.2)
    def col(x, title, items, color):
        add_rect(slide, x, cy, cw, Inches(0.55), color)
        add_text(slide, title, x, cy, cw, Inches(0.55),
                 size=14, bold=True, color=WHITE,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        add_rect(slide, x, cy + Inches(0.55), cw, ch - Inches(0.55), LIGHT, BORDER, 0.5)
        tb = slide.shapes.add_textbox(x + Inches(0.1), cy + Inches(0.7),
                                      cw - Inches(0.2), ch - Inches(0.85))
        tf = tb.text_frame; tf.word_wrap = True
        for i, (method, path, descr) in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(8)
            r1 = p.add_run(); r1.text = f"{method:6}"
            r1.font.name = FONT_MONO; r1.font.size = Pt(11)
            r1.font.bold = True; r1.font.color.rgb = ORANGE
            r2 = p.add_run(); r2.text = path
            r2.font.name = FONT_MONO; r2.font.size = Pt(11); r2.font.color.rgb = NAVY
            p2 = tf.add_paragraph(); p2.space_after = Pt(8)
            r3 = p2.add_run(); r3.text = "  " + descr
            r3.font.name = FONT; r3.font.size = Pt(10); r3.font.color.rgb = MID

    col(Inches(0.6), "Без auth (для устройства)", [
        ("POST", "/api/devices/enroll",   "Атомарная привязка"),
        ("POST", "/api/telemetry",        "Bearer api_key"),
        ("POST", "/api/device/ping",      "Heartbeat"),
    ], NAVY)
    col(Inches(4.85), "JWT (admin компании)", [
        ("POST", "/api/enrollment-codes", "Выпуск 6-значного кода"),
        ("GET",  "/api/devices",          "Список устройств тенанта"),
        ("POST", "/api/devices/{id}/unclaim", "Отвязать"),
        ("POST", "/api/devices/{id}/rotate-key", "Ротация ключа"),
        ("GET",  "/api/vehicles/{id}/telemetry", "История для графиков"),
    ], NAVY2)
    col(Inches(9.1), "Super-admin (на apex)", [
        ("POST",   "/api/tenants",          "Создать компанию"),
        ("GET",    "/api/tenants",          "Список компаний"),
        ("DELETE", "/api/tenants/{id}",     "Удалить пустого"),
    ], ORANGE)
    footer_band(slide, idx, total)

@page
def s22(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Веб-админка тенанта", "Vue 3 + Vite + TypeScript")
    add_bullets(slide, [
        "Dashboard — KPI: онлайн-устройств, фур в движении, расход за день",
        "Список фур с last-seen статусом",
        "Страница фуры: графики (RPM, скорость, температура, расход)",
        "Устройства: статусы и кнопки unclaim / rotate-key",
        "Коды привязки: выдача и отзыв 6-значных кодов",
    ], Inches(0.7), by + Inches(0.3), Inches(6.5), Inches(4.5), size=14)
    photo_placeholder(slide, Inches(7.5), by + Inches(0.2), Inches(5.2), Inches(2.4),
                       "СКРИН: дашборд тенанта (KPI + список фур)")
    photo_placeholder(slide, Inches(7.5), by + Inches(2.8), Inches(5.2), Inches(2.0),
                       "СКРИН: график телеметрии за период")
    footer_band(slide, idx, total)

@page
def s23(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Безопасность")
    tile_h = Inches(1.4); ty = by + Inches(0.2)
    def fact(x, w, title, body, color):
        add_rect(slide, x, ty, w, tile_h, color)
        add_text(slide, title, x, ty + Inches(0.1), w, Inches(0.4),
                 size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(slide, body, x, ty + Inches(0.55), w, Inches(0.85),
                 size=11, color=WHITE, align=PP_ALIGN.CENTER)
    fact(Inches(0.7), Inches(4.0), "Транспорт",
         "ESP → backend только HTTPS\nWildcard *.nonconf.ru\n(Let's Encrypt)", NAVY)
    fact(Inches(4.85), Inches(4.0), "API-ключи",
         "64-hex (256 бит)\nBackend хранит SHA-256 хеш\nПри утечке — /rotate-key", NAVY2)
    fact(Inches(9.0), Inches(3.7), "Изоляция БД",
         "Middleware режет JWT по tenant_id\nЗапрос на чужой поддомен → 403", ORANGE)
    fy = ty + tile_h + Inches(0.4)
    add_text(slide, "Защита enroll-flow — три фактора",
             Inches(0.7), fy, Inches(8), Inches(0.4),
             size=17, bold=True, color=NAVY)
    add_numbered(slide, [
        "Физический доступ к устройству — для подключения к SoftAP",
        "Знание поддомена компании — где находится тенант",
        "6-значный код от админа — TTL 30 мин, single-use, привязан к одному тенанту",
    ], Inches(0.7), fy + Inches(0.5), SW - Inches(1.4), Inches(2), size=14)
    note_y = fy + Inches(2.5)
    add_rect(slide, Inches(0.7), note_y, SW - Inches(1.4), Inches(0.6), ORANGE)
    add_text(slide, "Опечатка в поддомене → код не пройдёт → устройство НЕ привяжется к чужой компании",
             Inches(0.7), note_y, SW - Inches(1.4), Inches(0.6),
             size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    footer_band(slide, idx, total)

@page
def s24(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Сводка работ — коммиты в git")
    rows = [
        ("1cc8a7a", "Этап 1", "Среда + диагностика + тестовый стенд",      "первичный setup"),
        ("32a1c61", "Этап 2", "Декодер J1939/OBD-II + auto-baud/proto",     "+982"),
        ("06dced1", "Этап 3", "Новая схема provisioning + NVS-обёртка",     "+535"),
        ("f4b0117", "Этап 3", "SoftAP + captive portal",                     "+346"),
        ("09699f8", "Этап 3", "HTTPS POST /enroll + cloud-модуль",          "+165"),
        ("aabde2e", "Этап 3", "Перенос J1939/OBD-II в production firmware", "+453"),
    ]
    add_table(slide, ["Коммит", "Этап", "Описание", "Строк"], rows,
              Inches(0.7), by + Inches(0.3), SW - Inches(1.4), Inches(3.0),
              col_widths=[Inches(1.6), Inches(1.4), Inches(7.5), Inches(1.4)],
              first_col_bold=True)
    ty = by + Inches(3.7); tw = Inches(3.85); th = Inches(1.4)
    def kpi(x, value, label, color=ORANGE):
        add_rect(slide, x, ty, tw, th, NAVY)
        add_text(slide, value, x, ty + Inches(0.1), tw, Inches(0.7),
                 size=30, bold=True, color=color, align=PP_ALIGN.CENTER)
        add_text(slide, label, x, ty + Inches(0.85), tw, Inches(0.5),
                 size=12, color=WHITE, align=PP_ALIGN.CENTER)
    kpi(Inches(0.7),  "~2500",  "строк C++/HTML/MD", ORANGE)
    kpi(Inches(4.75), "79.4 %", "Flash на ESP32",     SUCCESS)
    kpi(Inches(8.8),  "14.6 %", "RAM на ESP32",       SUCCESS)
    footer_band(slide, idx, total)

@page
def s25(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Roadmap — что дальше")
    cw = Inches(2.95); ch = Inches(4.7); cy = by + Inches(0.2)
    def stage(x, num, title, items):
        add_rect(slide, x, cy, cw, Inches(0.7), NAVY)
        add_text(slide, num, x, cy + Inches(0.05), cw, Inches(0.3),
                 size=10, bold=True, color=ORANGE, align=PP_ALIGN.CENTER)
        add_text(slide, title, x, cy + Inches(0.32), cw, Inches(0.4),
                 size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_rect(slide, x, cy + Inches(0.7), cw, ch - Inches(0.7), LIGHT, BORDER, 0.5)
        add_bullets(slide, items, x + Inches(0.15), cy + Inches(0.85),
                     cw - Inches(0.3), ch - Inches(0.95), size=11)
    stage(Inches(0.6),  "ЭТАП 4", "Working mode + телеметрия", [
        "WiFi connect from NVS",
        "CAN init с auto-baud",
        "POST /api/telemetry",
        "Heartbeat /ping",
        "Обработка 401/410",
    ])
    stage(Inches(3.75), "ЭТАП 5", "GPS + IMU интеграция", [
        "Координаты по GPS",
        "Скорость (cross-check с CAN)",
        "Резкое торможение",
        "Удар через MPU-6050",
    ])
    stage(Inches(6.9),  "ЭТАП 6", "Reset, LED, factory script", [
        "Кнопка сброса 5/10 сек",
        "LED-индикация",
        "Factory Python-скрипт",
        "Запись serial+secret",
    ])
    stage(Inches(10.05),"ЭТАП 7", "Буферизация и OTA", [
        "LittleFS-буфер",
        "Повторная отправка",
        "Watchdog timer",
        "HTTPS OTA с подписью",
    ])
    footer_band(slide, idx, total)

@page
def s26(idx, total):
    slide = prs.slides.add_slide(BLANK)
    by = header_band(slide, "Демонстрация",
                      "Live-привязка устройства от первого включения до телеметрии")
    add_numbered(slide, [
        "ESP32 включается «с завода» → boot-лог: VL-7A37F9D1, NVS пуст → SoftAP",
        "Подключение телефоном к Wi-Fi VehicleLogger-7A37F9D1",
        "Captive portal: WiFi + поддомен test + 6-значный код",
        "Submit → ESP подключается → POST /enroll → получает api_key",
        "В админке test.nonconf.ru появляется новое устройство со статусом claimed",
        "На стенде с USBCAN-2A — RPM/Speed обновляются в реальном времени",
    ], Inches(0.7), by + Inches(0.3), Inches(6.7), Inches(4.5), size=14)
    photo_placeholder(slide, Inches(7.6), by + Inches(0.2), Inches(5.0), Inches(4.6),
                       "СКРИН: дашборд во время живой\nдемонстрации")
    footer_band(slide, idx, total)

@page
def s27(idx, total):
    slide = prs.slides.add_slide(BLANK)
    add_rect(slide, 0, 0, SW, SH, NAVY)
    add_rect(slide, 0, 0, Inches(0.4), SH, ORANGE)
    add_text(slide, "Спасибо за внимание!",
             Inches(1), Inches(2.5), SW - Inches(2), Inches(1.2),
             size=56, bold=True, color=WHITE)
    add_text(slide, "Вопросы?",
             Inches(1), Inches(3.7), SW - Inches(2), Inches(0.7),
             size=28, color=ORANGE)
    add_rect(slide, Inches(1), Inches(4.6), Inches(2), Inches(0.05), ORANGE)
    add_text(slide, "🌐  nonconf.ru\n📧  ZoraidaGilbo356@outlook.com\n🔧  GitHub: feature/esp32-firmware",
             Inches(1), Inches(4.85), SW - Inches(2), Inches(2),
             size=16, color=WHITE)

TOTAL = len(SLIDES)
for i, fn in enumerate(SLIDES, 1):
    fn(i, TOTAL)

OUT = r"c:\Users\Huanan\Desktop\Projects\VehicleLogger\presentation.pptx"
prs.save(OUT)
print(f"saved: {OUT}  ({TOTAL} slides)")