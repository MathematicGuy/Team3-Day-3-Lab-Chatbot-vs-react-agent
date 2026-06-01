"""
invoice_tools.py
~~~~~~~~~~~~~~~~
Tool tạo hóa đơn đặt vé máy bay.

Cách dùng (agent gọi sau khi người dùng chốt mua):

    from tools.invoice_tools import generate_invoice

    invoice = generate_invoice(
        passenger_name="Nguyen Van A",
        passenger_email="vana@email.com",
        passenger_phone="0901234567",
        flight_id="flight-854624",
        airline="British Airways",
        flight_number="BA 301",
        departure_airport="CDG",
        arrival_airport="SYD",
        departure_time="2026-03-03 10:10",
        arrival_time="2026-03-03 16:50",
        duration="13h 40m",
        stops=1,
        stop_info="Heathrow Airport",
        travel_class="economy",
        passengers=1,
        price_per_person=520.0,
        currency="USD",
        booking_link="https://www.google.com/travel/flights?booking_token=...",
    )

    # invoice["receipt_text"]  → chuỗi hóa đơn đẹp, in ra chat
    # invoice["invoice_data"]  → dict đầy đủ để lưu DB / xử lý tiếp
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Pydantic model — validate input trước khi tạo hóa đơn
# ---------------------------------------------------------------------------

class InvoiceRequest(BaseModel):
    # --- Thông tin hành khách ---
    passenger_name: str = Field(..., min_length=2, description="Họ tên hành khách")
    passenger_email: Optional[str] = Field(None, description="Email hành khách")
    passenger_phone: Optional[str] = Field(None, description="Số điện thoại")

    # --- Thông tin chuyến bay (lấy từ kết quả search_flights) ---
    flight_id: str = Field(..., description="ID chuyến bay")
    airline: str = Field(..., description="Hãng hàng không")
    flight_number: Optional[str] = Field(None, description="Số hiệu chuyến bay")
    departure_airport: str = Field(..., min_length=3, max_length=3)
    arrival_airport: str = Field(..., min_length=3, max_length=3)
    departure_time: str = Field(..., description="Giờ khởi hành, vd: '2026-03-03 10:10'")
    arrival_time: str = Field(..., description="Giờ đến, vd: '2026-03-03 16:50'")
    duration: str = Field(..., description="Thời gian bay, vd: '13h 40m'")
    stops: int = Field(default=0, ge=0)
    stop_info: Optional[str] = Field(None, description="Thông tin điểm dừng")
    travel_class: str = Field(default="economy")
    passengers: int = Field(default=1, ge=1, le=9, description="Số hành khách")

    # --- Thông tin giá ---
    price_per_person: float = Field(..., gt=0, description="Giá mỗi người")
    currency: str = Field(default="USD")
    booking_link: Optional[str] = Field(None, description="Link đặt vé")

    @field_validator("departure_airport", "arrival_airport", mode="before", check_fields=False)
    @classmethod
    def _upper_airport(cls, v):
        return str(v).strip().upper()

    @field_validator("travel_class", mode="before", check_fields=False)
    @classmethod
    def _normalize_class(cls, v):
        return str(v).strip().lower()

    @field_validator("currency", mode="before", check_fields=False)
    @classmethod
    def _upper_currency(cls, v):
        return str(v).strip().upper()


class InvoiceException(Exception):
    pass


# ---------------------------------------------------------------------------
# Template hóa đơn
# ---------------------------------------------------------------------------

_INVOICE_TEMPLATE = """\
╔══════════════════════════════════════════════════════════════╗
║              ✈  XÁC NHẬN ĐẶT VÉ MÁY BAY                    ║
╚══════════════════════════════════════════════════════════════╝

  Mã đặt vé  : {booking_ref}
  Ngày xuất  : {issued_at}

──────────────────────────────────────────────────────────────
  THÔNG TIN HÀNH KHÁCH
──────────────────────────────────────────────────────────────
  Họ tên     : {passenger_name}
  Email      : {passenger_email}
  Điện thoại : {passenger_phone}

──────────────────────────────────────────────────────────────
  THÔNG TIN CHUYẾN BAY
──────────────────────────────────────────────────────────────
  Hãng bay   : {airline}{flight_number_line}
  Hành trình : {departure_airport} → {arrival_airport}
  Khởi hành  : {departure_time}
  Hạ cánh    : {arrival_time}
  Thời gian  : {duration}
  Điểm dừng  : {stops_text}
  Hạng vé    : {travel_class_label}
  Hành khách : {passengers} người

──────────────────────────────────────────────────────────────
  CHI TIẾT GIÁ VÉ
──────────────────────────────────────────────────────────────
  Giá / người: {price_per_person:,.2f} {currency}
  Số người   : {passengers}
  Phí dịch vụ: {service_fee:,.2f} {currency}
  ─────────────────────────────────────────────
  TỔNG CỘNG  : {total_price:,.2f} {currency}

──────────────────────────────────────────────────────────────
  ĐẶT VÉ
──────────────────────────────────────────────────────────────
  {booking_link_line}

══════════════════════════════════════════════════════════════
  Cảm ơn bạn đã sử dụng dịch vụ! Chúc bạn có chuyến bay vui.
══════════════════════════════════════════════════════════════
"""

_CLASS_LABELS = {
    "economy": "Phổ thông (Economy)",
    "premium_economy": "Phổ thông đặc biệt (Premium Economy)",
    "business": "Thương gia (Business)",
    "first": "Hạng nhất (First Class)",
}

_SERVICE_FEE_RATE = 0.05  # 5% phí dịch vụ mock


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_invoice(
    passenger_name: str,
    flight_id: str,
    airline: str,
    departure_airport: str,
    arrival_airport: str,
    departure_time: str,
    arrival_time: str,
    duration: str,
    price_per_person: float,
    passenger_email: Optional[str] = None,
    passenger_phone: Optional[str] = None,
    flight_number: Optional[str] = None,
    stops: int = 0,
    stop_info: Optional[str] = None,
    travel_class: str = "economy",
    passengers: int = 1,
    currency: str = "USD",
    booking_link: Optional[str] = None,
) -> dict:
    """
    Tạo hóa đơn xác nhận đặt vé máy bay.

    Returns:
        {
            "status": "success",
            "booking_ref": "<mã đặt vé>",
            "receipt_text": "<hóa đơn dạng text đẹp, in ra chat>",
            "invoice_data": { ...toàn bộ thông tin dạng dict... }
        }
    """
    # --- Validate ---
    try:
        req = InvoiceRequest(
            passenger_name=passenger_name,
            passenger_email=passenger_email,
            passenger_phone=passenger_phone,
            flight_id=flight_id,
            airline=airline,
            flight_number=flight_number,
            departure_airport=departure_airport,
            arrival_airport=arrival_airport,
            departure_time=departure_time,
            arrival_time=arrival_time,
            duration=duration,
            stops=stops,
            stop_info=stop_info,
            travel_class=travel_class,
            passengers=passengers,
            price_per_person=price_per_person,
            currency=currency,
            booking_link=booking_link,
        )
    except Exception as exc:
        raise InvoiceException(f"Thông tin hóa đơn không hợp lệ: {exc}")

    # --- Tính giá ---
    subtotal = req.price_per_person * req.passengers
    service_fee = round(subtotal * _SERVICE_FEE_RATE, 2)
    total_price = round(subtotal + service_fee, 2)

    # --- Tạo mã đặt vé ngẫu nhiên ---
    booking_ref = "BK-" + uuid.uuid4().hex[:8].upper()
    issued_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Render các trường phụ ---
    flight_number_line = f" ({req.flight_number})" if req.flight_number else ""
    stops_text = (
        f"Không dừng (Bay thẳng)"
        if req.stops == 0
        else f"{req.stops} điểm dừng — {req.stop_info or ''}"
    )
    travel_class_label = _CLASS_LABELS.get(req.travel_class, req.travel_class.title())
    booking_link_line = req.booking_link if req.booking_link else "N/A"

    # --- Render template ---
    receipt_text = _INVOICE_TEMPLATE.format(
        booking_ref=booking_ref,
        issued_at=issued_at,
        passenger_name=req.passenger_name,
        passenger_email=req.passenger_email or "N/A",
        passenger_phone=req.passenger_phone or "N/A",
        airline=req.airline,
        flight_number_line=flight_number_line,
        departure_airport=req.departure_airport,
        arrival_airport=req.arrival_airport,
        departure_time=req.departure_time,
        arrival_time=req.arrival_time,
        duration=req.duration,
        stops_text=stops_text,
        travel_class_label=travel_class_label,
        passengers=req.passengers,
        price_per_person=req.price_per_person,
        currency=req.currency,
        service_fee=service_fee,
        total_price=total_price,
        booking_link_line=booking_link_line,
    )

    invoice_data = {
        "booking_ref": booking_ref,
        "issued_at": issued_at,
        "passenger": {
            "name": req.passenger_name,
            "email": req.passenger_email,
            "phone": req.passenger_phone,
        },
        "flight": {
            "flight_id": req.flight_id,
            "airline": req.airline,
            "flight_number": req.flight_number,
            "departure_airport": req.departure_airport,
            "arrival_airport": req.arrival_airport,
            "departure_time": req.departure_time,
            "arrival_time": req.arrival_time,
            "duration": req.duration,
            "stops": req.stops,
            "stop_info": req.stop_info,
            "travel_class": req.travel_class,
        },
        "pricing": {
            "price_per_person": req.price_per_person,
            "passengers": req.passengers,
            "subtotal": subtotal,
            "service_fee": service_fee,
            "total_price": total_price,
            "currency": req.currency,
        },
        "booking_link": req.booking_link,
    }

    return {
        "status": "success",
        "booking_ref": booking_ref,
        "receipt_text": receipt_text,
        "invoice_data": invoice_data,
    }


# ---------------------------------------------------------------------------
# PDF Invoice — dùng fpdf2
# ---------------------------------------------------------------------------

# PDF-safe cabin class labels (ASCII only — Helvetica cannot handle Vietnamese)
_PDF_CLASS_LABELS = {
    "economy": "Economy",
    "premium_economy": "Premium Economy",
    "business": "Business",
    "first": "First Class",
}


def generate_invoice_pdf(
    invoice_result: dict,
    output_path: Optional[str] = None,
) -> dict:
    """
    Tạo file PDF hóa đơn từ kết quả trả về của generate_invoice().

    Args:
        invoice_result : dict trả về từ generate_invoice()
        output_path    : đường dẫn lưu file PDF.
                         Mặc định: "invoice_<booking_ref>.pdf" tại thư mục hiện tại.

    Returns:
        {
            "status": "success",
            "pdf_path": "<đường dẫn tuyệt đối file PDF>",
            "booking_ref": "<mã đặt vé>",
        }
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise InvoiceException(
            "Thư viện fpdf2 chưa được cài. Chạy: pip install fpdf2"
        )

    import os

    data = invoice_result.get("invoice_data", {})
    booking_ref = invoice_result.get("booking_ref", "N/A")
    passenger = data.get("passenger", {})
    flight = data.get("flight", {})
    pricing = data.get("pricing", {})
    booking_link = data.get("booking_link") or "N/A"

    if output_path is None:
        output_path = f"invoice_{booking_ref}.pdf"
    output_path = os.path.abspath(output_path)

    # ---- Màu sắc ----
    BRAND_R, BRAND_G, BRAND_B = 30, 90, 180       # xanh dương đậm
    ACCENT_R, ACCENT_G, ACCENT_B = 240, 248, 255   # xanh nhạt (nền section)
    GRAY_R, GRAY_G, GRAY_B = 100, 100, 100
    GREEN_R, GREEN_G, GREEN_B = 20, 130, 60        # tổng cộng

    class InvoicePDF(FPDF):
        def header(self):
            # Banner nền xanh
            self.set_fill_color(BRAND_R, BRAND_G, BRAND_B)
            self.rect(0, 0, 210, 32, "F")
            # Icon máy bay + tiêu đề
            self.set_font("Helvetica", "B", 18)
            self.set_text_color(255, 255, 255)
            self.set_xy(10, 8)
            self.cell(0, 10, "  FLIGHT BOOKING CONFIRMATION", align="L")
            # Subtitle
            self.set_font("Helvetica", "", 9)
            self.set_xy(10, 20)
            self.cell(0, 6, "Your e-ticket receipt - please keep this for your records", align="L")
            self.ln(20)

        def footer(self):
            self.set_y(-14)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(GRAY_R, GRAY_G, GRAY_B)
            self.cell(0, 10, f"Page {self.page_no()} | Generated by Flight Booking System", align="C")

    pdf = InvoicePDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(14, 36, 14)

    # ---- Helper: section title ----
    def section_title(title: str):
        pdf.set_fill_color(ACCENT_R, ACCENT_G, ACCENT_B)
        pdf.set_text_color(BRAND_R, BRAND_G, BRAND_B)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 8, f"  {title}", border="B", fill=True, ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    # ---- Helper: hai cột key-value ----
    def kv(label: str, value: str):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(GRAY_R, GRAY_G, GRAY_B)
        pdf.cell(45, 7, label, ln=False)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 7, str(value), ln=True)

    # ---- Booking ref + date ----
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(BRAND_R, BRAND_G, BRAND_B)
    pdf.cell(0, 8, f"Booking Reference: {booking_ref}", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(GRAY_R, GRAY_G, GRAY_B)
    pdf.cell(0, 6, f"Issue Date: {invoice_result.get('invoice_data', {}).get('issued_at', 'N/A')}", ln=True)
    pdf.ln(4)

    # ---- PASSENGER ----
    section_title("PASSENGER INFORMATION")
    kv("Name", passenger.get("name", "N/A"))
    kv("Email", passenger.get("email") or "N/A")
    kv("Phone", passenger.get("phone") or "N/A")
    pdf.ln(4)

    # ---- FLIGHT ----
    section_title("FLIGHT DETAILS")
    fn = flight.get("flight_number")
    airline_str = flight.get("airline", "N/A")
    if fn:
        airline_str += f"  ({fn})"
    kv("Airline", airline_str)
    kv("Route", f"{flight.get('departure_airport','?')}  ->  {flight.get('arrival_airport','?')}")
    kv("Departure", flight.get("departure_time", "N/A"))
    kv("Arrival", flight.get("arrival_time", "N/A"))
    kv("Duration", flight.get("duration", "N/A"))
    stops = flight.get("stops", 0)
    stop_info = flight.get("stop_info") or ""
    stops_str = "Non-stop" if stops == 0 else f"{stops} stop(s) via {stop_info}"
    kv("Stops", stops_str)
    kv("Cabin", _PDF_CLASS_LABELS.get(flight.get("travel_class", "economy"), "Economy"))
    kv("Passengers", str(pricing.get("passengers", 1)))
    pdf.ln(4)

    # ---- PRICING TABLE ----
    section_title("PRICE BREAKDOWN")
    cur = pricing.get("currency", "USD")

    def price_row(label, amount, bold=False, color=None):
        if bold:
            pdf.set_font("Helvetica", "B", 10)
        else:
            pdf.set_font("Helvetica", "", 9)
        if color:
            pdf.set_text_color(*color)
        else:
            pdf.set_text_color(0, 0, 0)
        pdf.cell(120, 8, label)
        pdf.cell(0, 8, f"{amount:,.2f} {cur}", align="R", ln=True)
        pdf.set_text_color(0, 0, 0)

    price_row(
        f"Base fare x {pricing.get('passengers',1)} pax",
        pricing.get("subtotal", 0),
    )
    price_row("Service fee (5%)", pricing.get("service_fee", 0))
    # Đường kẻ
    pdf.set_draw_color(BRAND_R, BRAND_G, BRAND_B)
    pdf.set_line_width(0.5)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(1)
    price_row(
        "TOTAL",
        pricing.get("total_price", 0),
        bold=True,
        color=(GREEN_R, GREEN_G, GREEN_B),
    )
    pdf.ln(5)

    # ---- BOOKING LINK ----
    section_title("BOOK NOW")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(BRAND_R, BRAND_G, BRAND_B)
    pdf.multi_cell(0, 6, booking_link)
    pdf.ln(6)

    # ---- Footer banner ----
    pdf.set_fill_color(BRAND_R, BRAND_G, BRAND_B)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 10, "  Thank you for booking with us! Have a great flight.", fill=True, ln=True)

    pdf.output(output_path)

    return {
        "status": "success",
        "pdf_path": output_path,
        "booking_ref": booking_ref,
    }

