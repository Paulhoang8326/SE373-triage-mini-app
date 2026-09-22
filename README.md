# MÔN KỸ THUẬT XÂY DỰNG HỆ THỐNG AGENTIC AI

## BÀI TẬP VỀ NHÀ 2

### Xây dựng Issue Triage mini-app

Ứng dụng minh họa quy trình tiếp nhận và phân loại issue phần mềm bằng LLM. Hệ thống nhận mô tả sự cố, đánh giá mức độ ưu tiên, xác định component liên quan, sử dụng function calling để tra cứu team phụ trách và trả về kết quả có cấu trúc đã được kiểm tra bằng Pydantic.

## Mục tiêu bài tập

- Gọi một LLM thông qua OpenAI-compatible API.
- Quan sát sự khác biệt về token giữa nội dung tiếng Anh và tiếng Việt.
- So sánh JSON tạo bằng prompt với structured output theo schema.
- Sử dụng function calling theo mô hình: model đề xuất, application kiểm tra và thực thi.
- Tách system instruction khỏi dữ liệu issue do người dùng nhập.
- Kiểm tra kết quả của model bằng Pydantic và các quy tắc của application.
- Xây dựng giao diện tương tác bằng Streamlit.
###
### Đáp ứng yêu cầu đề bài
| Yêu cầu | Cách triển khai | File liên quan |
|---|---|---|
| Nhận mô tả issue phần mềm | Nhận input qua CLI hoặc giao diện Streamlit | `00_minimal_triage.py`, `04_streamlit_triage.py` |
| Tách instruction và input | Dùng riêng `SYSTEM_PROMPT` và `USER_ISSUE_TEMPLATE` | `triage_workflow.py` |
| Trả về `IssueTriage` | Khai báo schema bằng Pydantic | `triage_workflow.py`, `02_structured_output.py` |
| Validate output tại application | Pydantic kiểm tra schema; application đối chiếu component và owner | `validate_triage_output()` trong `triage_workflow.py` |
| Khai báo một tool đơn giản | Tool `get_component_owner` tra cứu team phụ trách | `triage_workflow.py` |
| In đầy đủ trace | Hiển thị `tool_call → application executes → tool_result → final response` | `03_function_calling.py`, `04_streamlit_triage.py` |

## Chức năng chính

Ứng dụng nhận một mô tả issue và trả về `IssueTriage` gồm:

- `status`: `classified`, `insufficient_data` hoặc `out_of_scope`.
- `severity`: `P0`, `P1`, `P2` hoặc `P3`.
- `component`: `payment`, `identity` hoặc `search`.
- `owner`: team chịu trách nhiệm cho component.
- `needs_urgent_response`: issue có cần phản hồi khẩn cấp hay không.
- `reason`: lý do phân loại ngắn gọn bằng tiếng Việt.

Function `get_component_owner` chỉ được application thực thi sau khi kiểm tra tên tool và tham số. Model không được tự tạo team phụ trách. Luồng xử lý được hiển thị theo thứ tự:

```text
tool_call -> application validates and executes -> tool_result -> final response
```

## Công nghệ sử dụng

- Python 3.11 trở lên
- OpenAI Python SDK
- OpenAI-compatible API
- Pydantic
- Streamlit
- tiktoken
- python-dotenv

## Cấu trúc project

```text
.
├── 00_minimal_triage.py      # Gọi LLM và nhận kết quả dạng văn bản
├── 01_measure_tokens.py      # So sánh token tiếng Anh và tiếng Việt
├── 02_structured_output.py   # So sánh prompt-only JSON và structured output
├── 03_function_calling.py    # Demo function calling trên CLI
├── 04_streamlit_triage.py    # Giao diện Issue Triage bằng Streamlit
├── demo_common.py            # Đọc cấu hình và khởi tạo API client
├── triage_workflow.py        # Schema, tool và quy trình triage chính
├── test_triage_workflow.py   # Kiểm thử offline
├── demo-guide.html           # Hướng dẫn chạy demo chi tiết
├── requirements.txt          # Danh sách thư viện Python
└── .env.example              # Mẫu cấu hình, không chứa API key thật
```

## Cài đặt trên Windows

Mở PowerShell tại thư mục project và chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở `.env` và cập nhật thông tin của provider:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_MODEL=gemini-2.5-flash
```

Model được cấu hình phải hỗ trợ structured output và function calling theo chuẩn OpenAI-compatible API.

## Chạy các demo

### Demo 00 — LLM call tối thiểu

```powershell
python .\00_minimal_triage.py
```

Có thể truyền issue khác bằng tham số `--issue`:

```powershell
python .\00_minimal_triage.py --issue "API đăng nhập trả HTTP 503 cho toàn bộ người dùng từ 09:15."
```

### Demo 01 — Đo token

```powershell
python .\01_measure_tokens.py
```

Demo này chạy offline và không gọi API.

### Demo 02 — Structured output

```powershell
python .\02_structured_output.py
```

Script in kết quả JSON được yêu cầu bằng prompt và kết quả structured output đã được parse theo schema.

### Demo 03 — Function calling

```powershell
python .\03_function_calling.py
```

Kết quả gồm tool call của model, bước application kiểm tra và thực thi, tool result và `IssueTriage` cuối cùng.

### Demo 04 — Streamlit UI

```powershell
python -m streamlit run .\04_streamlit_triage.py --server.headless true
```

Mở Local URL do Streamlit hiển thị, nhập mô tả issue và chọn **Phân loại issue**.

## Chạy kiểm thử

```powershell
python -m unittest -v
```

Các kiểm thử xác minh:

- System instruction và input người dùng được tách riêng.
- Tool chỉ chấp nhận các component được application cho phép.
- Schema yêu cầu severity đối với issue đã phân loại.
- Application từ chối owner không khớp với kết quả tool.

## Hướng dẫn chi tiết

Mở file [`demo-guide.html`](demo-guide.html) bằng trình duyệt để xem hướng dẫn chạy tuần tự Demo 00–04 và cách xử lý các lỗi thường gặp.
