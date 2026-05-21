# 🏥 MediCare App

Ứng dụng đặt lịch khám bệnh trực tuyến, xây dựng bằng Flask + SQLite.

---

## 📁 Cấu trúc dự án

```
medicare_clean/
├── README.md
├── backend/
│   ├── app.py                     ← Entry point: khởi động Flask, đăng ký Blueprints + Swagger
│   ├── requirements.txt           ← Danh sách thư viện cần cài
│   ├── models/
│   │   └── database.py            ← Kết nối DB, tạo bảng, seed dữ liệu mẫu
│   ├── middleware/
│   │   └── auth.py                ← Bảo vệ route: login_required, require_api_key, CORS
│   └── routes/
│       ├── web_public.py          ← Trang công khai: /, /login, /register, /logout
│       ├── web_patient.py         ← Bệnh nhân: /patient/dashboard, /book, /cancel, /invoice
│       ├── web_doctor.py          ← Bác sĩ: /doctor/dashboard, /confirm, /medical-record, /invoice
│       ├── web_admin.py           ← Quản trị: /admin/dashboard, /doctors, /patients, /specialties
│       ├── api_internal.py        ← API nội bộ (không cần key): /api/booked-slots, /api/doctors-by-specialty
│       └── api_v1.py              ← API công khai (cần X-API-Key): /api/v1/*
│
└── frontend/
    ├── static/
    │   ├── css/                   ← File CSS tùy chỉnh
    │   └── js/                    ← File JavaScript tùy chỉnh
    └── templates/
        ├── shared/                ← Dùng chung: base.html, index.html, invoice.html
        ├── auth/                  ← Đăng nhập/đăng ký: login.html, register.html
        ├── patient/               ← Giao diện bệnh nhân: dashboard.html, book_appointment.html
        ├── doctor/                ← Giao diện bác sĩ: dashboard.html, medical_record.html
        └── admin/                 ← Giao diện quản trị: dashboard.html, doctors.html, ...
```

---

## 🚀 Hướng dẫn cài đặt và chạy

### Yêu cầu
- Python 3.8 trở lên
- pip

### Bước 1 — Cài thư viện

```bash
cd backend
pip install -r requirements.txt
```

### Bước 2 — Chạy server

```bash
python app.py
```

Server sẽ chạy tại: **http://localhost:5000**

> Lần đầu chạy, database `medicare.db` sẽ được tạo tự động kèm dữ liệu mẫu.

---

## 🌐 Các đường dẫn chính

| Đường dẫn | Mô tả |
|---|---|
| `http://localhost:5000/` | Trang chủ |
| `http://localhost:5000/login` | Đăng nhập |
| `http://localhost:5000/register` | Đăng ký tài khoản bệnh nhân |
| `http://localhost:5000/patient/dashboard` | Dashboard bệnh nhân |
| `http://localhost:5000/doctor/dashboard` | Dashboard bác sĩ |
| `http://localhost:5000/admin/dashboard` | Dashboard quản trị |
| `http://localhost:5000/api/docs` | **Swagger UI — xem và test API** |

---

## 🔑 Tài khoản mặc định

| Vai trò | Username | Password |
|---|---|---|
| Quản trị viên | `admin` | `admin123` |
| Bác sĩ | `bs_nguyen` | `doctor123` |
| Bác sĩ | `bs_le` | `doctor123` |
| Bác sĩ | `bs_tran` | `doctor123` |
| Bệnh nhân | `patient1` | `patient123` |

---

## 📡 Hướng dẫn sử dụng API

### Mở Swagger UI

Truy cập **http://localhost:5000/api/docs** để xem toàn bộ tài liệu API và test trực tiếp trên trình duyệt.

### Xác thực API Key

Tất cả endpoint `/api/v1/*` đều yêu cầu API Key. Có 2 cách truyền:

**Cách 1 — Header (khuyến nghị):**
```
X-API-Key: medicare-api-key-2024
```

**Cách 2 — Query string:**
```
GET /api/v1/doctors?api_key=medicare-api-key-2024
```

**Trên Swagger UI:**
1. Nhấn nút **Authorize** (🔒) góc trên phải
2. Nhập `medicare-api-key-2024` vào ô Value
3. Nhấn **Authorize** → **Close**
4. Tất cả request sẽ tự động kèm API Key

### Các endpoint chính

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/v1/info` | Thông tin phiên bản API |
| GET | `/api/v1/specialties` | Danh sách chuyên khoa |
| GET | `/api/v1/doctors` | Danh sách bác sĩ (lọc theo `?chuyen_khoa_id=`) |
| GET | `/api/v1/doctors/<id>` | Chi tiết một bác sĩ |
| GET | `/api/v1/booked-slots` | Giờ đã đặt (`?bac_si_id=&ngay_kham=`) |
| GET | `/api/v1/appointments` | Danh sách lịch khám (có thể lọc) |
| POST | `/api/v1/appointments` | Đặt lịch khám mới |
| GET | `/api/v1/appointments/<id>` | Chi tiết một lịch khám |
| PUT | `/api/v1/appointments/<id>/status` | Cập nhật trạng thái lịch khám |
| GET | `/api/v1/patients` | Danh sách bệnh nhân |
| GET | `/api/v1/patients/<id>` | Chi tiết bệnh nhân + lịch sử khám |

### Ví dụ gọi API bằng curl

```bash
# Lấy danh sách chuyên khoa
curl -H "X-API-Key: medicare-api-key-2024" http://localhost:5000/api/v1/specialties

# Lấy bác sĩ theo chuyên khoa
curl -H "X-API-Key: medicare-api-key-2024" http://localhost:5000/api/v1/doctors?chuyen_khoa_id=1

# Đặt lịch khám mới
curl -X POST http://localhost:5000/api/v1/appointments \
  -H "X-API-Key: medicare-api-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"benh_nhan_id": 1, "bac_si_id": 1, "ngay_kham": "2026-05-01", "gio_kham": "09:00", "ly_do": "Khám tổng quát"}'

# Cập nhật trạng thái lịch khám
curl -X PUT http://localhost:5000/api/v1/appointments/1/status \
  -H "X-API-Key: medicare-api-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"trang_thai": "da_xac_nhan", "ghi_chu": "Đã xác nhận lịch"}'
```

### Trạng thái lịch khám

| Giá trị | Ý nghĩa |
|---|---|
| `cho_xac_nhan` | Chờ bác sĩ xác nhận |
| `da_xac_nhan` | Đã xác nhận |
| `hoan_thanh` | Đã khám xong |
| `da_huy` | Đã hủy |

---

## ⚙️ Cấu hình môi trường

Có thể đặt các biến môi trường trước khi chạy:

```bash
# Thay đổi API Key (bắt buộc khi deploy thật)
export MEDICARE_API_KEY=your-strong-secret-key

# Thay đổi secret key cho session Flask
export SECRET_KEY=your-flask-secret-key

python app.py
```

---

## 🗄️ Database

File database SQLite được tạo tự động tại `backend/../medicare.db` khi chạy lần đầu. Không cần cài thêm bất kỳ database engine nào.

**Các bảng chính:**

| Bảng | Mô tả |
|---|---|
| `tai_khoan` | Tài khoản người dùng (admin, bác sĩ, bệnh nhân) |
| `bac_si` | Thông tin bác sĩ |
| `benh_nhan` | Thông tin bệnh nhân |
| `chuyen_khoa` | Danh mục chuyên khoa |
| `lich_kham` | Lịch đặt khám |
| `ho_so_benh_an` | Hồ sơ bệnh án |
| `hoa_don` | Hóa đơn thanh toán |
