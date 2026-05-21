from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.database import get_db
from middleware.auth import login_required

# ================================================================
# web_patient.py — Giao diện bệnh nhân
# URL prefix: /patient/...
# Template:   frontend/templates/patient/
# ================================================================

web_patient_bp = Blueprint('web_patient', __name__)


# ── TRANG CHỦ BỆNH NHÂN ─────────────────────────────────────────
# URL: /patient/dashboard
# Hiển thị: lịch khám, hóa đơn, hồ sơ bệnh án của bệnh nhân đang đăng nhập
@web_patient_bp.route('/dashboard')
@login_required('benh_nhan')
def dashboard():
    conn = get_db()
    # Tìm hồ sơ bệnh nhân từ tài khoản đang đăng nhập
    bn = conn.execute("SELECT * FROM benh_nhan WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    today = date.today().isoformat()

    # Toàn bộ lịch khám của bệnh nhân này, kèm tên bác sĩ và chuyên khoa
    appointments = conn.execute("""
        SELECT lk.*, tk.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM lich_kham lk
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.benh_nhan_id=? ORDER BY lk.ngay_kham DESC, lk.gio_kham DESC
    """, (bn['id'],)).fetchall()

    # Toàn bộ hóa đơn của bệnh nhân
    invoices = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, tk.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id=lk.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.benh_nhan_id=? ORDER BY hd.ngay_tao DESC
    """, (bn['id'],)).fetchall()

    # Hồ sơ bệnh án bệnh nhân được bác sĩ lập
    medical_records = conn.execute("""
        SELECT hsba.*, lk.ngay_kham, lk.gio_kham, lk.ly_do, tk.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM ho_so_benh_an hsba
        JOIN lich_kham lk ON hsba.lich_kham_id=lk.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.benh_nhan_id=? ORDER BY hsba.ngay_tao DESC
    """, (bn['id'],)).fetchall()

    conn.close()

    # Phân loại lịch khám theo trạng thái (xử lý trong Python)
    upcoming  = [a for a in appointments if a['ngay_kham'] >= today and a['trang_thai'] not in ('da_huy','hoan_thanh')]
    completed = [a for a in appointments if a['trang_thai'] == 'hoan_thanh']
    cancelled = [a for a in appointments if a['trang_thai'] == 'da_huy']

    return render_template('patient/dashboard.html',
        appointments=appointments, upcoming=upcoming, completed=completed,
        cancelled=cancelled, invoices=invoices, medical_records=medical_records,
        benh_ans=medical_records, today=today)


# ── ĐẶT LỊCH KHÁM ───────────────────────────────────────────────
# URL: /patient/book  [GET/POST]
# GET  → Hiển thị form chọn bác sĩ, ngày, giờ
# POST → Kiểm tra trùng giờ → tạo lịch khám mới
@web_patient_bp.route('/book', methods=['GET', 'POST'])
@login_required('benh_nhan')
def book_appointment():
    conn = get_db()
    if request.method == 'POST':
        bn = conn.execute("SELECT * FROM benh_nhan WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
        bac_si_id = request.form['bac_si_id']
        ngay_kham = request.form['ngay_kham']
        gio_kham  = request.form['gio_kham']
        ly_do     = request.form.get('ly_do', '')

        # Kiểm tra khung giờ đã có người đặt chưa (bỏ qua lịch đã hủy)
        if conn.execute(
            "SELECT id FROM lich_kham WHERE bac_si_id=? AND ngay_kham=? AND gio_kham=? AND trang_thai NOT IN ('da_huy')",
            (bac_si_id, ngay_kham, gio_kham)
        ).fetchone():
            flash('Khung giờ này đã được đặt!', 'error')
        else:
            # Lấy phí khám của bác sĩ để lưu vào lịch
            bs  = conn.execute("SELECT phi_kham FROM bac_si WHERE id=?", (bac_si_id,)).fetchone()
            phi = bs['phi_kham'] if bs else 200000
            conn.execute(
                "INSERT INTO lich_kham (benh_nhan_id, bac_si_id, ngay_kham, gio_kham, ly_do, phi_kham) VALUES (?,?,?,?,?,?)",
                (bn['id'], bac_si_id, ngay_kham, gio_kham, ly_do, phi)
            )
            conn.commit(); conn.close()
            flash('Đặt lịch khám thành công!', 'success')
            return redirect(url_for('web_patient.dashboard'))

    # GET: lấy danh sách chuyên khoa và bác sĩ đang hoạt động để hiển thị form
    specialties = conn.execute("SELECT * FROM chuyen_khoa GROUP BY ten_chuyen_khoa ORDER BY ten_chuyen_khoa").fetchall()
    doctors = conn.execute("""
        SELECT bs.*, tk.ho_ten, ck.ten_chuyen_khoa FROM bac_si bs
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE tk.trang_thai=1 ORDER BY tk.ho_ten
    """).fetchall()
    conn.close()
    return render_template('patient/book_appointment.html', specialties=specialties, doctors=doctors)


# ── HỦY LỊCH KHÁM ───────────────────────────────────────────────
# URL: /patient/cancel/<lk_id>  [POST]
# Chỉ hủy được lịch ở trạng thái 'cho_xac_nhan' hoặc 'da_xac_nhan'
@web_patient_bp.route('/cancel/<int:lk_id>', methods=['POST'])
@login_required('benh_nhan')
def cancel_appointment(lk_id):
    conn = get_db()
    bn = conn.execute("SELECT * FROM benh_nhan WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    lk = conn.execute("SELECT * FROM lich_kham WHERE id=? AND benh_nhan_id=?", (lk_id, bn['id'])).fetchone()
    if lk and lk['trang_thai'] in ('cho_xac_nhan', 'da_xac_nhan'):
        ly_do_huy = request.form.get('ly_do_huy', '')
        conn.execute("UPDATE lich_kham SET trang_thai='da_huy', ly_do_huy=?, nguoi_huy='benh_nhan' WHERE id=?", (ly_do_huy, lk_id))
        conn.commit()
        flash('Đã hủy lịch khám!', 'success')
    conn.close()
    return redirect(url_for('web_patient.dashboard'))


# ── XEM CHI TIẾT HÓA ĐƠN (bệnh nhân) ───────────────────────────
# URL: /patient/invoice/<hd_id>  [GET]
# Chỉ bệnh nhân sở hữu lịch khám mới xem được hóa đơn này
@web_patient_bp.route('/invoice/<int:hd_id>')
@login_required('benh_nhan')
def invoice(hd_id):
    conn = get_db()
    bn = conn.execute("SELECT * FROM benh_nhan WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    hd = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, lk.ly_do, lk.phi_kham,
               tk.ho_ten as ten_bs, ck.ten_chuyen_khoa, tkbn.ho_ten as ten_bn,
               tkkn.ho_ten as ten_bs_xn
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id=lk.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        LEFT JOIN bac_si bsxn ON hd.bac_si_xac_nhan_id=bsxn.id
        LEFT JOIN tai_khoan tkkn ON bsxn.tai_khoan_id=tkkn.id
        WHERE hd.id=? AND lk.benh_nhan_id=?
    """, (hd_id, bn['id'])).fetchone()
    conn.close()
    if not hd:
        flash('Không tìm thấy hóa đơn!', 'error')
        return redirect(url_for('web_patient.dashboard'))
    return render_template('shared/invoice.html', hd=hd, role='benh_nhan')
