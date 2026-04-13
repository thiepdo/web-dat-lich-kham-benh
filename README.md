# 🏥 MediCare — Hệ thống Đặt Lịch Khám Bệnh

Ứng dụng web quản lý lịch khám bệnh, hỗ trợ 3 vai trò: **Bệnh nhân**, **Bác sĩ**, **Admin**.
Tích hợp **REST API** với tài liệu Swagger UI tương tác.

---

## 🚀 Cài đặt & Chạy

### 1. Cài thư viện

```bash
pip install -r requirements.txt
```

### 2. Chạy ứng dụng

```bash
python app.py
```

Mặc định chạy tại: **http://localhost:5000**

---

## 👤 Tài khoản mặc định

| Vai trò   | Tên đăng nhập | Mật khẩu    |
|-----------|---------------|-------------|
| Admin     | admin         | admin123    |
| Bác sĩ    | bs_nguyen     | doctor123   |
| Bác sĩ    | bs_le         | doctor123   |
| Bác sĩ    | bs_tran       | doctor123   |
| Bệnh nhân | patient1      | patient123  |

---

## 📡 API & Swagger UI

### Mở Swagger UI

Sau khi chạy app, truy cập:

```
http://localhost:5000/api/docs
```

Giao diện Swagger cho phép xem toàn bộ API và test trực tiếp trên trình duyệt — không cần Postman hay curl.

---

### 🔑 API Key

Mọi request API đều cần xác thực bằng API Key.

**API Key mặc định:**
```
medicare-api-key-2024
```

**Cách đổi API Key (khuyến nghị trước khi deploy):**
```bash
export MEDICARE_API_KEY="key-bi-mat-cua-ban"
python app.py
```

---

### Cách nhập API Key trong Swagger UI

1. Mở http://localhost:5000/api/docs
2. Nhấn nút **Authorize** (góc trên bên phải, có hình ổ khóa)
3. Nhập API Key vào ô **Value**: `medicare-api-key-2024`
4. Nhấn **Authorize** rồi **Close**
5. Tất cả request từ đây sẽ tự động gửi kèm API Key

Sau khi Authorize, nhấn **Try it out** ở bất kỳ endpoint nào để test.

---

### Danh sách API Endpoint

| Method | Endpoint                  | Mô tả                                        |
|--------|---------------------------|----------------------------------------------|
| GET    | /api/v1/info              | Thông tin phiên bản API                      |
| GET    | /api/v1/specialties       | Danh sách chuyên khoa                        |
| GET    | /api/v1/doctors           | Danh sách bác sĩ (lọc theo ?chuyen_khoa_id=)|
| GET    | /api/v1/doctors/{id}      | Chi tiết một bác sĩ                          |
| GET    | /api/v1/booked_slots      | Giờ đã đặt (?bac_si_id= & ngay_kham=)       |
| POST   | /api/v1/appointments      | Đặt lịch khám mới                            |

---

### Ví dụ gọi API bằng curl

```bash
# Danh sách chuyên khoa
curl http://localhost:5000/api/v1/specialties \
  -H "X-API-Key: medicare-api-key-2024"

# Bác sĩ theo chuyên khoa
curl "http://localhost:5000/api/v1/doctors?chuyen_khoa_id=1" \
  -H "X-API-Key: medicare-api-key-2024"

# Giờ đã đặt
curl "http://localhost:5000/api/v1/booked_slots?bac_si_id=1&ngay_kham=2026-04-15" \
  -H "X-API-Key: medicare-api-key-2024"

# Đặt lịch
curl -X POST http://localhost:5000/api/v1/appointments \
  -H "X-API-Key: medicare-api-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"benh_nhan_id":1,"bac_si_id":1,"ngay_kham":"2026-04-15","gio_kham":"09:00","ly_do":"Kham tong quat"}'
```

---

## 🗂️ Cấu trúc thư mục

```
medicare_app_new/
├── app.py              # Flask app chính + toàn bộ routes & API
├── requirements.txt    # Thư viện cần cài (flask, flasgger)
├── README.md           # File này
├── medicare.db         # SQLite database (tự tạo khi chạy lần đầu)
├── templates/          # Giao diện HTML
└── static/             # CSS, JS tĩnh
```

---

## 🛡️ Bảo mật khi deploy

- Đổi `app.secret_key` trong app.py thành chuỗi ngẫu nhiên dài
- Đặt `MEDICARE_API_KEY` qua biến môi trường, không để key mặc định
- Tắt `debug=True` trong app.run()
- Dùng HTTPS (nginx + certbot) khi deploy lên server thật
