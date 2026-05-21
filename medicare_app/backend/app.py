from flask import Flask
from flasgger import Swagger
import os

from models.database import init_db
from middleware.auth import add_cors_headers

# ── Các nhóm route (blueprint) ─────────────────────────────────
from routes.web_public  import web_public_bp   # Trang công khai: đăng nhập, đăng ký
from routes.web_patient import web_patient_bp  # Giao diện bệnh nhân
from routes.web_doctor  import web_doctor_bp   # Giao diện bác sĩ
from routes.web_admin   import web_admin_bp    # Giao diện quản trị viên
from routes.api_internal import api_internal_bp # API nội bộ (dùng trong web)
from routes.api_v1      import api_v1_bp       # API công khai v1 (Swagger)

# ── Khởi tạo Flask ─────────────────────────────────────────────
app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.secret_key = os.environ.get('SECRET_KEY', 'medicare_secret_key_2024')

app.after_request(add_cors_headers)  # Thêm CORS header cho mọi response

# ── Đăng ký blueprint với URL prefix ───────────────────────────
# URL đầy đủ = prefix + route trong từng blueprint
app.register_blueprint(web_public_bp)                          # /
app.register_blueprint(web_patient_bp, url_prefix='/patient')  # /patient/...
app.register_blueprint(web_doctor_bp,  url_prefix='/doctor')   # /doctor/...
app.register_blueprint(web_admin_bp,   url_prefix='/admin')    # /admin/...
app.register_blueprint(api_internal_bp, url_prefix='/api')     # /api/...
app.register_blueprint(api_v1_bp,       url_prefix='/api/v1')  # /api/v1/...

# ── Swagger UI: tài liệu API tại /api/docs ─────────────────────
swagger_config = {
    "headers": [],
    "specs": [{"endpoint": "apispec", "route": "/apispec.json",
               "rule_filter": lambda rule: rule.rule.startswith("/api/v1"),
               "model_filter": lambda tag: True}],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs",
}
swagger_template = {
    "info": {"title": "MediCare API",
             "description": "API đặt lịch khám bệnh.\n\nNhấn **Authorize** và nhập API Key vào ô **Value** để dùng được tất cả endpoint.",
             "version": "1.0.0"},
    "securityDefinitions": {"ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
    "security": [{"ApiKeyAuth": []}],
}
Swagger(app, config=swagger_config, template=swagger_template)

# ── Chạy ứng dụng ──────────────────────────────────────────────
if __name__ == '__main__':
    init_db()   # Tạo bảng DB + seed dữ liệu mặc định (admin, chuyên khoa...)
    app.run(debug=True, port=5000)
