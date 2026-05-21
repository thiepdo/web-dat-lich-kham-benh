import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'medicare.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS tai_khoan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ten_dang_nhap TEXT UNIQUE NOT NULL,
            mat_khau TEXT NOT NULL,
            vai_tro TEXT NOT NULL CHECK(vai_tro IN ('admin','bac_si','benh_nhan')),
            ho_ten TEXT NOT NULL,
            email TEXT,
            so_dien_thoai TEXT,
            trang_thai INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS chuyen_khoa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ten_chuyen_khoa TEXT NOT NULL,
            mo_ta TEXT
        );
        CREATE TABLE IF NOT EXISTS bac_si (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tai_khoan_id INTEGER UNIQUE,
            chuyen_khoa_id INTEGER,
            bang_cap TEXT,
            kinh_nghiem TEXT,
            mo_ta TEXT,
            phi_kham INTEGER DEFAULT 200000,
            FOREIGN KEY(tai_khoan_id) REFERENCES tai_khoan(id),
            FOREIGN KEY(chuyen_khoa_id) REFERENCES chuyen_khoa(id)
        );
        CREATE TABLE IF NOT EXISTS benh_nhan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tai_khoan_id INTEGER UNIQUE,
            ngay_sinh TEXT,
            gioi_tinh TEXT,
            dia_chi TEXT,
            FOREIGN KEY(tai_khoan_id) REFERENCES tai_khoan(id)
        );
        CREATE TABLE IF NOT EXISTS lich_kham (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benh_nhan_id INTEGER,
            bac_si_id INTEGER,
            ngay_kham TEXT NOT NULL,
            gio_kham TEXT NOT NULL,
            ly_do TEXT,
            trang_thai TEXT DEFAULT 'cho_xac_nhan'
                CHECK(trang_thai IN ('cho_xac_nhan','da_xac_nhan','hoan_thanh','da_huy')),
            phi_kham INTEGER DEFAULT 200000,
            ghi_chu TEXT,
            ly_do_huy TEXT,
            nguoi_huy TEXT,
            ngay_tao TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(benh_nhan_id) REFERENCES benh_nhan(id),
            FOREIGN KEY(bac_si_id) REFERENCES bac_si(id)
        );
        CREATE TABLE IF NOT EXISTS ho_so_benh_an (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lich_kham_id INTEGER UNIQUE,
            trieu_chung TEXT,
            chan_doan TEXT,
            huong_dieu_tri TEXT,
            don_thuoc TEXT,
            ghi_chu_them TEXT,
            ngay_tao TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(lich_kham_id) REFERENCES lich_kham(id)
        );
        CREATE TABLE IF NOT EXISTS hoa_don (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lich_kham_id INTEGER UNIQUE,
            so_tien INTEGER NOT NULL,
            trang_thai TEXT DEFAULT 'cho_thanh_toan'
                CHECK(trang_thai IN ('cho_thanh_toan','da_thanh_toan','da_huy')),
            phuong_thuc_thanh_toan TEXT DEFAULT 'tien_mat',
            ghi_chu TEXT,
            ngay_tao TEXT DEFAULT CURRENT_TIMESTAMP,
            ngay_thanh_toan TEXT,
            bac_si_xac_nhan_id INTEGER,
            FOREIGN KEY(lich_kham_id) REFERENCES lich_kham(id),
            FOREIGN KEY(bac_si_xac_nhan_id) REFERENCES bac_si(id)
        );
    ''')
    # Migration: thêm cột mới nếu chưa có (cho DB cũ)
    for migration in [
        "ALTER TABLE lich_kham ADD COLUMN ly_do_huy TEXT",
        "ALTER TABLE lich_kham ADD COLUMN nguoi_huy TEXT",
    ]:
        try:
            c.execute(migration)
        except Exception:
            pass
    # Seed dữ liệu mặc định
    admin_pw = generate_password_hash('admin123')
    c.execute("INSERT OR IGNORE INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email) VALUES (?,?,?,?,?)",
              ('admin', admin_pw, 'admin', 'Quản trị viên', 'admin@medicare.vn'))
    specialties = [('Nội khoa','Khám nội khoa'),('Nhi khoa','Khám nhi'),
                   ('Tim mạch','Khám tim mạch'),('Da liễu','Khám da liễu'),('Mắt','Khám mắt')]
    for sp in specialties:
        if not c.execute("SELECT id FROM chuyen_khoa WHERE ten_chuyen_khoa=?", (sp[0],)).fetchone():
            c.execute("INSERT INTO chuyen_khoa (ten_chuyen_khoa, mo_ta) VALUES (?,?)", sp)
    c.execute("DELETE FROM chuyen_khoa WHERE id NOT IN (SELECT MIN(id) FROM chuyen_khoa GROUP BY ten_chuyen_khoa)")
    doctors = [
        ('bs_nguyen','doctor123','BS. Nguyễn Văn An','nguyenan@medicare.vn','0901111111',1),
        ('bs_le','doctor123','BS. Lê Hoàng Cường','lecuong@medicare.vn','0902222222',2),
        ('bs_tran','doctor123','BS. Trần Thị Bình','tranbinh@medicare.vn','0903333333',3),
    ]
    for d in doctors:
        pw = generate_password_hash(d[1])
        c.execute("INSERT OR IGNORE INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email, so_dien_thoai) VALUES (?,?,?,?,?,?)",
                  (d[0], pw, 'bac_si', d[2], d[3], d[4]))
        row = c.execute("SELECT id FROM tai_khoan WHERE ten_dang_nhap=?", (d[0],)).fetchone()
        if row:
            c.execute("INSERT OR IGNORE INTO bac_si (tai_khoan_id, chuyen_khoa_id, bang_cap, kinh_nghiem, phi_kham) VALUES (?,?,?,?,?)",
                      (row[0], d[5], 'Tiến sĩ Y khoa', '10 năm kinh nghiệm', 200000))
    p_pw = generate_password_hash('patient123')
    c.execute("INSERT OR IGNORE INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email, so_dien_thoai) VALUES (?,?,?,?,?,?)",
              ('patient1', p_pw, 'benh_nhan', 'Phạm Minh Đức', 'pham.duc@email.com', '0911111111'))
    pr = c.execute("SELECT id FROM tai_khoan WHERE ten_dang_nhap='patient1'").fetchone()
    if pr:
        c.execute("INSERT OR IGNORE INTO benh_nhan (tai_khoan_id, ngay_sinh, gioi_tinh, dia_chi) VALUES (?,?,?,?)",
                  (pr[0], '1990-05-15', 'Nam', 'Hà Nội'))
    conn.commit()
    conn.close()
