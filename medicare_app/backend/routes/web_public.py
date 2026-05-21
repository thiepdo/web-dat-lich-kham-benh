from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from models.database import get_db

web_public_bp = Blueprint('web_public', __name__)


@web_public_bp.route('/')
def index():
    return render_template('shared/index.html')


@web_public_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM tai_khoan WHERE ten_dang_nhap=? AND trang_thai=1", (username,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user['mat_khau'], password):
            session['user_id'] = user['id']
            session['username'] = user['ten_dang_nhap']
            session['vai_tro'] = user['vai_tro']
            session['ho_ten'] = user['ho_ten']
            if user['vai_tro'] == 'admin':
                return redirect(url_for('web_admin.dashboard'))
            elif user['vai_tro'] == 'bac_si':
                return redirect(url_for('web_doctor.dashboard'))
            else:
                return redirect(url_for('web_patient.dashboard'))
        flash('Tên đăng nhập hoặc mật khẩu không đúng!', 'error')
    return render_template('auth/login.html')


@web_public_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        conn = get_db()
        if conn.execute("SELECT id FROM tai_khoan WHERE ten_dang_nhap=?", (data['username'],)).fetchone():
            conn.close()
            flash('Tên đăng nhập đã tồn tại!', 'error')
            return render_template('auth/register.html')
        pw = generate_password_hash(data['password'])
        c = conn.cursor()
        c.execute(
            "INSERT INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email, so_dien_thoai) VALUES (?,?,?,?,?,?)",
            (data['username'], pw, 'benh_nhan', data['ho_ten'], data['email'], data['so_dien_thoai'])
        )
        tk_id = c.lastrowid
        c.execute(
            "INSERT INTO benh_nhan (tai_khoan_id, ngay_sinh, gioi_tinh, dia_chi) VALUES (?,?,?,?)",
            (tk_id, data.get('ngay_sinh', ''), data.get('gioi_tinh', ''), data.get('dia_chi', ''))
        )
        conn.commit(); conn.close()
        flash('Đăng ký thành công!', 'success')
        return redirect(url_for('web_public.login'))
    return render_template('auth/register.html')


@web_public_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('web_public.index'))
