"""
Các endpoint nội bộ — dùng cho JavaScript phía frontend (không cần API Key).
"""
from flask import Blueprint, request, jsonify
from models.database import get_db

api_internal_bp = Blueprint('api_internal', __name__)


@api_internal_bp.route('/booked-slots')
def booked_slots():
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


@api_internal_bp.route('/doctors-by-specialty/<int:ck_id>')
def doctors_by_specialty(ck_id):
    conn = get_db()
    doctors = conn.execute(
        "SELECT bs.id, tk.ho_ten, bs.phi_kham, bs.kinh_nghiem FROM bac_si bs JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id WHERE bs.chuyen_khoa_id=? AND tk.trang_thai=1",
        (ck_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(d) for d in doctors])
