import os
from functools import wraps
from flask import request, session, redirect, url_for, flash, jsonify

API_KEY = os.environ.get('MEDICARE_API_KEY', 'medicare-api-key-2024')


def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
    return response


def require_api_key(f):
    """Decorator bảo vệ các endpoint API công khai bằng X-API-Key."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if key != API_KEY:
            return jsonify({'error': 'Unauthorized. Thiếu hoặc sai API Key.'}), 401
        return f(*args, **kwargs)
    return decorated


def login_required(role=None):
    """Decorator bảo vệ các route web, kiểm tra session và vai trò."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('web_public.login'))
            if role and session.get('vai_tro') != role:
                flash('Bạn không có quyền truy cập!', 'error')
                return redirect(url_for('web_public.login'))
            return f(*args, **kwargs)
        return decorated
    return decorator
