"""
API công khai v1 — yêu cầu header X-API-Key cho tất cả endpoint.
Swagger UI có tại /api/docs
"""
from flask import Blueprint, request, jsonify
from models.database import get_db
from middleware.auth import require_api_key

api_v1_bp = Blueprint('api_v1', __name__)


@api_v1_bp.route('/info')
@require_api_key
def info():
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
      401:
        description: Thiếu hoặc sai API Key
    """
    return jsonify({'name': 'MediCare API', 'version': '1.0', 'endpoints': [
        'GET /api/v1/info', 'GET /api/v1/specialties',
        'GET /api/v1/doctors', 'GET /api/v1/doctors/<id>',
        'GET /api/v1/booked-slots', 'POST /api/v1/appointments',
        'GET /api/v1/appointments', 'GET /api/v1/appointments/<id>',
        'PUT /api/v1/appointments/<id>/status',
        'GET /api/v1/patients', 'GET /api/v1/patients/<id>',
    ]})


@api_v1_bp.route('/specialties')
@require_api_key
def specialties():
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
      401:
        description: Thiếu hoặc sai API Key
    """
    conn = get_db()
    rows = conn.execute("SELECT * FROM chuyen_khoa ORDER BY ten_chuyen_khoa").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@api_v1_bp.route('/doctors')
@require_api_key
def doctors():
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
    responses:
      200:
        description: Danh sách bác sĩ
      401:
        description: Thiếu hoặc sai API Key
    """
    conn = get_db()
    ck_id = request.args.get('chuyen_khoa_id')
    sql = """
        SELECT bs.id, tk.ho_ten, tk.email, tk.so_dien_thoai,
               bs.bang_cap, bs.kinh_nghiem, bs.phi_kham, ck.ten_chuyen_khoa
        FROM bac_si bs
        JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE tk.trang_thai=1 {extra} ORDER BY tk.ho_ten
    """
    rows = conn.execute(sql.format(extra="AND bs.chuyen_khoa_id=?"), (ck_id,)).fetchall() if ck_id \
           else conn.execute(sql.format(extra="")).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@api_v1_bp.route('/doctors/<int:bs_id>')
@require_api_key
def doctor_detail(bs_id):
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
    responses:
      200:
        description: Thông tin chi tiết bác sĩ
      401:
        description: Thiếu hoặc sai API Key
      404:
        description: Không tìm thấy bác sĩ
    """
    conn = get_db()
    row = conn.execute("""
        SELECT bs.id, tk.ho_ten, tk.email, tk.so_dien_thoai,
               bs.bang_cap, bs.kinh_nghiem, bs.phi_kham, bs.mo_ta, ck.ten_chuyen_khoa
        FROM bac_si bs JOIN tai_khoan tk ON bs.tai_khoan_id=tk.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE bs.id=? AND tk.trang_thai=1
    """, (bs_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Không tìm thấy bác sĩ'}), 404
    return jsonify(dict(row))


@api_v1_bp.route('/booked-slots')
@require_api_key
def booked_slots():
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
      - name: ngay_kham
        in: query
        type: string
        required: true
        example: "2026-04-15"
    responses:
      200:
        description: Danh sách giờ đã đặt
      400:
        description: Thiếu tham số
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


@api_v1_bp.route('/appointments', methods=['GET'])
@require_api_key
def list_appointments():
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
      - name: benh_nhan_id
        in: query
        type: integer
        required: false
      - name: trang_thai
        in: query
        type: string
        required: false
        example: cho_xac_nhan
      - name: ngay_kham
        in: query
        type: string
        required: false
        example: "2026-04-15"
    responses:
      200:
        description: Danh sách lịch khám
      401:
        description: Thiếu hoặc sai API Key
    """
    conn = get_db()
    filters, params = [], []
    for field, col in [('bac_si_id','lk.bac_si_id'),('benh_nhan_id','lk.benh_nhan_id'),
                       ('trang_thai','lk.trang_thai'),('ngay_kham','lk.ngay_kham')]:
        if request.args.get(field):
            filters.append(f"{col}=?"); params.append(request.args[field])
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = conn.execute(f"""
        SELECT lk.id, lk.ngay_kham, lk.gio_kham, lk.trang_thai, lk.phi_kham, lk.ly_do, lk.ghi_chu,
               tkbn.ho_ten as ten_bn, tkbs.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM lich_kham lk
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        {where} ORDER BY lk.ngay_kham DESC, lk.gio_kham DESC
    """, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@api_v1_bp.route('/appointments', methods=['POST'])
@require_api_key
def create_appointment():
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
          required: [benh_nhan_id, bac_si_id, ngay_kham, gio_kham]
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
    for f in ['benh_nhan_id', 'bac_si_id', 'ngay_kham', 'gio_kham']:
        if not data.get(f):
            return jsonify({'error': f'Thiếu trường: {f}'}), 400
    conn = get_db()
    if conn.execute(
        "SELECT id FROM lich_kham WHERE bac_si_id=? AND ngay_kham=? AND gio_kham=? AND trang_thai NOT IN ('da_huy')",
        (data['bac_si_id'], data['ngay_kham'], data['gio_kham'])
    ).fetchone():
        conn.close(); return jsonify({'error': 'Khung giờ này đã được đặt'}), 409
    bs  = conn.execute("SELECT phi_kham FROM bac_si WHERE id=?", (data['bac_si_id'],)).fetchone()
    phi = bs['phi_kham'] if bs else 200000
    conn.execute("INSERT INTO lich_kham (benh_nhan_id, bac_si_id, ngay_kham, gio_kham, ly_do, phi_kham) VALUES (?,?,?,?,?,?)",
                 (data['benh_nhan_id'], data['bac_si_id'], data['ngay_kham'], data['gio_kham'], data.get('ly_do',''), phi))
    conn.commit()
    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({'success': True, 'lich_kham_id': new_id, 'phi_kham': phi}), 201


@api_v1_bp.route('/appointments/<int:lk_id>')
@require_api_key
def appointment_detail(lk_id):
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
    responses:
      200:
        description: Chi tiết lịch khám
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
        JOIN benh_nhan b ON lk.benh_nhan_id=b.id JOIN tai_khoan tkbn ON b.tai_khoan_id=tkbn.id
        JOIN bac_si bs ON lk.bac_si_id=bs.id JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.id=?
    """, (lk_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Không tìm thấy lịch khám'}), 404
    return jsonify(dict(row))


@api_v1_bp.route('/appointments/<int:lk_id>/status', methods=['PUT'])
@require_api_key
def update_appointment_status(lk_id):
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
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [trang_thai]
          properties:
            trang_thai:
              type: string
              example: da_xac_nhan
            ghi_chu:
              type: string
    responses:
      200:
        description: Cập nhật thành công
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
    if not conn.execute("SELECT id FROM lich_kham WHERE id=?", (lk_id,)).fetchone():
        conn.close(); return jsonify({'error': 'Không tìm thấy lịch khám'}), 404
    conn.execute("UPDATE lich_kham SET trang_thai=?, ghi_chu=? WHERE id=?",
                 (data['trang_thai'], data.get('ghi_chu',''), lk_id))
    conn.commit(); conn.close()
    return jsonify({'success': True})


@api_v1_bp.route('/patients')
@require_api_key
def patients():
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
      401:
        description: Thiếu hoặc sai API Key
    """
    conn = get_db()
    rows = conn.execute("""
        SELECT b.id, tk.ho_ten, tk.email, tk.so_dien_thoai, b.ngay_sinh, b.gioi_tinh, b.dia_chi
        FROM benh_nhan b JOIN tai_khoan tk ON b.tai_khoan_id=tk.id
        WHERE tk.trang_thai=1 ORDER BY tk.ho_ten
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@api_v1_bp.route('/patients/<int:bn_id>')
@require_api_key
def patient_detail(bn_id):
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
    responses:
      200:
        description: Thông tin bệnh nhân và lịch sử khám
      401:
        description: Thiếu hoặc sai API Key
      404:
        description: Không tìm thấy bệnh nhân
    """
    conn = get_db()
    bn = conn.execute("""
        SELECT b.id, tk.ho_ten, tk.email, tk.so_dien_thoai, b.ngay_sinh, b.gioi_tinh, b.dia_chi
        FROM benh_nhan b JOIN tai_khoan tk ON b.tai_khoan_id=tk.id WHERE b.id=?
    """, (bn_id,)).fetchone()
    if not bn:
        conn.close(); return jsonify({'error': 'Không tìm thấy bệnh nhân'}), 404
    history = conn.execute("""
        SELECT lk.id, lk.ngay_kham, lk.gio_kham, lk.trang_thai, lk.phi_kham, lk.ly_do,
               tkbs.ho_ten as ten_bs, ck.ten_chuyen_khoa
        FROM lich_kham lk
        JOIN bac_si bs ON lk.bac_si_id=bs.id JOIN tai_khoan tkbs ON bs.tai_khoan_id=tkbs.id
        JOIN chuyen_khoa ck ON bs.chuyen_khoa_id=ck.id
        WHERE lk.benh_nhan_id=? ORDER BY lk.ngay_kham DESC
    """, (bn_id,)).fetchall()
    conn.close()
    return jsonify({'benh_nhan': dict(bn), 'lich_su_kham': [dict(r) for r in history]})
