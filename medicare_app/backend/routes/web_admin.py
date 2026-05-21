from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from models.database import get_db
from middleware.auth import login_required

# ================================================================
# web_admin.py — Giao diện quản trị viên
# URL prefix: /admin/...
# Template:   frontend/templates/admin/
# ================================================================

web_admin_bp = Blueprint('web_admin', __name__)


# ── TRANG CHỦ ADMIN ─────────────────────────────────────────────
# URL: /admin/dashboard
# Hiển thị: số liệu tổng hợp, lịch khám gần đây, mini chart doanh thu
@web_admin_bp.route('/dashboard')
@login_required('admin')
def dashboard():
    conn = get_db()

    # Đếm tổng số các đối tượng trong hệ thống
    stats = {
        'doctor_count':    conn.execute("SELECT COUNT(*) FROM bac_si").fetchone()[0],
        'patient_count':   conn.execute("SELECT COUNT(*) FROM benh_nhan").fetchone()[0],
        'appt_count':      conn.execute("SELECT COUNT(*) FROM lich_kham").fetchone()[0],
        'specialty_count': conn.execute("SELECT COUNT(*) FROM chuyen_khoa").fetchone()[0],
        'pending_count':   conn.execute("SELECT COUNT(*) FROM lich_kham WHERE trang_thai='cho_xac_nhan'").fetchone()[0],
    }

    # 10 lịch khám được tạo gần nhất
    recent_appts = conn.execute("""
        SELECT lk.*, tkbn.ho_ten as ten_bn, tkbs.ho_ten as ten_bs FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        ORDER BY lk.ngay_tao DESC LIMIT 10
    """).fetchall()

    # Doanh thu 6 tháng gần nhất (dữ liệu cho mini line chart)
    monthly_revenue = conn.execute("""
        SELECT strftime('%Y-%m', ngay_thanh_toan) as thang,
               SUM(so_tien) as doanh_thu,
               COUNT(*) as so_hoa_don
        FROM hoa_don WHERE trang_thai='da_thanh_toan' AND ngay_thanh_toan IS NOT NULL
        GROUP BY thang ORDER BY thang DESC LIMIT 6
    """).fetchall()

    # Tổng doanh thu đã thu & số tiền đang chờ thanh toán
    revenue_overview = conn.execute("""
        SELECT
            SUM(CASE WHEN trang_thai='da_thanh_toan' THEN so_tien ELSE 0 END) as tong_doanh_thu,
            SUM(CASE WHEN trang_thai='cho_thanh_toan' THEN so_tien ELSE 0 END) as cho_thanh_toan
        FROM hoa_don
    """).fetchone()

    conn.close()
    return render_template('admin/dashboard.html',
        **stats,
        recent_appts=recent_appts,
        monthly_revenue=monthly_revenue,
        revenue_overview=revenue_overview)


# ── QUẢN LÝ BÁC SĨ ──────────────────────────────────────────────
# URL: /admin/doctors
# Hiển thị: danh sách bác sĩ, tìm kiếm, lọc theo chuyên khoa/trạng thái
@web_admin_bp.route('/doctors')
@login_required('admin')
def doctors():
    conn = get_db()
    # Lấy toàn bộ bác sĩ kèm thông tin tài khoản và chuyên khoa
    doctors = conn.execute("""
        SELECT bs.*, tk.ho_ten, tk.email, tk.so_dien_thoai,
               tk.trang_thai as tk_trang_thai, tk.ten_dang_nhap, ck.ten_chuyen_khoa
        FROM bac_si bs JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        LEFT JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id ORDER BY tk.ho_ten
    """).fetchall()
    specialties = conn.execute("SELECT * FROM chuyen_khoa").fetchall()
    conn.close()
    return render_template('admin/doctors.html', doctors=doctors, specialties=specialties)


# URL: /admin/doctors/add  [POST]
# Thêm bác sĩ mới: tạo tài khoản + hồ sơ bác sĩ
@web_admin_bp.route('/doctors/add', methods=['POST'])
@login_required('admin')
def add_doctor():
    data = request.form; conn = get_db()
    if conn.execute("SELECT id FROM tai_khoan WHERE ten_dang_nhap=?", (data['ten_dang_nhap'],)).fetchone():
        flash('Tên đăng nhập đã tồn tại!', 'error')
    else:
        pw = generate_password_hash(data['mat_khau']); c = conn.cursor()
        # Tạo tài khoản với vai trò bac_si
        c.execute("INSERT INTO tai_khoan (ten_dang_nhap, mat_khau, vai_tro, ho_ten, email, so_dien_thoai) VALUES (?,?,?,?,?,?)",
                  (data['ten_dang_nhap'], pw, 'bac_si', data['ho_ten'], data['email'], data['so_dien_thoai']))
        tk_id = c.lastrowid
        # Tạo hồ sơ bác sĩ liên kết với tài khoản vừa tạo
        c.execute("INSERT INTO bac_si (tai_khoan_id, chuyen_khoa_id, bang_cap, kinh_nghiem, phi_kham) VALUES (?,?,?,?,?)",
                  (tk_id, data['chuyen_khoa_id'], data.get('bang_cap',''), data.get('kinh_nghiem',''), int(data.get('phi_kham', 200000))))
        conn.commit(); flash('Thêm bác sĩ thành công!', 'success')
    conn.close()
    return redirect(url_for('web_admin.doctors'))


# URL: /admin/doctors/delete/<bs_id>  [POST]
# Vô hiệu hóa bác sĩ (không xóa, chỉ đặt trang_thai=0)
@web_admin_bp.route('/doctors/delete/<int:bs_id>', methods=['POST'])
@login_required('admin')
def delete_doctor(bs_id):
    conn = get_db()
    bs = conn.execute("SELECT tai_khoan_id FROM bac_si WHERE id=?", (bs_id,)).fetchone()
    if bs:
        conn.execute("UPDATE tai_khoan SET trang_thai=0 WHERE id=?", (bs['tai_khoan_id'],))
        conn.commit(); flash('Đã vô hiệu hóa bác sĩ!', 'success')
    conn.close()
    return redirect(url_for('web_admin.doctors'))


# URL: /admin/doctors/activate/<bs_id>  [POST]
# Kích hoạt lại bác sĩ đã bị vô hiệu hóa (đặt trang_thai=1)
@web_admin_bp.route('/doctors/activate/<int:bs_id>', methods=['POST'])
@login_required('admin')
def activate_doctor(bs_id):
    conn = get_db()
    bs = conn.execute("SELECT tai_khoan_id FROM bac_si WHERE id=?", (bs_id,)).fetchone()
    if bs:
        conn.execute("UPDATE tai_khoan SET trang_thai=1 WHERE id=?", (bs['tai_khoan_id'],))
        conn.commit(); flash('Đã kích hoạt lại bác sĩ!', 'success')
    conn.close()
    return redirect(url_for('web_admin.doctors'))


# URL: /admin/doctors/edit/<bs_id>  [POST]
# Cập nhật thông tin bác sĩ (tên, email, SĐT, chuyên khoa, bằng cấp, phí khám)
@web_admin_bp.route('/doctors/edit/<int:bs_id>', methods=['POST'])
@login_required('admin')
def edit_doctor(bs_id):
    data = request.form
    conn = get_db()
    bs = conn.execute("SELECT tai_khoan_id FROM bac_si WHERE id=?", (bs_id,)).fetchone()
    if bs:
        # Cập nhật thông tin tài khoản
        conn.execute(
            "UPDATE tai_khoan SET ho_ten=?, email=?, so_dien_thoai=? WHERE id=?",
            (data['ho_ten'], data.get('email',''), data.get('so_dien_thoai',''), bs['tai_khoan_id'])
        )
        # Cập nhật hồ sơ bác sĩ
        conn.execute(
            "UPDATE bac_si SET chuyen_khoa_id=?, bang_cap=?, kinh_nghiem=?, phi_kham=? WHERE id=?",
            (data['chuyen_khoa_id'], data.get('bang_cap',''),
             data.get('kinh_nghiem',''), int(data.get('phi_kham', 200000)), bs_id)
        )
        conn.commit()
        flash('Cập nhật thông tin bác sĩ thành công!', 'success')
    conn.close()
    return redirect(url_for('web_admin.doctors'))


# ── QUẢN LÝ BỆNH NHÂN ───────────────────────────────────────────
# URL: /admin/patients
# Hiển thị danh sách toàn bộ bệnh nhân
@web_admin_bp.route('/patients')
@login_required('admin')
def patients():
    conn = get_db()
    patients = conn.execute("""
        SELECT b.*, tk.ho_ten, tk.email, tk.so_dien_thoai,
               tk.trang_thai as tk_trang_thai, tk.ten_dang_nhap
        FROM benh_nhan b JOIN tai_khoan tk ON b.tai_khoan_id=tk.id ORDER BY tk.ho_ten
    """).fetchall()
    conn.close()
    return render_template('admin/patients.html', patients=patients)


# ── QUẢN LÝ CHUYÊN KHOA ─────────────────────────────────────────
# URL: /admin/specialties
# Hiển thị danh sách chuyên khoa kèm số bác sĩ mỗi khoa
@web_admin_bp.route('/specialties')
@login_required('admin')
def specialties():
    conn = get_db()
    specialties = conn.execute("""
        SELECT ck.*, COUNT(bs.id) as so_bac_si FROM chuyen_khoa ck
        LEFT JOIN bac_si bs ON ck.id=bs.chuyen_khoa_id
        GROUP BY ck.id ORDER BY ck.ten_chuyen_khoa
    """).fetchall()
    conn.close()
    return render_template('admin/specialties.html', specialties=specialties)


# URL: /admin/specialties/add  [POST]
# Thêm chuyên khoa mới
@web_admin_bp.route('/specialties/add', methods=['POST'])
@login_required('admin')
def add_specialty():
    conn = get_db()
    conn.execute("INSERT INTO chuyen_khoa (ten_chuyen_khoa, mo_ta) VALUES (?,?)",
                 (request.form['ten_chuyen_khoa'], request.form.get('mo_ta','')))
    conn.commit(); conn.close()
    flash('Thêm chuyên khoa thành công!', 'success')
    return redirect(url_for('web_admin.specialties'))


# URL: /admin/specialties/delete/<ck_id>  [POST]
# Xóa chuyên khoa (cẩn thận: sẽ ảnh hưởng bác sĩ thuộc khoa này)
@web_admin_bp.route('/specialties/delete/<int:ck_id>', methods=['POST'])
@login_required('admin')
def delete_specialty(ck_id):
    conn = get_db()
    conn.execute("DELETE FROM chuyen_khoa WHERE id=?", (ck_id,))
    conn.commit(); conn.close()
    flash('Đã xóa chuyên khoa!', 'success')
    return redirect(url_for('web_admin.specialties'))


# ── QUẢN LÝ LỊCH KHÁM ───────────────────────────────────────────
# URL: /admin/appointments
# Hiển thị toàn bộ lịch khám, sắp xếp mới nhất lên đầu
@web_admin_bp.route('/appointments')
@login_required('admin')
def appointments():
    conn = get_db()
    appointments = conn.execute("""
        SELECT lk.*, tkbn.ho_ten as ten_bn, tkbs.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        ORDER BY lk.ngay_kham DESC, lk.gio_kham DESC
    """).fetchall()
    conn.close()
    return render_template('admin/appointments.html', appointments=appointments)


# URL: /admin/appointments/update/<lk_id>  [POST]
# Cập nhật trạng thái lịch khám (admin có thể override mọi trạng thái)
@web_admin_bp.route('/appointments/update/<int:lk_id>', methods=['POST'])
@login_required('admin')
def update_appointment(lk_id):
    conn = get_db()
    conn.execute("UPDATE lich_kham SET trang_thai=? WHERE id=?", (request.form['trang_thai'], lk_id))
    conn.commit(); conn.close()
    flash('Cập nhật thành công!', 'success')
    return redirect(url_for('web_admin.appointments'))


# ── THỐNG KÊ DOANH THU ──────────────────────────────────────────
# URL: /admin/revenue
# Hiển thị: biểu đồ Chart.js, bảng hóa đơn, bộ lọc nâng cao, xuất CSV
@web_admin_bp.route('/revenue')
@login_required('admin')
def revenue():
    conn = get_db()

    # ── Đọc tham số bộ lọc từ URL query string ──────────────────
    # VD: /admin/revenue?trang_thai=da_thanh_toan&tu_ngay=2025-01-01
    f_status      = request.args.get('trang_thai', '')       # da_thanh_toan | cho_thanh_toan | da_huy | ''
    f_tu_ngay     = request.args.get('tu_ngay', '')          # Ngày khám từ (YYYY-MM-DD)
    f_den_ngay    = request.args.get('den_ngay', '')          # Ngày khám đến (YYYY-MM-DD)
    f_bac_si      = request.args.get('bac_si_id', '')         # ID bác sĩ
    f_chuyen_khoa = request.args.get('chuyen_khoa_id', '')    # ID chuyên khoa
    f_ten_bn      = request.args.get('ten_bn', '').strip()    # Tìm theo tên bệnh nhân (LIKE)
    f_so_tien_min = request.args.get('so_tien_min', '')       # Số tiền tối thiểu
    f_so_tien_max = request.args.get('so_tien_max', '')       # Số tiền tối đa

    # ── Xây dựng câu WHERE động theo bộ lọc ────────────────────
    where_parts = []
    params = []
    if f_status:
        where_parts.append("hd.trang_thai=?"); params.append(f_status)
    if f_tu_ngay:
        where_parts.append("lk.ngay_kham>=?"); params.append(f_tu_ngay)
    if f_den_ngay:
        where_parts.append("lk.ngay_kham<=?"); params.append(f_den_ngay)
    if f_bac_si:
        where_parts.append("bs.id=?"); params.append(f_bac_si)
    if f_chuyen_khoa:
        where_parts.append("ck.id=?"); params.append(f_chuyen_khoa)
    if f_ten_bn:
        where_parts.append("tkbn.ho_ten LIKE ?"); params.append(f'%{f_ten_bn}%')
    if f_so_tien_min:
        where_parts.append("hd.so_tien>=?"); params.append(int(f_so_tien_min))
    if f_so_tien_max:
        where_parts.append("hd.so_tien<=?"); params.append(int(f_so_tien_max))

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    # Phần JOIN chung, tái sử dụng cho nhiều query
    base_join = """
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id=lk.id
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
    """

    # ── Số liệu tổng quan toàn hệ thống (không bị ảnh hưởng bởi bộ lọc) ──
    # → Hiển thị ở 3 thẻ xanh/cam/xanh dương phía trên trang
    overview = conn.execute("""
        SELECT
            COUNT(*) as tong_hoa_don,
            SUM(CASE WHEN trang_thai='da_thanh_toan' THEN so_tien ELSE 0 END) as tong_doanh_thu,
            SUM(CASE WHEN trang_thai='cho_thanh_toan' THEN so_tien ELSE 0 END) as cho_thanh_toan,
            COUNT(CASE WHEN trang_thai='da_thanh_toan' THEN 1 END) as so_da_thanh_toan,
            COUNT(CASE WHEN trang_thai='cho_thanh_toan' THEN 1 END) as so_cho_tt
        FROM hoa_don
    """).fetchone()

    # ── Tổng kết theo bộ lọc hiện tại ──────────────────────────
    # → Hiển thị trong thanh tổng kết 4 thẻ bên dưới form lọc
    filtered_summary = conn.execute(f"""
        SELECT
            COUNT(*) as so_hoa_don,
            SUM(CASE WHEN hd.trang_thai='da_thanh_toan' THEN hd.so_tien ELSE 0 END) as da_thu,
            SUM(CASE WHEN hd.trang_thai='cho_thanh_toan' THEN hd.so_tien ELSE 0 END) as chua_thu,
            SUM(hd.so_tien) as tong_tat_ca
        {base_join} {where_sql}
    """, params).fetchone()

    # ── Doanh thu theo tháng: dữ liệu cho biểu đồ đường (line chart) ──
    monthly = conn.execute("""
        SELECT strftime('%Y-%m', ngay_thanh_toan) as thang,
               COUNT(*) as so_hoa_don,
               SUM(so_tien) as doanh_thu
        FROM hoa_don WHERE trang_thai='da_thanh_toan' AND ngay_thanh_toan IS NOT NULL
        GROUP BY thang ORDER BY thang DESC LIMIT 12
    """).fetchall()

    # ── Doanh thu theo bác sĩ: dữ liệu cho biểu đồ cột ngang ──
    by_doctor = conn.execute("""
        SELECT tkbs.ho_ten as ten_bs, ck.ten_chuyen_khoa,
               COUNT(hd.id) as so_ca,
               SUM(CASE WHEN hd.trang_thai='da_thanh_toan' THEN hd.so_tien ELSE 0 END) as doanh_thu
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id=lk.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        GROUP BY bs.id ORDER BY doanh_thu DESC
    """).fetchall()

    # ── Doanh thu theo chuyên khoa: dữ liệu cho biểu đồ donut + bar ──
    # Chỉ tính tiền từ hóa đơn 'da_thanh_toan', gom theo chuyên khoa
    by_specialty = conn.execute("""
        SELECT ck.ten_chuyen_khoa,
               COUNT(hd.id) as so_ca,
               SUM(CASE WHEN hd.trang_thai='da_thanh_toan' THEN hd.so_tien ELSE 0 END) as doanh_thu
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id=lk.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        GROUP BY ck.id
        ORDER BY so_ca DESC
    """).fetchall()

    # ── Danh sách hóa đơn theo bộ lọc (tối đa 200 bản ghi) ────
    # → Hiển thị trong bảng hóa đơn có phân trang phía dưới
    invoices = conn.execute(f"""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham,
               tkbn.ho_ten as ten_bn, tkbs.ho_ten as ten_bs,
               ck.ten_chuyen_khoa, ck.id as chuyen_khoa_id, bs.id as bac_si_id_val
        {base_join} {where_sql}
        ORDER BY hd.ngay_tao DESC LIMIT 200
    """, params).fetchall()

    # ── Dữ liệu cho dropdown bộ lọc ────────────────────────────
    all_doctors = conn.execute("""
        SELECT bs.id, tk.ho_ten FROM bac_si bs JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        WHERE tk.trang_thai=1 ORDER BY tk.ho_ten
    """).fetchall()
    all_specialties = conn.execute("SELECT * FROM chuyen_khoa ORDER BY ten_chuyen_khoa").fetchall()

    conn.close()
    return render_template('admin/revenue.html',
        overview=overview, filtered_summary=filtered_summary,
        monthly=monthly, by_doctor=by_doctor, by_specialty=by_specialty,
        invoices=invoices, all_doctors=all_doctors, all_specialties=all_specialties,
        filters=dict(trang_thai=f_status, tu_ngay=f_tu_ngay, den_ngay=f_den_ngay,
                     bac_si_id=f_bac_si, chuyen_khoa_id=f_chuyen_khoa,
                     ten_bn=f_ten_bn, so_tien_min=f_so_tien_min, so_tien_max=f_so_tien_max))
