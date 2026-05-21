from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.database import get_db
from middleware.auth import login_required

# ================================================================
# web_doctor.py — Giao diện bác sĩ
# URL prefix: /doctor/...
# Template:   frontend/templates/doctor/
# ================================================================

web_doctor_bp = Blueprint('web_doctor', __name__)


# ── TRANG CHỦ BÁC SĨ ────────────────────────────────────────────
# URL: /doctor/dashboard
# Hiển thị: lịch khám, hóa đơn chờ thu, hồ sơ bệnh án của bác sĩ đang đăng nhập
@web_doctor_bp.route('/dashboard')
@login_required('bac_si')
def dashboard():
    conn = get_db()
    # Tìm hồ sơ bác sĩ từ tài khoản đang đăng nhập
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    if not bs:
        conn.close(); return redirect(url_for('web_public.logout'))

    today = date.today().isoformat()

    # Toàn bộ lịch khám của bác sĩ này
    appointments = conn.execute("""
        SELECT lk.*, tkbn.ho_ten as ten_bn, tkbn.email, tkbn.so_dien_thoai
        FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        WHERE lk.bac_si_id=? ORDER BY lk.ngay_kham DESC, lk.gio_kham DESC
    """, (bs['id'],)).fetchall()

    # Phân loại lịch khám theo trạng thái (xử lý trong Python để tránh nhiều query)
    today_count = sum(1 for a in appointments if a['ngay_kham'] == today and a['trang_thai'] != 'da_huy')
    pending  = [a for a in appointments if a['trang_thai'] == 'cho_xac_nhan']   # Chờ bác sĩ xác nhận
    upcoming = [a for a in appointments if a['ngay_kham'] > today and a['trang_thai'] == 'da_xac_nhan']  # Sắp tới

    # Hóa đơn đang chờ bác sĩ xác nhận thanh toán
    invoices_pending = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, tkbn.ho_ten as ten_bn
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id=lk.id
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        WHERE lk.bac_si_id=? AND hd.trang_thai='cho_thanh_toan' ORDER BY hd.ngay_tao DESC
    """, (bs['id'],)).fetchall()

    # Toàn bộ hóa đơn (dùng cho tab "Tất cả hóa đơn")
    all_invoices = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, tkbn.ho_ten as ten_bn
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id=lk.id
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        WHERE lk.bac_si_id=? ORDER BY hd.ngay_tao DESC
    """, (bs['id'],)).fetchall()

    # Hồ sơ bệnh án bác sĩ đã lập
    medical_records = conn.execute("""
        SELECT hsba.*, lk.ngay_kham, lk.gio_kham, lk.ly_do, tkbn.ho_ten as ten_bn
        FROM ho_so_benh_an hsba
        JOIN lich_kham lk ON hsba.lich_kham_id=lk.id
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        WHERE lk.bac_si_id=? ORDER BY hsba.ngay_tao DESC
    """, (bs['id'],)).fetchall()

    conn.close()
    return render_template('doctor/dashboard.html', bs=bs,
        appointments=appointments, today_count=today_count, pending=pending, upcoming=upcoming,
        invoices_pending=invoices_pending, all_invoices=all_invoices, benh_ans=medical_records)


# ── XÁC NHẬN / HỦY / HOÀN THÀNH LỊCH KHÁM ─────────────────────
# URL: /doctor/confirm/<lk_id>  [POST]
# action=confirm  → xác nhận lịch (cho_xac_nhan → da_xac_nhan)
# action=reject   → từ chối lịch (→ da_huy)
# action=complete → hoàn thành khám (→ hoan_thanh)
@web_doctor_bp.route('/confirm/<int:lk_id>', methods=['POST'])
@login_required('bac_si')
def confirm_appointment(lk_id):
    conn = get_db()
    bs     = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    action = request.form.get('action')
    note   = request.form.get('ghi_chu', '')
    ly_do_huy = request.form.get('ly_do_huy', '')
    if action == 'confirm':
        conn.execute("UPDATE lich_kham SET trang_thai='da_xac_nhan', ghi_chu=? WHERE id=? AND bac_si_id=?", (note, lk_id, bs['id']))
    elif action == 'reject':
        conn.execute("UPDATE lich_kham SET trang_thai='da_huy', ghi_chu=?, ly_do_huy=?, nguoi_huy='bac_si' WHERE id=? AND bac_si_id=?", (note, ly_do_huy, lk_id, bs['id']))
    elif action == 'complete':
        conn.execute("UPDATE lich_kham SET trang_thai='hoan_thanh' WHERE id=? AND bac_si_id=?", (lk_id, bs['id']))
    conn.commit(); conn.close()
    flash('Cập nhật thành công!', 'success')
    return redirect(url_for('web_doctor.dashboard'))


# ── LẬP / CẬP NHẬT HỒ SƠ BỆNH ÁN ──────────────────────────────
# URL: /doctor/medical-record/<lk_id>  [GET/POST]
# GET  → Hiển thị form nhập bệnh án
# POST → Lưu bệnh án + đổi lịch khám thành 'hoan_thanh' + tạo hóa đơn 'cho_thanh_toan'
@web_doctor_bp.route('/medical-record/<int:lk_id>', methods=['GET', 'POST'])
@login_required('bac_si')
def medical_record(lk_id):
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    lk = conn.execute("""
        SELECT lk.*, tkbn.ho_ten as ten_bn FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        WHERE lk.id=? AND lk.bac_si_id=?
    """, (lk_id, bs['id'])).fetchone()
    if not lk:
        conn.close(); flash('Không tìm thấy lịch khám!', 'error')
        return redirect(url_for('web_doctor.dashboard'))
    if request.method == 'POST':
        fields = (request.form['trieu_chung'], request.form['chan_doan'],
                  request.form['huong_dieu_tri'], request.form['don_thuoc'],
                  request.form.get('ghi_chu_them', ''))
        # Nếu đã có bệnh án → cập nhật; chưa có → tạo mới
        if conn.execute("SELECT id FROM ho_so_benh_an WHERE lich_kham_id=?", (lk_id,)).fetchone():
            conn.execute("UPDATE ho_so_benh_an SET trieu_chung=?, chan_doan=?, huong_dieu_tri=?, don_thuoc=?, ghi_chu_them=? WHERE lich_kham_id=?",
                         (*fields, lk_id))
        else:
            conn.execute("INSERT INTO ho_so_benh_an (lich_kham_id, trieu_chung, chan_doan, huong_dieu_tri, don_thuoc, ghi_chu_them) VALUES (?,?,?,?,?,?)",
                         (lk_id, *fields))
        # Đổi trạng thái lịch khám thành hoàn thành
        conn.execute("UPDATE lich_kham SET trang_thai='hoan_thanh' WHERE id=?", (lk_id,))
        # Tạo hóa đơn nếu chưa có (mặc định: chờ thanh toán)
        if not conn.execute("SELECT id FROM hoa_don WHERE lich_kham_id=?", (lk_id,)).fetchone():
            conn.execute("INSERT INTO hoa_don (lich_kham_id, so_tien, trang_thai) VALUES (?,?,?)",
                         (lk_id, lk['phi_kham'], 'cho_thanh_toan'))
        conn.commit(); conn.close()
        flash('Đã lưu bệnh án và tạo hóa đơn!', 'success')
        return redirect(url_for('web_doctor.dashboard'))
    existing_record = conn.execute("SELECT * FROM ho_so_benh_an WHERE lich_kham_id=?", (lk_id,)).fetchone()
    conn.close()
    return render_template('doctor/medical_record.html', lk=lk, existing_record=existing_record)


# ── XEM CHI TIẾT HÓA ĐƠN (bác sĩ) ─────────────────────────────
# URL: /doctor/invoice/<hd_id>  [GET]
# Chỉ bác sĩ sở hữu lịch khám mới xem được hóa đơn này
@web_doctor_bp.route('/invoice/<int:hd_id>')
@login_required('bac_si')
def invoice_detail(hd_id):
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    hd = conn.execute("""
        SELECT hd.*, lk.ngay_kham, lk.gio_kham, lk.ly_do, lk.phi_kham,
               tk.ho_ten as ten_bs, ck.ten_chuyen_khoa, tkbn.ho_ten as ten_bn, tkkn.ho_ten as ten_bs_xn
        FROM hoa_don hd
        JOIN lich_kham lk ON hd.lich_kham_id=lk.id
        JOIN bac_si bslk ON lk.bac_si_id=bslk.id
        JOIN tai_khoan tk ON bslk.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bslk.chuyen_khoa_id=ck.id
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id
        JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        LEFT JOIN bac_si bsxn ON hd.bac_si_xac_nhan_id=bsxn.id
        LEFT JOIN tai_khoan tkkn ON bsxn.tai_khoan_id=tkkn.id
        WHERE hd.id=? AND lk.bac_si_id=?
    """, (hd_id, bs['id'])).fetchone()
    conn.close()
    if not hd:
        flash('Không tìm thấy hóa đơn!', 'error'); return redirect(url_for('web_doctor.dashboard'))
    return render_template('shared/invoice.html', hd=hd, role='bac_si')


# ── XÁC NHẬN THANH TOÁN HÓA ĐƠN ────────────────────────────────
# URL: /doctor/invoice/confirm/<hd_id>  [POST]
# Bác sĩ xác nhận bệnh nhân đã thanh toán → đổi trạng thái thành 'da_thanh_toan'
@web_doctor_bp.route('/invoice/confirm/<int:hd_id>', methods=['POST'])
@login_required('bac_si')
def confirm_payment(hd_id):
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    hd = conn.execute("SELECT hd.* FROM hoa_don hd JOIN lich_kham lk ON hd.lich_kham_id=lk.id WHERE hd.id=? AND lk.bac_si_id=?", (hd_id, bs['id'])).fetchone()
    if not hd:
        conn.close(); flash('Không có quyền xác nhận!', 'error'); return redirect(url_for('web_doctor.dashboard'))
    # Ghi nhận: hình thức thanh toán, ghi chú, thời điểm và bác sĩ xác nhận
    conn.execute("UPDATE hoa_don SET trang_thai='da_thanh_toan', phuong_thuc_thanh_toan=?, ghi_chu=?, ngay_thanh_toan=?, bac_si_xac_nhan_id=? WHERE id=?",
                 (request.form.get('phuong_thuc_thanh_toan','tien_mat'), request.form.get('ghi_chu',''),
                  datetime.now().strftime('%Y-%m-%d %H:%M'), bs['id'], hd_id))
    conn.commit(); conn.close()
    flash('Đã xác nhận thanh toán!', 'success')
    return redirect(url_for('web_doctor.dashboard'))


# ── HỦY HÓA ĐƠN ────────────────────────────────────────────────
# URL: /doctor/invoice/cancel/<hd_id>  [POST]
# Bác sĩ hủy hóa đơn → đổi trạng thái thành 'da_huy'
@web_doctor_bp.route('/invoice/cancel/<int:hd_id>', methods=['POST'])
@login_required('bac_si')
def cancel_invoice(hd_id):
    conn = get_db()
    bs = conn.execute("SELECT * FROM bac_si WHERE tai_khoan_id=?", (session['user_id'],)).fetchone()
    hd = conn.execute("SELECT hd.* FROM hoa_don hd JOIN lich_kham lk ON hd.lich_kham_id=lk.id WHERE hd.id=? AND lk.bac_si_id=?", (hd_id, bs['id'])).fetchone()
    if not hd:
        conn.close(); flash('Không có quyền hủy!', 'error'); return redirect(url_for('web_doctor.dashboard'))
    conn.execute("UPDATE hoa_don SET trang_thai='da_huy' WHERE id=?", (hd_id,))
    conn.commit(); conn.close()
    flash('Đã hủy hóa đơn!', 'success')
    return redirect(url_for('web_doctor.dashboard'))
