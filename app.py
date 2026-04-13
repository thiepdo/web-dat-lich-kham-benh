from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import os
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'medicare_secret_key_2024'

# ==================== API KEY CONFIG ====================
# Đổi key này hoặc set biến môi trường MEDICARE_API_KEY trước khi deploy
API_KEY = os.environ.get('MEDICARE_API_KEY', 'medicare-api-key-2024')

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if key != API_KEY:
            return jsonify({'error': 'Unauthorized. Thieu hoac sai API Key.'}), 401
        return f(*args, **kwargs)
    return decorated

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

DB_PATH = os.path.join(os.path.dirname(__file__), 'medicare.db')

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
            trang_thai TEXT DEFAULT 'cho_xac_nhan' CHECK(trang_thai IN ('cho_xac_nhan','da_xac_nhan','hoan_thanh','da_huy')),
            phi_kham INTEGER DEFAULT 200000,
            ghi_chu TEXT,
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
            trang_thai TEXT DEFAULT 'cho_thanh_toan' CHECK(trang_thai IN ('cho_thanh_toan','da_thanh_toan','da_huy')),
            phuong_thuc_thanh_toan TEXT DEFAULT 'tien_mat',
            ghi_chu TEXT,
            ngay_tao TEXT DEFAULT CURRENT_TIMESTAMP,
            ngay_thanh_toan TEXT,
            bac_si_xac_nhan_id INTEGER,
            FOREIGN KEY(lich_kham_id) REFERENCES lich_kham(id),
            FOREIGN KEY(bac_si_xac_nhan_id) REFERENCES bac_si(id)
        );
    ''')
    admin_pw = generate_password_hash('admin123')
    c.execute("INSERT OR IGNORE INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email) VALUES (?,?,?,?,?)",
              ('admin', admin_pw, 'admin', 'Quản trị viên', 'admin@medicare.vn'))
    specialties = [('Nội khoa','Khám nội khoa'),('Nhi khoa','Khám nhi'),('Tim mạch','Khám tim mạch'),('Da liễu','Khám da liễu'),('Mắt','Khám mắt')]
    for sp in specialties:
        exists = c.execute("SELECT id FROM chuyen_khoa WHERE ten_chuyen_khoa=?", (sp[0],)).fetchone()
        if not exists:
            c.execute("INSERT INTO chuyen_khoa (ten_chuyen_khoa, mo_ta) VALUES (?,?)", sp)
    # Xóa chuyên khoa bị trùng, giữ id nhỏ nhất
    c.execute("DELETE FROM chuyen_khoa WHERE id NOT IN (SELECT MIN(id) FROM chuyen_khoa GROUP BY ten_chuyen_khoa)")
    doctors = [('bs_nguyen','doctor123','BS. Nguyễn Văn An','nguyenan@medicare.vn','0901111111',1),('bs_le','doctor123','BS. Lê Hoàng Cường','lecuong@medicare.vn','0902222222',2),('bs_tran','doctor123','BS. Trần Thị Bình','tranbinh@medicare.vn','0903333333',3)]
    for d in doctors:
        pw = generate_password_hash(d[1])
        c.execute("INSERT OR IGNORE INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email, so_dien_thoai) VALUES (?,?,?,?,?,?)", (d[0],pw,'bac_si',d[2],d[3],d[4]))
        row = c.execute("SELECT id FROM tai_khoan WHERE ten_dang_nhap=?", (d[0],)).fetchone()
        if row:
            c.execute("INSERT OR IGNORE INTO bac_si (tai_khoan_id, chuyen_khoa_id, bang_cap, kinh_nghiem, phi_kham) VALUES (?,?,?,?,?)", (row[0],d[5],'Tiến sĩ Y khoa','10 năm kinh nghiệm',200000))
    p_pw = generate_password_hash('patient123')
    c.execute("INSERT OR IGNORE INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email, so_dien_thoai) VALUES (?,?,?,?,?,?)", ('patient1',p_pw,'benh_nhan','Phạm Minh Đức','pham.duc@email.com','0911111111'))
    pr = c.execute("SELECT id FROM tai_khoan WHERE ten_dang_nhap='patient1'").fetchone()
    if pr:
        c.execute("INSERT OR IGNORE INTO benh_nhan (tai_khoan_id, ngay_sinh, gioi_tinh, dia_chi) VALUES (?,?,?,?)", (pr[0],'1990-05-15','Nam','Hà Nội'))
    conn.commit()
    conn.close()

# ==================== TRANG WEB ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM tai_khoan WHERE ten_dang_nhap=? AND trang_thai=1", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['mat_khau'], password):
            session['user_id'] = user['id']
            session['username'] = user['ten_dang_nhap']
            session['vai_tro'] = user['vai_tro']
            session['ho_ten'] = user['ho_ten']
            if user['vai_tro'] == 'admin': return redirect(url_for('admin_dashboard'))
            elif user['vai_tro'] == 'bac_si': return redirect(url_for('doctor_dashboard'))
            else: return redirect(url_for('patient_dashboard'))
        flash('Tên đăng nhập hoặc mật khẩu không đúng!', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        conn = get_db()
        existing = conn.execute("SELECT id FROM tai_khoan WHERE ten_dang_nhap=?", (data['username'],)).fetchone()
        if existing:
            conn.close()
            flash('Tên đăng nhập đã tồn tại!', 'error')
            return render_template('register.html')
        pw = generate_password_hash(data['password'])
        c = conn.cursor()
        c.execute("INSERT INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email, so_dien_thoai) VALUES (?,?,?,?,?,?)",
                  (data['username'], pw, 'benh_nhan', data['ho_ten'], data['email'], data['so_dien_thoai']))
        tk_id = c.lastrowid
        c.execute("INSERT INTO benh_nhan (tai_khoan_id, ngay_sinh, gioi_tinh, dia_chi) VALUES (?,?,?,?)",
                  (tk_id, data.get('ngay_sinh', ''), data.get('gioi_tinh', ''), data.get('dia_chi', '')))
        conn.commit(); conn.close()
        flash('Đăng ký thành công!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session: return redirect(url_for('login'))
            if role and session.get('vai_tro') != role:
                flash('Bạn không có quyền truy cập!', 'error')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ==================== PATIENT ====================

@app.route('/patient/dashboard')
@login_required('benh_nhan')
def patient_dashboard():
    conn = get_db()
    bn = conn.execute("SELECT * FROM benh_nhan WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    today = date.today().isoformat()
    appointments = conn.execute("""
        SELECT lk.*, tk.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM lich_kham lk
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.benh_nhan_id=? ORDER BY lk.ngay_kham DESC, lk.gio_kham DESC
    """, (bn['id'],)).fetchall()
    invoices = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, tk.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id=lk.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.benh_nhan_id=? ORDER BY hd.ngay_tao DESC
    """, (bn['id'],)).fetchall()
    medical_records = conn.execute("""
        SELECT hsba.*, lk.ngay_kham, lk.gio_kham, lk.ly_do, tk.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM ho_so_benh_an hsba
        JOIN lich_kham lk ON hsba.lich_kham_id=lk.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.benh_nhan_id=? ORDER BY hsba.ngay_tao DESC
    """, (bn['id'],)).fetchall()
    upcoming = [a for a in appointments if a['ngay_kham'] >= today and a['trang_thai'] not in ('da_huy', 'hoan_thanh')]
    completed = [a for a in appointments if a['trang_thai'] == 'hoan_thanh']
    cancelled = [a for a in appointments if a['trang_thai'] == 'da_huy']
    conn.close()
    return render_template('patient_dashboard.html', appointments=appointments, upcoming=upcoming,
                           completed=completed, cancelled=cancelled, invoices=invoices,
                           medical_records=medical_records, today=today)

@app.route('/patient/book', methods=['GET', 'POST'])
@login_required('benh_nhan')
def book_appointment():
    conn = get_db()
    if request.method == 'POST':
        bn = conn.execute("SELECT * FROM benh_nhan WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
        bac_si_id = request.form['bac_si_id']
        ngay_kham = request.form['ngay_kham']
        gio_kham = request.form['gio_kham']
        ly_do = request.form.get('ly_do', '')
        conflict = conn.execute("SELECT id FROM lich_kham WHERE bac_si_id=? AND ngay_kham=? AND gio_kham=? AND trang_thai NOT IN ('da_huy')", (bac_si_id, ngay_kham, gio_kham)).fetchone()
        if conflict:
            flash('Khung giờ này đã được đặt!', 'error')
        else:
            bs = conn.execute("SELECT phi_kham FROM bac_si WHERE id=?", (bac_si_id,)).fetchone()
            phi = bs['phi_kham'] if bs else 200000
            conn.execute("INSERT INTO lich_kham (benh_nhan_id, bac_si_id, ngay_kham, gio_kham, ly_do, phi_kham) VALUES (?,?,?,?,?,?)", (bn['id'], bac_si_id, ngay_kham, gio_kham, ly_do, phi))
            conn.commit(); conn.close()
            flash('Đặt lịch khám thành công!', 'success')
            return redirect(url_for('patient_dashboard'))
    specialties = conn.execute("SELECT * FROM chuyen_khoa GROUP BY ten_chuyen_khoa ORDER BY ten_chuyen_khoa").fetchall()
    doctors = conn.execute("SELECT bs.*, tk.ho_ten, ck.ten_chuyen_khoa FROM bac_si bs JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id WHERE tk.trang_thai=1 ORDER BY tk.ho_ten").fetchall()
    conn.close()
    return render_template('book_appointment.html', specialties=specialties, doctors=doctors)

@app.route('/patient/cancel/<int:lk_id>', methods=['POST'])
@login_required('benh_nhan')
def cancel_appointment(lk_id):
    conn = get_db()
    bn = conn.execute("SELECT * FROM benh_nhan WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    lk = conn.execute("SELECT * FROM lich_kham WHERE id=? AND benh_nhan_id=?", (lk_id, bn['id'])).fetchone()
    if lk and lk['trang_thai'] in ('cho_xac_nhan', 'da_xac_nhan'):
        conn.execute("UPDATE lich_kham SET trang_thai='da_huy' WHERE id=?", (lk_id,))
        conn.commit()
        flash('Đã hủy lịch khám!', 'success')
    conn.close()
    return redirect(url_for('patient_dashboard'))

@app.route('/patient/invoice/<int:hd_id>')
@login_required('benh_nhan')
def patient_invoice(hd_id):
    conn = get_db()
    bn = conn.execute("SELECT * FROM benh_nhan WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    hd = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, lk.ly_do, lk.phi_kham,
               tk.ho_ten as ten_bs, ck.ten_chuyen_khoa, tkbn.ho_ten as ten_bn,
               tkkn.ho_ten as ten_bs_xn
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id = lk.id
        JOIN bac_si bs ON lk.bac_si_id = bs.id
        JOIN tai_khoan tk ON bs.tai_khoan_id = tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id = ck.id
        JOIN benh_nhan b ON lk.benh_nhan_id = b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id = tkbn.id
        LEFT JOIN bac_si bsxn ON hd.bac_si_xac_nhan_id = bsxn.id
        LEFT JOIN tai_khoan tkkn ON bsxn.tai_khoan_id = tkkn.id
        WHERE hd.id=? AND lk.benh_nhan_id=?
    """, (hd_id, bn['id'])).fetchone()
    conn.close()
    if not hd:
        flash('Không tìm thấy hóa đơn!', 'error')
        return redirect(url_for('patient_dashboard'))
    return render_template('invoice.html', hd=hd, role='benh_nhan')

# ==================== DOCTOR ====================

@app.route('/doctor/dashboard')
@login_required('bac_si')
def doctor_dashboard():
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    if not bs: conn.close(); return redirect(url_for('logout'))
    today = date.today().isoformat()
    appointments = conn.execute("""
        SELECT lk.*, tkbn.ho_ten as ten_bn, tkbn.email, tkbn.so_dien_thoai
        FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id = b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id = tkbn.id
        WHERE lk.bac_si_id=? ORDER BY lk.ngay_kham DESC, lk.gio_kham DESC
    """, (bs['id'],)).fetchall()
    today_count = sum(1 for a in appointments if a['ngay_kham'] == today and a['trang_thai'] not in ('da_huy',))
    pending = [a for a in appointments if a['trang_thai'] == 'cho_xac_nhan']
    upcoming = [a for a in appointments if a['ngay_kham'] > today and a['trang_thai'] == 'da_xac_nhan']
    invoices_pending = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, tkbn.ho_ten as ten_bn
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id = lk.id
        JOIN benh_nhan b ON lk.benh_nhan_id = b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id = tkbn.id
        WHERE lk.bac_si_id=? AND hd.trang_thai='cho_thanh_toan' ORDER BY hd.ngay_tao DESC
    """, (bs['id'],)).fetchall()
    all_invoices = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, tkbn.ho_ten as ten_bn
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id = lk.id
        JOIN benh_nhan b ON lk.benh_nhan_id = b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id = tkbn.id
        WHERE lk.bac_si_id=? ORDER BY hd.ngay_tao DESC
    """, (bs['id'],)).fetchall()
    benh_ans = conn.execute("""
        SELECT hsba.*, lk.ngay_kham, lk.gio_kham, lk.ly_do, tkbn.ho_ten as ten_bn
        FROM ho_so_benh_an hsba
        JOIN lich_kham lk ON hsba.lich_kham_id = lk.id
        JOIN benh_nhan b ON lk.benh_nhan_id = b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id = tkbn.id
        WHERE lk.bac_si_id=? ORDER BY hsba.ngay_tao DESC
    """, (bs['id'],)).fetchall()
    conn.close()
    return render_template('doctor_dashboard.html', bs=bs, appointments=appointments,
                           today_count=today_count, pending=pending, upcoming=upcoming,
                           invoices_pending=invoices_pending, all_invoices=all_invoices,
                           benh_ans=benh_ans)

@app.route('/doctor/confirm/<int:lk_id>', methods=['POST'])
@login_required('bac_si')
def doctor_confirm(lk_id):
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    action = request.form.get('action')
    ghi_chu = request.form.get('ghi_chu', '')
    if action == 'confirm':
        conn.execute("UPDATE lich_kham SET trang_thai='da_xac_nhan', ghi_chu=? WHERE id=? AND bac_si_id=?", (ghi_chu, lk_id, bs['id']))
    elif action == 'reject':
        conn.execute("UPDATE lich_kham SET trang_thai='da_huy', ghi_chu=? WHERE id=? AND bac_si_id=?", (ghi_chu, lk_id, bs['id']))
    elif action == 'complete':
        conn.execute("UPDATE lich_kham SET trang_thai='hoan_thanh' WHERE id=? AND bac_si_id=?", (lk_id, bs['id']))
    conn.commit(); conn.close()
    flash('Cập nhật thành công!', 'success')
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/medical_record/<int:lk_id>', methods=['GET', 'POST'])
@login_required('bac_si')
def add_medical_record(lk_id):
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    lk = conn.execute("""
        SELECT lk.*, tkbn.ho_ten as ten_bn
        FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id = b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id = tkbn.id
        WHERE lk.id=? AND lk.bac_si_id=?
    """, (lk_id, bs['id'])).fetchone()
    if not lk:
        conn.close(); flash('Không tìm thấy lịch khám!', 'error'); return redirect(url_for('doctor_dashboard'))
    if request.method == 'POST':
        existing = conn.execute("SELECT id FROM ho_so_benh_an WHERE lich_kham_id=?", (lk_id,)).fetchone()
        if existing:
            conn.execute("UPDATE ho_so_benh_an SET trieu_chung=?, chan_doan=?, huong_dieu_tri=?, don_thuoc=?, ghi_chu_them=? WHERE lich_kham_id=?",
                         (request.form['trieu_chung'], request.form['chan_doan'], request.form['huong_dieu_tri'], request.form['don_thuoc'], request.form.get('ghi_chu_them', ''), lk_id))
        else:
            conn.execute("INSERT INTO ho_so_benh_an (lich_kham_id, trieu_chung, chan_doan, huong_dieu_tri, don_thuoc, ghi_chu_them) VALUES (?,?,?,?,?,?)",
                         (lk_id, request.form['trieu_chung'], request.form['chan_doan'], request.form['huong_dieu_tri'], request.form['don_thuoc'], request.form.get('ghi_chu_them', '')))
        conn.execute("UPDATE lich_kham SET trang_thai='hoan_thanh' WHERE id=?", (lk_id,))
        existing_hd = conn.execute("SELECT id FROM hoa_don WHERE lich_kham_id=?", (lk_id,)).fetchone()
        if not existing_hd:
            conn.execute("INSERT INTO hoa_don (lich_kham_id, so_tien, trang_thai) VALUES (?,?,?)", (lk_id, lk['phi_kham'], 'cho_thanh_toan'))
        conn.commit(); conn.close()
        flash('Đã lưu bệnh án và tạo hóa đơn!', 'success')
        return redirect(url_for('doctor_dashboard'))
    existing_record = conn.execute("SELECT * FROM ho_so_benh_an WHERE lich_kham_id=?", (lk_id,)).fetchone()
    conn.close()
    return render_template('medical_record.html', lk=lk, existing_record=existing_record)

@app.route('/doctor/invoice/<int:hd_id>')
@login_required('bac_si')
def doctor_invoice_detail(hd_id):
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    hd = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, lk.ly_do, lk.phi_kham,
               tk.ho_ten as ten_bs, ck.ten_chuyen_khoa, tkbn.ho_ten as ten_bn,
               tkkn.ho_ten as ten_bs_xn
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id = lk.id
        JOIN bac_si bslk ON lk.bac_si_id = bslk.id
        JOIN tai_khoan tk ON bslk.tai_khoan_id = tk.id
        JOIN chuyen_khoa ck ON bslk.chuyen_khoa_id = ck.id
        JOIN benh_nhan b ON lk.benh_nhan_id = b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id = tkbn.id
        LEFT JOIN bac_si bsxn ON hd.bac_si_xac_nhan_id = bsxn.id
        LEFT JOIN tai_khoan tkkn ON bsxn.tai_khoan_id = tkkn.id
        WHERE hd.id=? AND lk.bac_si_id=?
    """, (hd_id, bs['id'])).fetchone()
    conn.close()
    if not hd:
        flash('Không tìm thấy hóa đơn!', 'error'); return redirect(url_for('doctor_dashboard'))
    return render_template('invoice.html', hd=hd, role='bac_si')

@app.route('/doctor/invoice/confirm/<int:hd_id>', methods=['POST'])
@login_required('bac_si')
def doctor_confirm_payment(hd_id):
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    hd = conn.execute("SELECT hd.* FROM hoa_don hd JOIN lich_kham lk ON hd.lich_kham_id=lk.id WHERE hd.id=? AND lk.bac_si_id=?", (hd_id, bs['id'])).fetchone()
    if not hd:
        conn.close(); flash('Không có quyền xác nhận!', 'error'); return redirect(url_for('doctor_dashboard'))
    phuong_thuc = request.form.get('phuong_thuc_thanh_toan', 'tien_mat')
    ghi_chu = request.form.get('ghi_chu', '')
    conn.execute("UPDATE hoa_don SET trang_thai='da_thanh_toan', phuong_thuc_thanh_toan=?, ghi_chu=?, ngay_thanh_toan=?, bac_si_xac_nhan_id=? WHERE id=?",
                 (phuong_thuc, ghi_chu, datetime.now().strftime('%Y-%m-%d %H:%M'), bs['id'], hd_id))
    conn.commit(); conn.close()
    flash('Đã xác nhận thanh toán!', 'success')
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/invoice/cancel/<int:hd_id>', methods=['POST'])
@login_required('bac_si')
def doctor_cancel_invoice(hd_id):
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    hd = conn.execute("SELECT hd.* FROM hoa_don hd JOIN lich_kham lk ON hd.lich_kham_id=lk.id WHERE hd.id=? AND lk.bac_si_id=?", (hd_id, bs['id'])).fetchone()
    if not hd:
        conn.close(); flash('Không có quyền hủy!', 'error'); return redirect(url_for('doctor_dashboard'))
    conn.execute("UPDATE hoa_don SET trang_thai='da_huy' WHERE id=?", (hd_id,))
    conn.commit(); conn.close()
    flash('Đã hủy hóa đơn!', 'success')
    return redirect(url_for('doctor_dashboard'))

# ==================== ADMIN ====================

@app.route('/admin/dashboard')
@login_required('admin')
def admin_dashboard():
    conn = get_db()
    doctor_count = conn.execute("SELECT COUNT(*) FROM bac_si").fetchone()[0]
    patient_count = conn.execute("SELECT COUNT(*) FROM benh_nhan").fetchone()[0]
    appt_count = conn.execute("SELECT COUNT(*) FROM lich_kham").fetchone()[0]
    specialty_count = conn.execute("SELECT COUNT(*) FROM chuyen_khoa").fetchone()[0]
    pending_count = conn.execute("SELECT COUNT(*) FROM lich_kham WHERE trang_thai='cho_xac_nhan'").fetchone()[0]
    recent_appts = conn.execute("""
        SELECT lk.*, tkbn.ho_ten as ten_bn, tkbs.ho_ten as ten_bs FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        ORDER BY lk.ngay_tao DESC LIMIT 10
    """).fetchall()
    conn.close()
    return render_template('admin_dashboard.html', doctor_count=doctor_count, patient_count=patient_count,
                           appt_count=appt_count, specialty_count=specialty_count,
                           pending_count=pending_count, recent_appts=recent_appts)

@app.route('/admin/doctors')
@login_required('admin')
def admin_doctors():
    conn = get_db()
    doctors = conn.execute("SELECT bs.*, tk.ho_ten, tk.email, tk.so_dien_thoai, tk.trang_thai as tk_trang_thai, tk.ten_dang_nhap, ck.ten_chuyen_khoa FROM bac_si bs JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id LEFT JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id ORDER BY tk.ho_ten").fetchall()
    specialties = conn.execute("SELECT * FROM chuyen_khoa").fetchall()
    conn.close()
    return render_template('admin_doctors.html', doctors=doctors, specialties=specialties)

@app.route('/admin/doctors/add', methods=['POST'])
@login_required('admin')
def admin_add_doctor():
    data = request.form; conn = get_db()
    existing = conn.execute("SELECT id FROM tai_khoan WHERE ten_dang_nhap=?", (data['ten_dang_nhap'],)).fetchone()
    if existing:
        flash('Tên đăng nhập đã tồn tại!', 'error')
    else:
        pw = generate_password_hash(data['mat_khau']); c = conn.cursor()
        c.execute("INSERT INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email, so_dien_thoai) VALUES (?,?,?,?,?,?)",
                  (data['ten_dang_nhap'], pw, 'bac_si', data['ho_ten'], data['email'], data['so_dien_thoai']))
        tk_id = c.lastrowid
        c.execute("INSERT INTO bac_si (tai_khoan_id, chuyen_khoa_id, bang_cap, kinh_nghiem, phi_kham) VALUES (?,?,?,?,?)",
                  (tk_id, data['chuyen_khoa_id'], data.get('bang_cap', ''), data.get('kinh_nghiem', ''), int(data.get('phi_kham', 200000))))
        conn.commit(); flash('Thêm bác sĩ thành công!', 'success')
    conn.close()
    return redirect(url_for('admin_doctors'))

@app.route('/admin/doctors/delete/<int:bs_id>', methods=['POST'])
@login_required('admin')
def admin_delete_doctor(bs_id):
    conn = get_db()
    bs = conn.execute("SELECT tai_khoan_id FROM bac_si WHERE id=?", (bs_id,)).fetchone()
    if bs:
        conn.execute("UPDATE tai_khoan SET trang_thai=0 WHERE id=?", (bs['tai_khoan_id'],)); conn.commit()
        flash('Đã vô hiệu hóa bác sĩ!', 'success')
    conn.close()
    return redirect(url_for('admin_doctors'))

@app.route('/admin/patients')
@login_required('admin')
def admin_patients():
    conn = get_db()
    patients = conn.execute("SELECT b.*, tk.ho_ten, tk.email, tk.so_dien_thoai, tk.trang_thai as tk_trang_thai, tk.ten_dang_nhap FROM benh_nhan b JOIN tai_khoan tk ON b.tai_khoan_id=tk.id ORDER BY tk.ho_ten").fetchall()
    conn.close()
    return render_template('admin_patients.html', patients=patients)

@app.route('/admin/specialties')
@login_required('admin')
def admin_specialties():
    conn = get_db()
    specialties = conn.execute("SELECT ck.*, COUNT(bs.id) as so_bac_si FROM chuyen_khoa ck LEFT JOIN bac_si bs ON ck.id=bs.chuyen_khoa_id GROUP BY ck.id ORDER BY ck.ten_chuyen_khoa").fetchall()
    conn.close()
    return render_template('admin_specialties.html', specialties=specialties)

@app.route('/admin/specialties/add', methods=['POST'])
@login_required('admin')
def admin_add_specialty():
    conn = get_db()
    conn.execute("INSERT INTO chuyen_khoa (ten_chuyen_khoa, mo_ta) VALUES (?,?)", (request.form['ten_chuyen_khoa'], request.form.get('mo_ta', '')))
    conn.commit(); conn.close()
    flash('Thêm chuyên khoa thành công!', 'success')
    return redirect(url_for('admin_specialties'))

@app.route('/admin/specialties/delete/<int:ck_id>', methods=['POST'])
@login_required('admin')
def admin_delete_specialty(ck_id):
    conn = get_db()
    conn.execute("DELETE FROM chuyen_khoa WHERE id=?", (ck_id,)); conn.commit(); conn.close()
    flash('Đã xóa chuyên khoa!', 'success')
    return redirect(url_for('admin_specialties'))

@app.route('/admin/appointments')
@login_required('admin')
def admin_appointments():
    conn = get_db()
    appointments = conn.execute("""
        SELECT lk.*, tkbn.ho_ten as ten_bn, tkbs.ho_ten as ten_bs, ck.ten_chuyen_khoa FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        ORDER BY lk.ngay_kham DESC, lk.gio_kham DESC
    """).fetchall()
    conn.close()
    return render_template('admin_appointments.html', appointments=appointments)

@app.route('/admin/appointments/update/<int:lk_id>', methods=['POST'])
@login_required('admin')
def admin_update_appointment(lk_id):
    conn = get_db()
    conn.execute("UPDATE lich_kham SET trang_thai=? WHERE id=?", (request.form['trang_thai'], lk_id))
    conn.commit(); conn.close()
    flash('Cập nhật thành công!', 'success')
    return redirect(url_for('admin_appointments'))

# ==================== SWAGGER / FLASGGER ====================
from flasgger import Swagger

swagger_config = {
    "headers": [],
    "specs": [{
        "endpoint": "apispec",
        "route": "/apispec.json",
        "rule_filter": lambda rule: rule.rule.startswith("/api/v1"),
        "model_filter": lambda tag: True,
    }],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs",
}

swagger_template = {
    "info": {
        "title": "MediCare API",
        "description": "API đặt lịch khám bệnh.\n\nNhấn **Authorize** và nhập API Key vào ô **Value** để dùng được tất cả endpoint.",
        "version": "1.0.0",
    },
    "securityDefinitions": {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    },
    "security": [{"ApiKeyAuth": []}],
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# ==================== PUBLIC API (cần X-API-Key) ====================

@app.route('/api/booked_slots')
def api_booked_slots_legacy():
    """Endpoint cũ — dùng nội bộ cho form đặt lịch (không cần API Key)"""
    bac_si_id = request.args.get('bac_si_id')
    ngay_kham = request.args.get('ngay_kham')
    if not bac_si_id or not ngay_kham:
        return jsonify([])
    conn = get_db()
    rows = conn.execute(
        "SELECT gio_kham FROM lich_kham WHERE bac_si_id=? AND ngay_kham=? AND trang_thai NOT IN ('da_huy')",
        (bac_si_id, ngay_kham)
    ).fetchall()
    conn.close()
    return jsonify([r['gio_kham'] for r in rows])

@app.route('/api/doctors_by_specialty/<int:ck_id>')
def api_doctors_by_specialty(ck_id):
    """Endpoint cũ — dùng nội bộ (không cần API Key)"""
    conn = get_db()
    doctors = conn.execute("SELECT bs.id, tk.ho_ten, bs.phi_kham, bs.kinh_nghiem FROM bac_si bs JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id WHERE bs.chuyen_khoa_id=? AND tk.trang_thai=1", (ck_id,)).fetchall()
    conn.close()
    return jsonify([dict(d) for d in doctors])

@app.route('/api/v1/info')
@require_api_key
def api_info():
    """
    Thông tin phiên bản API
    ---
    tags:
      - 1. Info
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Thông tin API
        schema:
          type: object
          properties:
            name:
              type: string
              example: MediCare API
            version:
              type: string
              example: "1.0"
      401:
        description: Thiếu hoặc sai API Key
    """
    return jsonify({
        'name': 'MediCare API',
        'version': '1.0',
        'endpoints': [
            'GET /api/v1/info',
            'GET /api/v1/specialties',
            'GET /api/v1/doctors',
            'GET /api/v1/doctors/<id>',
            'GET /api/v1/booked_slots?bac_si_id=&ngay_kham=',
            'POST /api/v1/appointments',
            'GET /api/v1/appointments',
            'GET /api/v1/appointments/<id>',
            'PUT /api/v1/appointments/<id>/status',
            'GET /api/v1/patients',
            'GET /api/v1/patients/<id>',
        ]
    })

@app.route('/api/v1/specialties')
@require_api_key
def api_v1_specialties():
    """
    Danh sách chuyên khoa
    ---
    tags:
      - 2. Chuyên khoa
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Danh sách chuyên khoa
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                example: 1
              ten_chuyen_khoa:
                type: string
                example: Nội khoa
              mo_ta:
                type: string
                example: Khám nội khoa
      401:
        description: Thiếu hoặc sai API Key
    """
    conn = get_db()
    rows = conn.execute("SELECT * FROM chuyen_khoa ORDER BY ten_chuyen_khoa").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/v1/doctors')
@require_api_key
def api_v1_doctors():
    """
    Danh sách bác sĩ
    ---
    tags:
      - 3. Bác sĩ
    security:
      - ApiKeyAuth: []
    parameters:
      - name: chuyen_khoa_id
        in: query
        type: integer
        required: false
        description: Lọc theo ID chuyên khoa
        example: 1
    responses:
      200:
        description: Danh sách bác sĩ
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                example: 1
              ho_ten:
                type: string
                example: BS. Nguyễn Văn An
              ten_chuyen_khoa:
                type: string
                example: Nội khoa
              phi_kham:
                type: integer
                example: 200000
              kinh_nghiem:
                type: string
                example: 10 năm kinh nghiệm
              email:
                type: string
                example: nguyenan@medicare.vn
      401:
        description: Thiếu hoặc sai API Key
    """
    conn = get_db()
    ck_id = request.args.get('chuyen_khoa_id')
    if ck_id:
        rows = conn.execute("""
            SELECT bs.id, tk.ho_ten, tk.email, tk.so_dien_thoai,
                   bs.bang_cap, bs.kinh_nghiem, bs.phi_kham, ck.ten_chuyen_khoa
            FROM bac_si bs
            JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
            JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
            WHERE tk.trang_thai=1 AND bs.chuyen_khoa_id=?
            ORDER BY tk.ho_ten
        """, (ck_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT bs.id, tk.ho_ten, tk.email, tk.so_dien_thoai,
                   bs.bang_cap, bs.kinh_nghiem, bs.phi_kham, ck.ten_chuyen_khoa
            FROM bac_si bs
            JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
            JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
            WHERE tk.trang_thai=1
            ORDER BY tk.ho_ten
        """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/v1/doctors/<int:bs_id>')
@require_api_key
def api_v1_doctor_detail(bs_id):
    """
    Chi tiết một bác sĩ
    ---
    tags:
      - 3. Bác sĩ
    security:
      - ApiKeyAuth: []
    parameters:
      - name: bs_id
        in: path
        type: integer
        required: true
        description: ID bác sĩ
        example: 1
    responses:
      200:
        description: Thông tin chi tiết bác sĩ
        schema:
          type: object
          properties:
            id:
              type: integer
              example: 1
            ho_ten:
              type: string
              example: BS. Nguyễn Văn An
            ten_chuyen_khoa:
              type: string
              example: Nội khoa
            phi_kham:
              type: integer
              example: 200000
            bang_cap:
              type: string
              example: Tiến sĩ Y khoa
            kinh_nghiem:
              type: string
              example: 10 năm kinh nghiệm
            mo_ta:
              type: string
              example: Bác sĩ chuyên khoa
      401:
        description: Thiếu hoặc sai API Key
      404:
        description: Không tìm thấy bác sĩ
    """
    conn = get_db()
    row = conn.execute("""
        SELECT bs.id, tk.ho_ten, tk.email, tk.so_dien_thoai,
               bs.bang_cap, bs.kinh_nghiem, bs.phi_kham, bs.mo_ta,
               ck.ten_chuyen_khoa
        FROM bac_si bs
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE bs.id=? AND tk.trang_thai=1
    """, (bs_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Không tìm thấy bác sĩ'}), 404
    return jsonify(dict(row))

@app.route('/api/v1/booked_slots')
@require_api_key
def api_v1_booked_slots():
    """
    Khung giờ đã được đặt theo bác sĩ và ngày
    ---
    tags:
      - 4. Lịch khám
    security:
      - ApiKeyAuth: []
    parameters:
      - name: bac_si_id
        in: query
        type: integer
        required: true
        description: ID bác sĩ
        example: 1
      - name: ngay_kham
        in: query
        type: string
        required: true
        description: Ngày khám định dạng YYYY-MM-DD
        example: "2026-04-15"
    responses:
      200:
        description: Danh sách giờ đã đặt
        schema:
          type: object
          properties:
            ngay_kham:
              type: string
              example: "2026-04-15"
            da_dat:
              type: array
              items:
                type: string
              example: ["08:00", "10:00"]
      400:
        description: Thiếu tham số bắt buộc
      401:
        description: Thiếu hoặc sai API Key
    """
    bac_si_id = request.args.get('bac_si_id')
    ngay_kham = request.args.get('ngay_kham')
    if not bac_si_id or not ngay_kham:
        return jsonify({'error': 'Thiếu bac_si_id hoặc ngay_kham'}), 400
    conn = get_db()
    rows = conn.execute(
        "SELECT gio_kham FROM lich_kham WHERE bac_si_id=? AND ngay_kham=? AND trang_thai NOT IN ('da_huy')",
        (bac_si_id, ngay_kham)
    ).fetchall()
    conn.close()
    return jsonify({'ngay_kham': ngay_kham, 'da_dat': [r['gio_kham'] for r in rows]})

@app.route('/api/v1/appointments', methods=['GET'])
@require_api_key
def api_v1_list_appointments():
    """
    Danh sách lịch khám
    ---
    tags:
      - 4. Lịch khám
    security:
      - ApiKeyAuth: []
    parameters:
      - name: bac_si_id
        in: query
        type: integer
        required: false
        description: Lọc theo bác sĩ
      - name: benh_nhan_id
        in: query
        type: integer
        required: false
        description: Lọc theo bệnh nhân
      - name: trang_thai
        in: query
        type: string
        required: false
        description: "Trạng thái: cho_xac_nhan | da_xac_nhan | hoan_thanh | da_huy"
        example: cho_xac_nhan
      - name: ngay_kham
        in: query
        type: string
        required: false
        description: Lọc theo ngày (YYYY-MM-DD)
        example: "2026-04-15"
    responses:
      200:
        description: Danh sách lịch khám
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                example: 1
              ten_bn:
                type: string
                example: Phạm Minh Đức
              ten_bs:
                type: string
                example: BS. Nguyễn Văn An
              ngay_kham:
                type: string
                example: "2026-04-15"
              gio_kham:
                type: string
                example: "09:00"
              trang_thai:
                type: string
                example: cho_xac_nhan
              phi_kham:
                type: integer
                example: 200000
      401:
        description: Thiếu hoặc sai API Key
    """
    conn = get_db()
    filters = []
    params = []
    if request.args.get('bac_si_id'):
        filters.append("lk.bac_si_id=?"); params.append(request.args['bac_si_id'])
    if request.args.get('benh_nhan_id'):
        filters.append("lk.benh_nhan_id=?"); params.append(request.args['benh_nhan_id'])
    if request.args.get('trang_thai'):
        filters.append("lk.trang_thai=?"); params.append(request.args['trang_thai'])
    if request.args.get('ngay_kham'):
        filters.append("lk.ngay_kham=?"); params.append(request.args['ngay_kham'])
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = conn.execute(f"""
        SELECT lk.id, lk.ngay_kham, lk.gio_kham, lk.trang_thai, lk.phi_kham, lk.ly_do, lk.ghi_chu,
               tkbn.ho_ten as ten_bn, tkbs.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        {where}
        ORDER BY lk.ngay_kham DESC, lk.gio_kham DESC
    """, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/v1/appointments', methods=['POST'])
@require_api_key
def api_v1_create_appointment():
    """
    Đặt lịch khám mới
    ---
    tags:
      - 4. Lịch khám
    security:
      - ApiKeyAuth: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - benh_nhan_id
            - bac_si_id
            - ngay_kham
            - gio_kham
          properties:
            benh_nhan_id:
              type: integer
              example: 1
            bac_si_id:
              type: integer
              example: 1
            ngay_kham:
              type: string
              example: "2026-04-15"
            gio_kham:
              type: string
              example: "09:00"
            ly_do:
              type: string
              example: Khám tổng quát
    responses:
      201:
        description: Đặt lịch thành công
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            lich_kham_id:
              type: integer
              example: 5
            phi_kham:
              type: integer
              example: 200000
      400:
        description: Thiếu trường bắt buộc
      401:
        description: Thiếu hoặc sai API Key
      409:
        description: Khung giờ đã được đặt
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Body phải là JSON'}), 400
    for field in ['benh_nhan_id', 'bac_si_id', 'ngay_kham', 'gio_kham']:
        if not data.get(field):
            return jsonify({'error': f'Thiếu trường: {field}'}), 400
    conn = get_db()
    conflict = conn.execute(
        "SELECT id FROM lich_kham WHERE bac_si_id=? AND ngay_kham=? AND gio_kham=? AND trang_thai NOT IN ('da_huy')",
        (data['bac_si_id'], data['ngay_kham'], data['gio_kham'])
    ).fetchone()
    if conflict:
        conn.close()
        return jsonify({'error': 'Khung giờ này đã được đặt'}), 409
    bs = conn.execute("SELECT phi_kham FROM bac_si WHERE id=?", (data['bac_si_id'],)).fetchone()
    phi = bs['phi_kham'] if bs else 200000
    conn.execute(
        "INSERT INTO lich_kham (benh_nhan_id, bac_si_id, ngay_kham, gio_kham, ly_do, phi_kham) VALUES (?,?,?,?,?,?)",
        (data['benh_nhan_id'], data['bac_si_id'], data['ngay_kham'], data['gio_kham'], data.get('ly_do', ''), phi)
    )
    conn.commit()
    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({'success': True, 'lich_kham_id': new_id, 'phi_kham': phi}), 201

@app.route('/api/v1/appointments/<int:lk_id>')
@require_api_key
def api_v1_appointment_detail(lk_id):
    """
    Chi tiết một lịch khám
    ---
    tags:
      - 4. Lịch khám
    security:
      - ApiKeyAuth: []
    parameters:
      - name: lk_id
        in: path
        type: integer
        required: true
        description: ID lịch khám
        example: 1
    responses:
      200:
        description: Chi tiết lịch khám
        schema:
          type: object
          properties:
            id:
              type: integer
              example: 1
            ten_bn:
              type: string
              example: Phạm Minh Đức
            ten_bs:
              type: string
              example: BS. Nguyễn Văn An
            ngay_kham:
              type: string
              example: "2026-04-15"
            gio_kham:
              type: string
              example: "09:00"
            trang_thai:
              type: string
              example: cho_xac_nhan
            phi_kham:
              type: integer
              example: 200000
      401:
        description: Thiếu hoặc sai API Key
      404:
        description: Không tìm thấy lịch khám
    """
    conn = get_db()
    row = conn.execute("""
        SELECT lk.*, tkbn.ho_ten as ten_bn, tkbn.email as email_bn, tkbn.so_dien_thoai as sdt_bn,
               tkbs.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.id=?
    """, (lk_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Không tìm thấy lịch khám'}), 404
    return jsonify(dict(row))

@app.route('/api/v1/appointments/<int:lk_id>/status', methods=['PUT'])
@require_api_key
def api_v1_update_appointment_status(lk_id):
    """
    Cập nhật trạng thái lịch khám
    ---
    tags:
      - 4. Lịch khám
    security:
      - ApiKeyAuth: []
    parameters:
      - name: lk_id
        in: path
        type: integer
        required: true
        description: ID lịch khám
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - trang_thai
          properties:
            trang_thai:
              type: string
              description: "cho_xac_nhan | da_xac_nhan | hoan_thanh | da_huy"
              example: da_xac_nhan
            ghi_chu:
              type: string
              example: Đã xác nhận
    responses:
      200:
        description: Cập nhật thành công
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
      400:
        description: Trạng thái không hợp lệ
      401:
        description: Thiếu hoặc sai API Key
      404:
        description: Không tìm thấy lịch khám
    """
    data = request.get_json()
    if not data or not data.get('trang_thai'):
        return jsonify({'error': 'Thiếu trường trang_thai'}), 400
    valid = ('cho_xac_nhan', 'da_xac_nhan', 'hoan_thanh', 'da_huy')
    if data['trang_thai'] not in valid:
        return jsonify({'error': f'trang_thai phải là một trong: {", ".join(valid)}'}), 400
    conn = get_db()
    row = conn.execute("SELECT id FROM lich_kham WHERE id=?", (lk_id,)).fetchone()
    if not row:
        conn.close(); return jsonify({'error': 'Không tìm thấy lịch khám'}), 404
    conn.execute("UPDATE lich_kham SET trang_thai=?, ghi_chu=? WHERE id=?",
                 (data['trang_thai'], data.get('ghi_chu', ''), lk_id))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/api/v1/patients')
@require_api_key
def api_v1_patients():
    """
    Danh sách bệnh nhân
    ---
    tags:
      - 5. Bệnh nhân
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Danh sách bệnh nhân
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                example: 1
              ho_ten:
                type: string
                example: Phạm Minh Đức
              email:
                type: string
                example: pham.duc@email.com
              so_dien_thoai:
                type: string
                example: "0911111111"
              ngay_sinh:
                type: string
                example: "1990-05-15"
              gioi_tinh:
                type: string
                example: Nam
      401:
        description: Thiếu hoặc sai API Key
    """
    conn = get_db()
    rows = conn.execute("""
        SELECT b.id, tk.ho_ten, tk.email, tk.so_dien_thoai,
               b.ngay_sinh, b.gioi_tinh, b.dia_chi
        FROM benh_nhan b
        JOIN tai_khoan tk ON b.tai_khoan_id=tk.id
        WHERE tk.trang_thai=1
        ORDER BY tk.ho_ten
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/v1/patients/<int:bn_id>')
@require_api_key
def api_v1_patient_detail(bn_id):
    """
    Chi tiết một bệnh nhân và lịch sử khám
    ---
    tags:
      - 5. Bệnh nhân
    security:
      - ApiKeyAuth: []
    parameters:
      - name: bn_id
        in: path
        type: integer
        required: true
        description: ID bệnh nhân
        example: 1
    responses:
      200:
        description: Thông tin bệnh nhân và lịch sử khám
        schema:
          type: object
          properties:
            benh_nhan:
              type: object
              properties:
                id:
                  type: integer
                  example: 1
                ho_ten:
                  type: string
                  example: Phạm Minh Đức
                email:
                  type: string
                  example: pham.duc@email.com
            lich_su_kham:
              type: array
              items:
                type: object
      401:
        description: Thiếu hoặc sai API Key
      404:
        description: Không tìm thấy bệnh nhân
    """
    conn = get_db()
    bn = conn.execute("""
        SELECT b.id, tk.ho_ten, tk.email, tk.so_dien_thoai, b.ngay_sinh, b.gioi_tinh, b.dia_chi
        FROM benh_nhan b JOIN tai_khoan tk ON b.tai_khoan_id=tk.id
        WHERE b.id=?
    """, (bn_id,)).fetchone()
    if not bn:
        conn.close(); return jsonify({'error': 'Không tìm thấy bệnh nhân'}), 404
    history = conn.execute("""
        SELECT lk.id, lk.ngay_kham, lk.gio_kham, lk.trang_thai, lk.phi_kham, lk.ly_do,
               tkbs.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM lich_kham lk
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.benh_nhan_id=?
        ORDER BY lk.ngay_kham DESC
    """, (bn_id,)).fetchall()
    conn.close()
    return jsonify({'benh_nhan': dict(bn), 'lich_su_kham': [dict(r) for r in history]})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
