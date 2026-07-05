from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).parent / "test_invoices"
W, H = 1240, 1754
MARGIN = 90
ITEMS_PER_PAGE = 9
DARK = (32, 34, 38)
GRAY = (108, 114, 122)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def font_mono(size: int) -> ImageFont.FreeTypeFont:
    for name in ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def fit_text(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: float) -> str:
    if d.textlength(text, font=f) <= max_w:
        return text
    while text and d.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text + "…"


def fmt_usd(v: float) -> str:
    return f"${v:,.2f}"


def fmt_eur(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def fmt_uzs(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ") + " сум"


def fmt_rub(v: float) -> str:
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


@dataclass
class InvoiceSpec:
    filename: str
    layout: str
    accent: tuple[int, int, int]
    title: str
    vendor_lines: list[str]
    customer_label: str
    customer_lines: list[str]
    number_label: str
    number: str
    date_label: str
    date: str
    col_labels: tuple[str, str, str, str]
    items: list[tuple[str, float, float]]
    money: Callable[[float], str]
    subtotal_label: str
    tax_label: str
    tax_rate: float
    total_label: str
    footer: str
    page_label: str = "Page"


def _draw_header(d: ImageDraw.ImageDraw, spec: InvoiceSpec) -> int:
    big, small = font(46, bold=True), font(26)
    title_f, meta_f = font(58, bold=True), font(28)
    y = MARGIN
    if spec.layout in ("left", "right"):
        vx, va = (MARGIN, "la") if spec.layout == "left" else (W - MARGIN, "ra")
        tx, ta = (W - MARGIN, "ra") if spec.layout == "left" else (MARGIN, "la")
        d.text((vx, y), spec.vendor_lines[0], font=big, fill=spec.accent, anchor=va)
        yy = y + 66
        for line in spec.vendor_lines[1:]:
            d.text((vx, yy), line, font=small, fill=GRAY, anchor=va)
            yy += 36
        d.text((tx, y), spec.title, font=title_f, fill=DARK, anchor=ta)
        d.text((tx, y + 88), f"{spec.number_label}: {spec.number}", font=meta_f, fill=DARK, anchor=ta)
        d.text((tx, y + 128), f"{spec.date_label}: {spec.date}", font=meta_f, fill=DARK, anchor=ta)
        y = max(yy, y + 168) + 30
    else:
        d.text((W // 2, y), spec.vendor_lines[0], font=big, fill=spec.accent, anchor="ma")
        yy = y + 66
        for line in spec.vendor_lines[1:]:
            d.text((W // 2, yy), line, font=small, fill=GRAY, anchor="ma")
            yy += 36
        d.text((W // 2, yy + 14), spec.title, font=title_f, fill=DARK, anchor="ma")
        yy += 14 + 74
        d.line((MARGIN, yy, W - MARGIN, yy), fill=spec.accent, width=3)
        yy += 20
        d.text((MARGIN, yy), f"{spec.number_label}: {spec.number}", font=meta_f, fill=DARK)
        d.text((W - MARGIN, yy), f"{spec.date_label}: {spec.date}", font=meta_f, fill=DARK, anchor="ra")
        y = yy + 70
    d.text((MARGIN, y), spec.customer_label, font=font(26, bold=True), fill=spec.accent)
    yy = y + 40
    for line in spec.customer_lines:
        d.text((MARGIN, yy), line, font=font(26), fill=DARK)
        yy += 34
    return yy + 36


def _draw_continuation_header(d: ImageDraw.ImageDraw, spec: InvoiceSpec) -> int:
    d.text(
        (MARGIN, MARGIN),
        f"{spec.vendor_lines[0]} — {spec.number_label} {spec.number}",
        font=font(30, bold=True),
        fill=spec.accent,
    )
    return MARGIN + 76


def _draw_items_table(
    d: ImageDraw.ImageDraw, spec: InvoiceSpec, items: list[tuple[str, float, float]], y: int
) -> int:
    x0, x1 = MARGIN, W - MARGIN
    sum_r, price_r, qty_r = x1 - 16, x1 - 210, x1 - 380
    name_x = x0 + 16
    name_max = qty_r - 130 - name_x
    hf, rf = font(26, bold=True), font(27)
    d.rectangle((x0, y, x1, y + 54), fill=spec.accent)
    cy = y + 27
    d.text((name_x, cy), spec.col_labels[0], font=hf, fill="white", anchor="lm")
    d.text((qty_r, cy), spec.col_labels[1], font=hf, fill="white", anchor="rm")
    d.text((price_r, cy), spec.col_labels[2], font=hf, fill="white", anchor="rm")
    d.text((sum_r, cy), spec.col_labels[3], font=hf, fill="white", anchor="rm")
    y += 54
    for i, (name, qty, price) in enumerate(items):
        if i % 2 == 0:
            d.rectangle((x0, y, x1, y + 50), fill=(246, 248, 251))
        cy = y + 25
        d.text((name_x, cy), fit_text(d, name, rf, name_max), font=rf, fill=DARK, anchor="lm")
        d.text((qty_r, cy), f"{qty:g}", font=rf, fill=DARK, anchor="rm")
        d.text((price_r, cy), spec.money(price), font=rf, fill=DARK, anchor="rm")
        d.text((sum_r, cy), spec.money(round(qty * price, 2)), font=rf, fill=DARK, anchor="rm")
        y += 50
    d.line((x0, y, x1, y), fill=(198, 204, 212), width=2)
    return y + 28


def _draw_totals(d: ImageDraw.ImageDraw, spec: InvoiceSpec, y: int) -> int:
    sum_r = W - MARGIN - 16
    label_r = W - MARGIN - 400
    subtotal = round(sum(round(q * p, 2) for _, q, p in spec.items), 2)
    tax = round(subtotal * spec.tax_rate, 2)
    total = round(subtotal + tax, 2)
    rf = font(28)
    d.text((label_r, y), spec.subtotal_label, font=rf, fill=GRAY, anchor="ra")
    d.text((sum_r, y), spec.money(subtotal), font=rf, fill=DARK, anchor="ra")
    y += 46
    if spec.tax_rate:
        d.text((label_r, y), spec.tax_label, font=rf, fill=GRAY, anchor="ra")
        d.text((sum_r, y), spec.money(tax), font=rf, fill=DARK, anchor="ra")
        y += 46
    d.line((W - MARGIN - 560, y, W - MARGIN, y), fill=spec.accent, width=3)
    y += 18
    bf = font(34, bold=True)
    d.text((label_r, y), spec.total_label, font=bf, fill=spec.accent, anchor="ra")
    d.text((sum_r, y), spec.money(total), font=bf, fill=spec.accent, anchor="ra")
    return y + 90


def render_invoice_pages(spec: InvoiceSpec) -> list[Image.Image]:
    chunks = [spec.items[i : i + ITEMS_PER_PAGE] for i in range(0, len(spec.items), ITEMS_PER_PAGE)]
    pages = []
    for pi, chunk in enumerate(chunks):
        img = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(img)
        y = _draw_header(d, spec) if pi == 0 else _draw_continuation_header(d, spec)
        y = _draw_items_table(d, spec, chunk, y)
        if pi == len(chunks) - 1:
            y = _draw_totals(d, spec, y)
            d.text((MARGIN, H - 150), spec.footer, font=font(24), fill=GRAY)
        if len(chunks) > 1:
            d.text(
                (W // 2, H - 70),
                f"{spec.page_label} {pi + 1}/{len(chunks)}",
                font=font(24),
                fill=GRAY,
                anchor="mm",
            )
        pages.append(img)
    return pages


def render_receipt() -> Image.Image:
    items = [
        ("Молоко 3,2% 1л", 2, 89.90),
        ("Хлеб бородинский", 1, 54.00),
        ("Сыр Гауда 250г", 1, 259.90),
        ("Яблоки Гала, кг", 1.42, 129.90),
        ("Вода минеральная 1,5л", 3, 42.50),
    ]
    total = round(sum(round(q * p, 2) for _, q, p in items), 2)
    vat = round(total * 20 / 120, 2)

    rw = 660
    img = Image.new("RGB", (rw, 1400), "white")
    d = ImageDraw.Draw(img)
    m_big, m, m_small = font_mono(34), font_mono(26), font_mono(24)
    y = 50
    for line, f in [
        ("ПРОДУКТЫ 24", m_big),
        ('ООО "РИТЕЙЛ ГРУПП"', m_small),
        ("г. Москва, ул. Лесная, д. 7", m_small),
        ("ИНН 7719402886", m_small),
    ]:
        d.text((rw // 2, y), line, font=f, fill="black", anchor="ma")
        y += 44 if f is m_big else 32
    y += 10
    d.text((rw // 2, y), "-" * 34, font=m, fill="black", anchor="ma")
    y += 40
    d.text((40, y), "КАССОВЫЙ ЧЕК № 4821", font=m, fill="black")
    y += 34
    d.text((40, y), "14.06.2026 18:42  КАССА 2", font=m, fill="black")
    y += 44
    for name, qty, price in items:
        d.text((40, y), name, font=m, fill="black")
        y += 32
        line = f"{qty:g} x {fmt_rub(price)} = {fmt_rub(round(qty * price, 2))}"
        d.text((rw - 40, y), line, font=m, fill="black", anchor="ra")
        y += 40
    d.text((rw // 2, y), "-" * 34, font=m, fill="black", anchor="ma")
    y += 44
    d.text((40, y), "ИТОГО:", font=m_big, fill="black")
    d.text((rw - 40, y), f"{fmt_rub(total)} РУБ", font=m_big, fill="black", anchor="ra")
    y += 56
    d.text((40, y), f"В Т.Ч. НДС 20%: {fmt_rub(vat)}", font=m_small, fill="black")
    y += 40
    d.text((40, y), "НАЛИЧНЫМИ: 1000,00", font=m_small, fill="black")
    y += 32
    d.text((40, y), f"СДАЧА: {fmt_rub(round(1000 - total, 2))}", font=m_small, fill="black")
    y += 50
    d.text((rw // 2, y), "СПАСИБО ЗА ПОКУПКУ!", font=m, fill="black", anchor="ma")
    y += 70
    img = img.crop((0, 0, rw, y))
    img = img.rotate(-2.5, expand=True, fillcolor=(213, 214, 218), resample=Image.BICUBIC)
    return img.filter(ImageFilter.GaussianBlur(0.6))


SPECS = [
    InvoiceSpec(
        filename="invoice_01_us.png",
        layout="left",
        accent=(23, 62, 112),
        title="INVOICE",
        vendor_lines=[
            "Northwind Office Supplies",
            "4820 Market Street, Suite 210",
            "Philadelphia, PA 19104",
            "(215) 555-0134",
        ],
        customer_label="BILL TO",
        customer_lines=["Maple & Co. Accounting", "112 Chestnut Ave", "Cherry Hill, NJ 08002"],
        number_label="Invoice No",
        number="INV-2026-0387",
        date_label="Date",
        date="May 12, 2026",
        col_labels=("Description", "Qty", "Unit price", "Amount"),
        items=[
            ("Copy paper A4 80gsm (box of 5 reams)", 4, 24.90),
            ("Heavy-duty stapler", 2, 18.50),
            ("Ink cartridge HP 305XL black", 3, 34.99),
            ("Whiteboard markers (pack of 8)", 5, 9.75),
            ("Bamboo desk organizer", 2, 27.40),
        ],
        money=fmt_usd,
        subtotal_label="Subtotal",
        tax_label="Sales tax (8%)",
        tax_rate=0.08,
        total_label="TOTAL",
        footer="Payment due within 30 days.  Wire transfer to First Keystone Bank, acc. 4402-118837.",
    ),
    InvoiceSpec(
        filename="invoice_02_de.png",
        layout="right",
        accent=(21, 96, 61),
        title="RECHNUNG",
        vendor_lines=[
            "Bergmann Werkzeuge GmbH",
            "Hauptstraße 27",
            "80331 München",
            "USt-IdNr. DE812947360",
        ],
        customer_label="RECHNUNGSEMPFÄNGER",
        customer_lines=["Schneider Bau AG", "Industriering 4", "85049 Ingolstadt"],
        number_label="Rechnungs-Nr.",
        number="RE-2026-1142",
        date_label="Datum",
        date="03.06.2026",
        col_labels=("Beschreibung", "Menge", "Einzelpreis", "Betrag"),
        items=[
            ("Akkuschrauber 18V Profi-Set", 1, 129.00),
            ("Schraubenset 200-tlg.", 3, 24.50),
            ("Arbeitshandschuhe Gr. 9", 10, 6.90),
            ("Wasserwaage 60 cm", 2, 15.80),
        ],
        money=fmt_eur,
        subtotal_label="Zwischensumme",
        tax_label="MwSt. (19%)",
        tax_rate=0.19,
        total_label="GESAMT",
        footer="Zahlbar innerhalb von 14 Tagen ohne Abzug.  IBAN DE89 7002 0270 0012 3456 78",
        page_label="Seite",
    ),
    InvoiceSpec(
        filename="invoice_03_uz.png",
        layout="center",
        accent=(0, 105, 110),
        title="СЧЁТ-ФАКТУРА",
        vendor_lines=[
            "OOO «Диёр Сервис»",
            "г. Ташкент, ул. Амира Темура, 41",
            "ИНН 305412873",
        ],
        customer_label="ПОКУПАТЕЛЬ",
        customer_lines=["ЧП «Барака Маркет»", "г. Ташкент, Чиланзарский р-н, 12-квартал"],
        number_label="№",
        number="ДС-458",
        date_label="Дата",
        date="21.05.2026",
        col_labels=("Наименование", "Кол-во", "Цена", "Сумма"),
        items=[
            ("Картридж лазерный HP 106A", 2, 385000),
            ("Клавиатура USB Logitech K120", 5, 120000),
            ("Мышь беспроводная", 5, 95000),
            ("Кабель HDMI 2м", 8, 45000),
            ("Установка и настройка ПО (услуга)", 1, 250000),
        ],
        money=fmt_uzs,
        subtotal_label="Итого без НДС",
        tax_label="НДС (12%)",
        tax_rate=0.12,
        total_label="ВСЕГО К ОПЛАТЕ",
        footer="Оплата в течение 10 банковских дней.  р/с 2020 8000 3005 4128 7300 1, МФО 00450",
    ),
    InvoiceSpec(
        filename="invoice_05_multipage.pdf",
        layout="left",
        accent=(90, 42, 130),
        title="INVOICE",
        vendor_lines=[
            "Atlas Web Studio LLC",
            "hello@atlasweb.studio",
            "Tashkent, Uzbekistan",
        ],
        customer_label="BILL TO",
        customer_lines=["GreenCart e-commerce", "Berlin, Germany"],
        number_label="Invoice No",
        number="AWS-2026-071",
        date_label="Date",
        date="June 10, 2026",
        col_labels=("Description", "Qty", "Unit price", "Amount"),
        items=[
            ("Landing page design", 1, 900),
            ("Frontend development (hour)", 32, 45),
            ("Backend API development (hour)", 40, 50),
            ("CMS integration", 1, 600),
            ("SEO audit", 1, 350),
            ("Copywriting (page)", 6, 80),
            ("Logo refresh", 1, 400),
            ("Hosting setup", 1, 120),
            ("SSL certificate (year)", 1, 90),
            ("Maintenance — June", 1, 250),
            ("Maintenance — July", 1, 250),
            ("Stock photos pack", 2, 60),
            ("Email templates", 3, 110),
            ("Analytics setup", 1, 180),
        ],
        money=fmt_usd,
        subtotal_label="Subtotal",
        tax_label="",
        tax_rate=0.0,
        total_label="TOTAL",
        footer="Payment via wire transfer or Payoneer within 15 days.  Thank you for your business!",
    ),
]


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    created = []
    for spec in SPECS:
        pages = render_invoice_pages(spec)
        out = OUT_DIR / spec.filename
        if out.suffix == ".pdf":
            pages[0].save(out, save_all=True, append_images=pages[1:], resolution=150)
        else:
            pages[0].save(out)
        created.append(f"{out.name} ({len(pages)} page{'s' if len(pages) > 1 else ''})")
    receipt = render_receipt()
    receipt_path = OUT_DIR / "invoice_04_receipt_rotated.png"
    receipt.save(receipt_path)
    created.append(f"{receipt_path.name} (rotated photo simulation)")
    print("Created in test_invoices/:")
    for name in sorted(created):
        print(f"  - {name}")


if __name__ == "__main__":
    main()
