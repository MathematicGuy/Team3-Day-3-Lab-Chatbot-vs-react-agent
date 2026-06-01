# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyen Anh Quan
- **Student ID**: 2A202600589
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

*Implemented two flight-related tools for the ReAct agent: a flight search tool backed by mock data (no API call) and an invoice generation tool that produces both a text receipt and a professional PDF.*

- **Modules Implemented**:
  - `src/tools/flight_tools.py`
  - `src/tools/invoice_tools.py`

- **Code Highlights**:

  **1. `search_flights` — đọc từ `data.json` thay vì gọi SerpAPI**

  ```python
  # Load mock data once at import time
  _MOCK_DATA: Dict[str, Any] = {}
  if _MOCK_DATA_PATH.exists():
      with open(_MOCK_DATA_PATH, encoding="utf-8") as _f:
          _MOCK_DATA = json.load(_f)

  def search_flights(
      departure_airport: str,
      arrival_airport: str,
      departure_date: str,
      return_date: Optional[str] = None,
      passengers: int = 1,
      travel_class: str = "economy",
      currency: str = "USD",
      sort_by: str = "price",        # "price" | "airline" | "departure_time" | "duration_minutes"
  ) -> Dict[str, Any]:
      ...
      flights = _load_flights_from_mock(params)
      flights.sort(key=lambda f: f.price)   # ví dụ sort theo giá
      return {"status": "success", "count": len(flights), "flights": [...]}
  ```

  **2. `generate_invoice` + `generate_invoice_pdf` — tạo hóa đơn text và PDF**

  ```python
  # Text invoice
  inv = generate_invoice(
      passenger_name="Nguyen Van An",
      flight_id="flight-854624",
      airline="British Airways",
      departure_airport="CDG", arrival_airport="AUS",
      departure_time="2026-03-03 10:10", arrival_time="2026-03-03 16:50",
      duration="13h 40m", stops=1, stop_info="London Heathrow (LHR)",
      passengers=2, price_per_person=520.0, currency="USD",
  )
  # => {"booking_ref": "BK-XXXXXXXX", "receipt_text": "...", "invoice_data": {...}}

  # PDF invoice (dùng fpdf2)
  pdf = generate_invoice_pdf(inv, output_path="invoice_BK-XXX.pdf")
  # => {"status": "success", "pdf_path": "D:/...invoice_BK-XXX.pdf"}
  ```

- **Documentation**:

  **`flight_tools.py` — tích hợp vào ReAct loop:**

  Khi người dùng hỏi tìm chuyến bay, agent gọi `search_flights()` với các tham số IATA code, ngày bay, hạng vé. Tool validate input qua Pydantic (`FlightSearchParams`), sau đó đọc `data.json` (mock SerpAPI response) và parse ra danh sách `FlightResult`. Kết quả trả về là dict chuẩn `{"status", "count", "flights": [...]}` mà agent dùng làm **Observation** để tạo **Thought** tiếp theo.

  Tham số `sort_by` cho phép agent tự động sắp xếp kết quả theo yêu cầu ngôn ngữ tự nhiên của người dùng (ví dụ: *"sắp xếp theo giá"* → `sort_by="price"`).

  **`invoice_tools.py` — tích hợp vào ReAct loop:**

  Sau khi người dùng xác nhận mua vé, agent gọi `generate_invoice()` với thông tin hành khách + dữ liệu chuyến bay đã lấy từ `search_flights`. Tool tự động sinh mã đặt vé (`BK-XXXXXXXX`), tính phí dịch vụ 5%, và render hóa đơn. Nếu người dùng muốn file PDF, agent gọi thêm `generate_invoice_pdf()` — dùng thư viện `fpdf2` để tạo file PDF có header màu, bảng giá, footer chuyên nghiệp.

---

## II. Debugging Case Study (10 Points)

*Phân tích hai lỗi thực tế gặp phải trong quá trình xây dựng tool.*

---

### Bug 1: `UnicodeEncodeError` khi xuất PDF

- **Problem Description**: Khi gọi `generate_invoice_pdf()`, fpdf2 ném lỗi `FPDFUnicodeEncodingException` ngay tại bước `add_page()` (gọi `header()`). Cụ thể ký tự `—` (U+2014, em dash) và `→` (U+2192, arrow) trong chuỗi subtitle của header không encode được sang Latin-1, vốn là encoding duy nhất font Helvetica built-in hỗ trợ.

  ```
  UnicodeEncodeError: 'latin-1' codec can't encode character '\u2014'
  FPDFUnicodeEncodingException: Character "—" at index 22 is outside
  the range of characters supported by the font used: "helvetica".
  ```

- **Log Source**: Traceback từ terminal khi chạy `test_pdf.py`:
  ```
  File "invoice_tools.py", line 356, in header
      self.cell(0, 6, "Your e-ticket receipt — please keep this for your records")
  fpdf.errors.FPDFUnicodeEncodingException: Character "—" ...
  ```

- **Diagnosis**: Vấn đề nằm ở thiết kế font của fpdf2 — các core font (Helvetica, Times, Courier) chỉ hỗ trợ Latin-1 (ISO-8859-1), không hỗ trợ Unicode extended. Ký tự `—` và `→` là Unicode ngoài range này. Lỗi xảy ra ở cả header lẫn nội dung vì `_CLASS_LABELS` dict chứa chuỗi tiếng Việt (`"Phổ thông (Economy)"` có ký tự `ổ` = U+1ED5`).

- **Solution**:
  1. Thay toàn bộ ký tự Unicode đặc biệt trong PDF function bằng ASCII tương đương: `—` → `-`, `→` → `->`, `×` → `x`.
  2. Tạo dict riêng `_PDF_CLASS_LABELS` chỉ chứa English (Latin-1 safe) dùng riêng trong `generate_invoice_pdf`, tách biệt với `_CLASS_LABELS` (tiếng Việt) dùng cho text receipt.

---

### Bug 2: `mock data` trả về kết quả không lọc theo route

- **Problem Description**: Khi người dùng tìm CDG→SYD (Sydney, Úc), tool vẫn trả về 9 chuyến bay dù mock data chỉ chứa route CDG→AUS (Austin, Texas). Agent không báo lỗi, trả về kết quả sai lặng lẽ.

- **Diagnosis**: `data.json` là snapshot cố định của một lần gọi SerpAPI thực (CDG→AUS). Hàm `_load_flights_from_mock()` chỉ parse toàn bộ `best_flights` + `other_flights` mà không kiểm tra departure/arrival airport của mock data có khớp với tham số tìm kiếm không. Đây là trade-off khi dùng mock data — dữ liệu không thay đổi theo input.

- **Solution**: Đây là giới hạn thiết kế có chủ ý (mock data = demo, không phải production). Thêm ghi chú rõ trong message trả về: `"(Dữ liệu mock)"` để agent/người dùng biết kết quả là cố định. Nếu muốn filter thực sự, cần extend `data.json` với nhiều route hoặc switch sang real API.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: Trong bài lab này, block `Thought` của ReAct agent tỏ ra vượt trội so với Chatbot đơn thuần khi xử lý yêu cầu nhiều bước như tìm vé → so sánh → chốt mua → xuất hóa đơn. Chatbot trả lời ngay một lần dựa trên context có sẵn, trong khi ReAct agent *lập luận từng bước*: Thought → xác định cần gọi `search_flights` → nhận Observation → Thought → quyết định sort theo giá → Thought → gọi `generate_invoice`. Chuỗi lý luận này giúp agent phản ứng đúng với feedback của tool (ví dụ: nếu tool trả về 0 chuyến bay, agent tự điều chỉnh tham số thay vì bịa kết quả).

2. **Reliability**: ReAct agent thực sự tệ hơn Chatbot trong các tình huống:
   - **Câu hỏi đơn giản**: Hỏi "British Airways bay từ đâu?" → Chatbot trả lời ngay, Agent lại cố gọi tool rồi parse kết quả — chậm hơn và đôi khi lỗi tool spec.
   - **Latency**: Mỗi tool call là một round-trip; với mock data thì nhanh, nhưng với real API thì mỗi Thought-Action-Observation có thể mất vài giây, gây UX kém.
   - **Hallucination khi tool fail**: Nếu tool raise exception mà prompt không xử lý tốt, agent có thể fallback sang bịa dữ liệu thay vì thông báo lỗi.

3. **Observation**: Observation từ tool ảnh hưởng trực tiếp đến Thought tiếp theo. Ví dụ điển hình: khi `search_flights` trả về field `message` có chứa số lượng chuyến bay và thứ tự sắp xếp, agent đọc được và dùng làm context để diễn giải kết quả cho người dùng mà không cần hardcode. Ngược lại, khi Observation thiếu rõ ràng (ví dụ chỉ trả về raw JSON không có `message`), agent lúng túng và lặp lại tool call không cần thiết.

---

## IV. Future Improvements (5 Points)

- **Scalability**: Hiện tại `data.json` là file tĩnh dùng chung cho mọi query. Trong production, nên thay bằng **async tool calls** — mỗi lần gọi `search_flights` là một coroutine gọi SerpAPI/Amadeus API song song, cache kết quả vào Redis với TTL 5 phút để tránh gọi lại cùng route trong thời gian ngắn.

- **Safety**: Thêm một **Supervisor LLM** kiểm tra Thought của agent trước khi thực thi Action — đặc biệt quan trọng với `generate_invoice_pdf` vì tool này ghi file ra disk. Supervisor cần xác nhận: (1) thông tin hành khách có đủ không, (2) giá có bất thường không (ví dụ $0 hoặc $999999), (3) booking_link có phải Google Flights URL hợp lệ không.

- **Performance**: Khi số tool tăng lên (search_flights, book_hotel, rent_car, travel_insurance...), agent cần **Tool Retrieval** thay vì liệt kê toàn bộ trong system prompt. Dùng Vector DB (FAISS hoặc ChromaDB) để embed mô tả tool, mỗi Thought chỉ retrieve top-3 tool phù hợp nhất — giảm context window và tăng độ chính xác khi chọn tool.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
