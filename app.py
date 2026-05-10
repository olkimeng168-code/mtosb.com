import os
import json
import base64
import io
import re
import uuid
from datetime import datetime, time # បន្ថែម time សម្រាប់ឆែកម៉ោងបើកបិទប្រព័ន្ធ
import pytz
from dateutil.relativedelta import relativedelta

from flask import Flask
from ocr_matching import ocr_sync_bp # ១. ទាញយក Blueprint ដែលទើបបង្កើត
app = Flask(__name__)
# ២. ចុះឈ្មោះ Blueprint ចូលក្នុងប្រព័ន្ធ EPS Smart Exam
app.register_blueprint(ocr_sync_bp)

from datetime import datetime, date
import pytz # <--- បន្ថែមបន្ទាត់នេះ

import pandas as pd 
import numpy as np
import cv2
from PIL import Image
# ==========================================
# 🌟 Smart Cross-Platform Face Recognition
# ==========================================
import sys
from unittest.mock import MagicMock

# បង្កើត Module ក្លែងក្លាយក្នុង System Memory តែម្តង
mock_face = MagicMock()
sys.modules["face_recognition"] = mock_face
sys.modules["face_recognition_models"] = mock_face
face_recognition = mock_face

print("🚫 បិទ Face Recognition ជាបណ្តោះអាសន្ន ដើម្បី Debug រក Error ផ្សេង...")

# 💡 ថែមជួរនេះមកវិញ ដើម្បីឱ្យកូដស្គាល់ mysql.connector.Error
import mysql.connector

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

# --- Import Limiter នៅទីនេះ ---
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 💡 ១. Import DB Connection ពី File ថ្មី (db_config.py)
from db_config import get_db_connection

# --- ២. បង្កើត App និងកំណត់ទម្រង់កូដ (Setup) ---
app = Flask(__name__)
app.secret_key = '0a03d8cb318f0228cc8dd3abbd00371aec0df9a8e1c66bdd'
bcrypt = Bcrypt(app) 

# --- ៣. ការកំណត់ Session និង Security សម្រាប់ទូរសព្ទដៃ ---
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',  # បង្ការបញ្ហា Session បាត់ពេល Submit លើ Mobile
    SESSION_COOKIE_SECURE=False,   # ដាក់ False បើតេស្តលើ Local/HTTP (បើប្រើ HTTPS ត្រូវដាក់ True)
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=3600 # ទុក Session ឱ្យនៅរស់បាន ១ម៉ោង
)

# កំណត់ទំហំ File រូបភាពឱ្យឡើងដល់ 16MB (ការពារការ Submit មិនទៅពេលរូបថតទូរសព្ទធំពេក)

# 💡 កំណត់ទំហំ Upload ត្រឹម 50MB (Megabytes)
# រូបមន្ត: ទំហំគិតជា MB * 1024 (ទៅជា KB) * 1024 (ទៅជា Bytes)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# ១. បង្កើតអថេរ limiter ជាមុន (កំណត់លេខឱ្យធំទូលាយសម្រាប់អ្នកប្រើទូទៅ)
limiter = Limiter(
    key_func=get_remote_address,
    # អនុញ្ញាត: ១ម៉ឺនដង/ថ្ងៃ | ២ពាន់ដង/ម៉ោង | ៦០ដង/នាទី
    default_limits=["10000 per day", "2000 per hour", "60 per minute"] 
)

# ២. បន្ទាប់មក ប្រើមុខងារ init_app ដើម្បីភ្ជាប់វាទៅនឹងកម្មវិធី Flask របស់អ្នក
limiter.init_app(app)

from flask import flash, redirect, request
from werkzeug.exceptions import RequestEntityTooLarge

# 💡 កូដចាប់យក Error 413 (ពេល File ធំពេក)
@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_file_size_error(e):
    # បង្ហាញសារប្រាប់អ្នកប្រើប្រាស់
    flash('សុំទោស! ឯកសារនេះធំពេកហើយ។ សូមជ្រើសរើសវីដេអូ ឬរូបភាពដែលមានទំហំតូចជាង ៥០ មេកាបៃ (50MB)។', 'danger')
    
    # បញ្ជូនគាត់ត្រឡប់ទៅទំព័រដែលគាត់ទើបតែ Upload វិញ
    # (ការពារកុំឱ្យគាត់ជាប់គាំងនៅលើទំព័រ Error)
    return redirect(request.url)

# --- ៤. កំណត់ទីតាំង Folder និងបង្កើត Folder ជាស្វ័យប្រវត្តិ ---
app.config['UPLOAD_FOLDER'] = 'static/uploads/excel'
app.config['PHOTO_FOLDER'] = 'static/uploads/reference_photos'
app.config['UPLOAD_FOLDER_APPS'] = 'static/uploads/apps' # សម្រាប់ឯកសារបេក្ខជន
app.config['LATEST_SCANS_FOLDER'] = 'static/latest_scans'

# បង្កើត Folder បើមិនទាន់មាន
for folder in [app.config['UPLOAD_FOLDER'], app.config['PHOTO_FOLDER'], 
               app.config['UPLOAD_FOLDER_APPS'], app.config['LATEST_SCANS_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# --- ៥. DEBUGGING PATH (សម្រាប់ឆែកមើល Folder templates) ---
print("--- DEBUGGING PATH ---")
template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
print("Searching for templates in:", template_path)
if os.path.exists(template_path):
    print("Files found in templates:", os.listdir(template_path))
print("----------------------")

# --- ៦. Function ជំនួយសម្រាប់ទិន្នន័យលេខ ---
def clean_int(val):
    if val is None: return 0
    val = str(val).strip()
    if val and val.isdigit():
        return int(val)
    return 0

# --- ៧. Route ផ្សេងៗ (Login, Form, Submit) ត្រូវដាក់នៅខាងក្រោមនេះ ---

#@app.route('/')
#def index():
#    return "ប្រព័ន្ធដំណើរការធម្មតា!"

# (បញ្ចូល Route ផ្សេងៗទៀតរបស់បងនៅទីនេះ បើមាន...)

# --- ៨. ការចុះឈ្មោះ Blueprint (Register Blueprints) ---
# 💡 ចុះឈ្មោះ Blueprint របស់ Queue System (និង Blueprint ផ្សេងៗបើបងមាន)
from routes.queue_tickets import queue_bp
app.register_blueprint(queue_bp)

# ឧទាហរណ៍បើបងមាន Blueprint ផ្សេងទៀត ក៏ត្រូវដាក់នៅទីនេះដែរ៖
# from routes.admin_routes import admin_bp
# app.register_blueprint(admin_bp)

# ========================================================
# ១. Route សម្រាប់ Login ចូលប្រព័ន្ធ
# ========================================================
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    # ១. ប្រសិនបើមាន Session រួចហើយ ឱ្យទៅ Dashboard តែម្តង
    if session.get('loggedin'):
        # 💡 បើគណនីជា 'Application Receiver' បោះទៅកាន់បញ្ជរតែម្តង
        if session.get('role_name') == 'Application Receiver':
            return redirect(url_for('queue.counter_dashboard'))
        return redirect(url_for('dashboard')) 

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # ប្រើ LEFT JOIN ដើម្បីទាញយកឈ្មោះ role មកជាមួយ
            cursor.execute('''
                SELECT u.*, r.name AS role_name 
                FROM users u 
                LEFT JOIN roles r ON u.role_id = r.role_id 
                WHERE u.username = %s
            ''', (username,))
            account = cursor.fetchone()
        except Exception as e:
            print(f"Database Error during login: {e}")
            account = None

        # ២. ផ្ទៀងផ្ទាត់ Password និងគណនី
        if account:
            try:
                is_password_correct = bcrypt.check_password_hash(account['password_hash'], password)
            except ValueError:
                # ការពារ Error: Invalid Salt ករណី Password មិនមែនជា Hash
                is_password_correct = False
        else:
            is_password_correct = False

        if account and is_password_correct:
            
            # ឆែកមើលថាតើគណនីត្រូវបាន Admin បិទ (Inactive) ដែរឬទេ
            if not account['is_active']:
                flash('គណនីរបស់អ្នកត្រូវបានផ្អាក! សូមទាក់ទង Admin។', 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('login'))

            # 💡 ធ្វើបច្ចុប្បន្នភាពម៉ោងចូលប្រព័ន្ធ (Update last_login) ទៅក្នុង Database
            try:
                cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (account['id'],))
                conn.commit()
            except Exception as e:
                print(f"Error updating last login: {e}")

            cursor.close()
            conn.close()

            # ៣. បង្កើត Session ឱ្យបានត្រឹមត្រូវ
            session.clear() # សម្អាតទិន្នន័យចាស់ៗចេញការពារបញ្ហាសុវត្ថិភាព
            session.permanent = True # កំណត់ឱ្យ Session នៅជាប់
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['full_name'] = account['full_name']
            session['role_id'] = account['role_id'] 
            
            # រក្សាទុកទាំងពីរឈ្មោះ ការពារក្រែងលោត Error នៅ HTML ផ្សេងៗ
            session['role_name'] = account['role_name'] 
            session['role'] = account['role_name']      
            
            # 💡 ផ្ទុករូបថត Profile សម្រាប់បង្ហាញលើ Header
            session['profile_image'] = account['profile_image'] 
            
            flash(f'ស្វាគមន៍មកកាន់ប្រព័ន្ធ, {account["full_name"]}!', 'success')
            
            # បង្វែរទិសទៅតាមតួនាទី
            if session.get('role_name') == 'Application Receiver':
                return redirect(url_for('queue.counter_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            cursor.close()
            conn.close()
            flash('ឈ្មោះគណនី ឬលេខសម្ងាត់មិនត្រឹមត្រូវទេ!', 'danger')
            return redirect(url_for('login')) 

    # ៤. ប្រសិនបើជា GET (បើកមើលទំព័រដំបូង) ត្រូវបង្ហាញ File login.html
    return render_template('login.html')


# ==========================================
# ផ្ទាំងព័ត៌មានគណនីផ្ទាល់ខ្លួន (My Profile)
# ==========================================
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    user_id = session['id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        full_name = request.form.get('full_name').strip()
        gender = request.form.get('gender')
        phone_number = request.form.get('phone_number').strip()
        email = request.form.get('email').strip()
        telegram_username = request.form.get('telegram_username').strip()
        password = request.form.get('password').strip()

        # 💡 ការរៀបចំ Upload រូបថត Profile
        profile_image_name = None
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                profile_image_name = f"{session['username']}_{filename}"
                upload_folder = os.path.join('static', 'uploads', 'profiles')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, profile_image_name))

        # រៀបចំ SQL Update
        update_fields = ["full_name=%s", "gender=%s", "phone_number=%s", "email=%s", "telegram_username=%s"]
        params = [full_name, gender, phone_number, email, telegram_username]

        if password: # បើគាត់វាយលេខសម្ងាត់ថ្មី ទើបដូរ
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            update_fields.append("password_hash=%s")
            params.append(hashed_pw)

        if profile_image_name: # បើគាត់ជ្រើសរើសរូបថ្មី ទើបដូរ
            update_fields.append("profile_image=%s")
            params.append(profile_image_name)
            # 💡 Update Session ដើម្បីឱ្យ Header លោតរូបថ្មីភ្លាមៗដោយមិនបាច់ Login ឡើងវិញ
            session['profile_image'] = profile_image_name 

        params.append(user_id)
        sql = f"UPDATE users SET {', '.join(update_fields)} WHERE id=%s"

        try:
            cursor.execute(sql, tuple(params))
            conn.commit()
            
            # 💡 Update ឈ្មោះក្នុង Session ក្រែងលោតគាត់ប្តូរឈ្មោះពិត
            session['full_name'] = full_name 
            
            flash('ព័ត៌មានគណនីរបស់អ្នកត្រូវបានកែប្រែជោគជ័យ!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'មានបញ្ហា: {str(e)}', 'danger')

        return redirect(url_for('profile'))

    # ពេលបើកទំព័រដំបូង (GET Request) ទាញទិន្នន័យគាត់មកបង្ហាញ
    cursor.execute("""
        SELECT u.*, r.name AS role_name 
        FROM users u 
        LEFT JOIN roles r ON u.role_id = r.role_id 
        WHERE u.id = %s
    """, (user_id,))
    user_data = cursor.fetchone()
    
    cursor.close()
    conn.close()

    return render_template('profile.html', user=user_data)


# ========================================================
# ២. Route សម្រាប់ប្តូរវគ្គប្រឡង (Active Session)
# ========================================================
@app.route('/set_active_session', methods=['POST'])
def set_active_session():
    new_session = request.form.get('session_code')
    session['active_session'] = new_session
    # 💡 ថែមសារជូនដំណឹងប្រាប់ User ថាគាត់បានប្តូរវគ្គជោគជ័យ
    flash(f'បានប្តូរទៅកាន់វគ្គ: {new_session}', 'success') 
    return redirect(request.referrer or url_for('dashboard'))

from datetime import datetime

# 💡 Function គណនាម៉ោង (ឧទាហរណ៍៖ "២ នាទីមុន", "១ ម៉ោងមុន")
def time_ago(time):
    if not time: return ""
    now = datetime.now()
    diff = now - time
    seconds = diff.total_seconds()
    if seconds < 60: return "អម្បាញ់មិញ"
    elif seconds < 3600: return f"{int(seconds // 60)} នាទីមុន"
    elif seconds < 86400: return f"{int(seconds // 3600)} ម៉ោងមុន"
    else: return f"{int(seconds // 86400)} ថ្ងៃមុន"

@app.route('/read_all_notifications', methods=['POST'])
def read_all_notifications():
    if 'loggedin' in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (session['id'],))
        conn.commit()
        cursor.close()
        conn.close()
    # ត្រឡប់ទៅទំព័រដើមវិញដោយស្ងាត់ៗ
    return redirect(request.referrer or url_for('dashboard'))    

from flask import jsonify

# ==============================================================
# API សម្រាប់ Auto-Refresh Notification (Real-time)
# ==============================================================
@app.route('/api/notifications', methods=['GET'])
def api_get_notifications():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # ទាញយកសារមិនទាន់អាន ៥ ថ្មីៗ
        cursor.execute("""
            SELECT * FROM notifications 
            WHERE user_id = %s AND is_read = 0 
            ORDER BY created_at DESC LIMIT 5
        """, (session['id'],))
        notifs = cursor.fetchall()
        
        # រាប់ចំនួនសារសរុប
        cursor.execute("SELECT COUNT(*) as total FROM notifications WHERE user_id = %s AND is_read = 0", (session['id'],))
        total_count = cursor.fetchone()['total']
        
        # រៀបចំទិន្នន័យ (Format ពណ៌ និង Icon) ឱ្យស្រេច ដើម្បីឱ្យ JS ស្រួលប្រើ
        for n in notifs:
            n['time_str'] = time_ago(n['created_at']) # ប្រើ Function time_ago ដែលមានស្រាប់
            n['color'] = 'primary' if n['type'] == 'info' else ('success' if n['type'] == 'success' else ('warning' if n['type'] == 'warning' else 'danger'))
            n['icon'] = 'info-circle' if n['type'] == 'info' else ('check-circle' if n['type'] == 'success' else ('exclamation-triangle' if n['type'] == 'warning' else 'times-circle'))

        return jsonify({
            'status': 'success',
            'unread_count': total_count,
            'notifications': notifs
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# 💡 Context Processor: ដំណើរការគ្រប់ទំព័រទាំងអស់ដើម្បីទាញ Notification មកបង្ហាញលើ Header
@app.context_processor
def inject_notifications():
    if 'loggedin' not in session:
        return dict(unread_notifications=[], unread_count=0)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # ទាញយកសារដែលមិនទាន់អានចំនួន ៥ ថ្មីៗបំផុត
        cursor.execute("""
            SELECT * FROM notifications 
            WHERE user_id = %s AND is_read = 0 
            ORDER BY created_at DESC LIMIT 5
        """, (session['id'],))
        notifs = cursor.fetchall()
        
        # ទាញយកចំនួនសារមិនទាន់អានសរុប (សម្រាប់លោតលេខក្រហម)
        cursor.execute("SELECT COUNT(*) as total FROM notifications WHERE user_id = %s AND is_read = 0", (session['id'],))
        total_count = cursor.fetchone()['total']
        
        # Format ម៉ោងសម្រាប់សារនីមួយៗ
        for n in notifs:
            n['time_str'] = time_ago(n['created_at'])

    except Exception as e:
        print(f"Notification Error: {e}")
        notifs = []
        total_count = 0
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return dict(unread_notifications=notifs, unread_count=total_count)


# ========================================================
# ៣. Context Processor (បញ្ជូនអថេរទៅគ្រប់ HTML ដោយស្វ័យប្រវត្តិ)
# ========================================================
@app.context_processor
def inject_global_variables():
    # 💡 កន្លែងនេះមិនគួរដាក់ Default ថា 'Admin' ឬ 'System Admin' ទេ
    # ព្រោះបើកុំព្យូទ័រនោះអត់ទាន់ Login វាអាចនឹងលោតឈ្មោះ Admin ច្រឡំគេបាន។ គួរទុកវាទទេបើអត់ទាន់ Login។
    return dict(
        active_session=session.get('active_session', ''),
        full_name=session.get('full_name', ''),
        role_name=session.get('role_name', '') 
    )

@app.route('/dashboard')
def dashboard():
    # ១. ការពារការ Login ឱ្យកាន់តែរឹងមាំ
    if not session.get('loggedin'):
        return redirect(url_for('login'))
    
    # ២. បង្វែរទិសមន្ត្រីទទួលពាក្យ (Application Receiver) ទៅកាន់ផ្ទាំងបញ្ជរតែម្តង
    if session.get('role_name') == 'Application Receiver':
        # ប្រសិនបើ Counter Dashboard របស់បងស្ថិតក្នុង Blueprint ឈ្មោះ 'queue'
        return redirect(url_for('queue.counter_dashboard')) 

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # កំណត់តម្លៃដើម (Default Values) ការពារ Error ពេលអត់ទិន្នន័យ
    all_sessions = []
    current_session = session.get('active_session', '')
    active_counters = []
    pending_count = total_candidates = total_female = absent_count = absent_female = 0
    skill_total = skill_female = skill_present = skill_present_f = skill_absent = skill_absent_f = 0
    
    try:
        # ទាញយកបញ្ជីវគ្គប្រឡងទាំងអស់
        cursor.execute("SELECT * FROM sessions ORDER BY session_code DESC")
        all_sessions = cursor.fetchall()
        
        # ==========================================
        # ទាញយកបញ្ជរដែលកំពុងដំណើរការ (Active Counters) គ្រប់ពេល
        # ==========================================
        cursor.execute("""
            SELECT c.counter_name_kh, c.status, u.full_name, u.username 
            FROM counters c
            LEFT JOIN users u ON c.current_user_id = u.id
            WHERE c.status IN ('Active', 'Paused')
            ORDER BY c.id ASC
        """)
        active_counters = cursor.fetchall()

        if current_session:
            # ==========================================
            # ១. ទិន្នន័យស្ថិតិរួម (UBT ដើម)
            # ==========================================
            cursor.execute("""
                SELECT COALESCE(COUNT(cr.id), 0) as pending_count 
                FROM change_requests cr
                JOIN candidates c ON cr.application_no = c.application_no
                WHERE cr.status = 'Pending' AND c.session_code = %s
            """, (current_session,))
            result_pending = cursor.fetchone()
            if result_pending:
                pending_count = result_pending['pending_count']
            
            cursor.execute("""
                SELECT 
                    COALESCE(COUNT(*), 0) as total, 
                    COALESCE(SUM(CASE WHEN gender IN ('F', 'Female', 'ស្រី') THEN 1 ELSE 0 END), 0) as total_f 
                FROM candidates WHERE session_code = %s
            """, (current_session,))
            t_data = cursor.fetchone()
            if t_data:
                total_candidates = t_data['total']
                total_female = t_data['total_f']
                
            cursor.execute("""
                SELECT 
                    COALESCE(COUNT(*), 0) as absent_total, 
                    COALESCE(SUM(CASE WHEN gender IN ('F', 'Female', 'ស្រី') THEN 1 ELSE 0 END), 0) as absent_f 
                FROM candidates WHERE is_present = 0 AND session_code = %s
            """, (current_session,))
            a_data = cursor.fetchone()
            if a_data:
                absent_count = a_data['absent_total']
                absent_female = a_data['absent_f']

            # ==========================================
            # ២. ទិន្នន័យស្ថិតិតេស្តជំនាញ (Skill Test)
            # ==========================================
            cursor.execute("""
                SELECT 
                    COALESCE(COUNT(stc.id), 0) as total, 
                    COALESCE(SUM(CASE WHEN stc.gender IN ('F', 'Female', 'ស្រី') THEN 1 ELSE 0 END), 0) as total_f,
                    COALESCE(SUM(CASE WHEN stc.is_present = TRUE THEN 1 ELSE 0 END), 0) as p_total,
                    COALESCE(SUM(CASE WHEN stc.is_present = TRUE AND stc.gender IN ('F', 'Female', 'ស្រី') THEN 1 ELSE 0 END), 0) as p_f,
                    COALESCE(SUM(CASE WHEN stc.is_present = 0 THEN 1 ELSE 0 END), 0) as a_total,
                    COALESCE(SUM(CASE WHEN stc.is_present = 0 AND stc.gender IN ('F', 'Female', 'ស្រី') THEN 1 ELSE 0 END), 0) as a_f
                FROM skill_test_candidates stc
                JOIN candidates c ON stc.application_no = c.application_no
                WHERE c.session_code = %s
            """, (current_session,))
            
            s_data = cursor.fetchone()
            if s_data:
                skill_total = s_data['total']
                skill_female = s_data['total_f']
                skill_present = s_data['p_total']
                skill_present_f = s_data['p_f']
                skill_absent = s_data['a_total']
                skill_absent_f = s_data['a_f']
                
    except Exception as e:
        print(f"Error in dashboard route: {str(e)}")
        flash('មានបញ្ហាក្នុងការទាញយកទិន្នន័យស្ថិតិ។', 'danger')
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
    
    # ៣. បញ្ជូនទិន្នន័យទាំងអស់ទៅកាន់ HTML
    return render_template('dashboard.html', 
                           all_sessions=all_sessions, 
                           active_session=current_session,
                           total_candidates=total_candidates, 
                           total_female=total_female,
                           pending_count=pending_count, 
                           absent_count=absent_count, 
                           absent_female=absent_female,
                           skill_total=skill_total, 
                           skill_female=skill_female,
                           skill_present=skill_present, 
                           skill_present_f=skill_present_f,
                           skill_absent=skill_absent, 
                           skill_absent_f=skill_absent_f,
                           active_counters=active_counters, # 👈 បញ្ជូនបញ្ជរដែលកំពុង Active
                           full_name=session.get('full_name', 'User'), 
                           role_name=session.get('role_name', 'No Role'))

@app.route('/sessions', methods=['GET', 'POST'])
def manage_sessions():
    if 'loggedin' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        session_code = request.form['session_code'].strip()
        session_type_en = request.form['session_type_en'].strip()
        session_type_kh = request.form['session_type_kh'].strip()
        title_en = request.form.get('title_en', '').strip() # 💡 ថ្មី
        title_kh = request.form.get('title_kh', '').strip() # 💡 ថ្មី

        try:
            cursor.execute("""
                INSERT INTO sessions (session_code, session_type_en, session_type_kh, title_en, title_kh) 
                VALUES (%s, %s, %s, %s, %s)
            """, (session_code, session_type_en, session_type_kh, title_en, title_kh))
            conn.commit()
            flash('បង្កើតវគ្គប្រឡងថ្មីបានជោគជ័យ!', 'success')
        except mysql.connector.Error as err:
            if err.errno == 1062: flash('លេខកូដវគ្គនេះមានរួចហើយ!', 'danger')
            else: flash(f'មានបញ្ហា: {str(err)}', 'danger')

    cursor.execute("SELECT * FROM sessions ORDER BY session_code DESC")
    sessions_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('sessions.html', sessions=sessions_list, full_name=session['full_name'])
# មុខងារសម្រាប់កែប្រែវគ្គប្រឡង (Edit Session)
@app.route('/edit_session/<old_session_code>', methods=['POST'])
def edit_session(old_session_code):
    if 'loggedin' not in session: return redirect(url_for('login'))
    
    new_session_code = request.form['session_code'].strip()
    session_type_en = request.form['session_type_en'].strip()
    session_type_kh = request.form['session_type_kh'].strip()
    title_en = request.form.get('title_en', '').strip() # 💡 ថ្មី
    title_kh = request.form.get('title_kh', '').strip() # 💡 ថ្មី
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions 
            SET session_code = %s, session_type_en = %s, session_type_kh = %s, title_en = %s, title_kh = %s 
            WHERE session_code = %s
        """, (new_session_code, session_type_en, session_type_kh, title_en, title_kh, old_session_code))
        conn.commit()
        cursor.close()
        conn.close()
        flash('កែប្រែវគ្គប្រឡងបានជោគជ័យ!', 'success')
    except Exception as err:
        flash(f'មានបញ្ហាក្នុងការកែប្រែ: {str(err)}', 'danger')
        
    return redirect(url_for('manage_sessions'))

# មុខងារសម្រាប់លុបវគ្គប្រឡង (Delete Session)
@app.route('/delete_session/<session_code>', methods=['POST'])
def delete_session(session_code):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_code = %s", (session_code,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('លុបវគ្គប្រឡងបានជោគជ័យ!', 'success')
    except mysql.connector.Error as err:
        # ប្រសិនបើវគ្គនេះកំពុងមានបេក្ខជនប្រើប្រាស់ (ជាប់ Foreign Key) ប្រព័ន្ធនឹងមិនឱ្យលុបទេ
        if err.errno == 1451: 
            flash('មិនអាចលុបបានទេ ព្រោះវគ្គនេះមានទិន្នន័យបេក្ខជនកំពុងប្រើប្រាស់!', 'danger')
        else:
            flash(f'មានបញ្ហា: {str(err)}', 'danger')
            
    return redirect(url_for('manage_sessions'))



@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    # ១. ទាញយកកូដវគ្គប្រឡងដែល Admin បានជ្រើសរើសពី Dropdown (ឧ. 0022026C)
    session_code_prefix = request.form.get('session_code', '').strip()
    
    if 'excel_file' not in request.files or not session_code_prefix:
        flash('សូមជ្រើសរើសវគ្គប្រឡង និង File Excel', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['excel_file']
    if file.filename == '':
        flash('មិនមាន File ត្រូវបានជ្រើសរើសទេ', 'danger')
        return redirect(url_for('dashboard'))

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            df = pd.read_excel(filepath)
            conn = get_db_connection()
            cursor = conn.cursor()

            success_count = 0
            error_list = []

            # ២. ដំណើរការទិន្នន័យម្តងមួយជួរៗ (លុបចោលកូដ Insert ចូល Table sessions ទាំងស្រុង)
            for index, row in df.iterrows():
                # កាត់យកលេខបេក្ខជនពី Excel ឧ. 50200001
                raw_app_no = str(row['Application No']).strip() 
                
                # ផ្គុំលេខកូដចូលគ្នា: 0022026C + 50200001 = 0022026C50200001
                full_app_no = f"{session_code_prefix}{raw_app_no}" 
                
                name_en = str(row['Name']).strip()
                gender = 'M' if str(row['Gender']).strip().upper() == 'M' else 'F'
                industry = str(row['Industry']).strip()
                room = str(row['Room']).strip()
                exam_session = str(row['Session']).strip() # វេនប្រឡង ឧ. 1st (09:30)

                # ឈ្មោះរូបថតក៏ប្រើលេខកូដពេញដែរ
                photo_filename = f"{full_app_no}_PT.png"
                photo_path = os.path.join(app.config['PHOTO_FOLDER'], photo_filename)
                face_encoding_json = None

                # ៣. ស្កេនផ្ទៃមុខពីរូបថត
                if os.path.exists(photo_path):
                    image = face_recognition.load_image_file(photo_path)
                    encodings = face_recognition.face_encodings(image)
                    if len(encodings) > 0:
                        face_encoding_json = json.dumps(encodings[0].tolist())
                    else:
                        error_list.append(f"មើលមុខមិនច្បាស់: {photo_filename}")
                else:
                    error_list.append(f"បាត់រូបថត: {photo_filename}")

                # ៤. បញ្ចូលទិន្នន័យទៅក្នុងតារាង candidates តែមួយគត់
                sql = """
                    INSERT IGNORE INTO candidates 
                    (application_no, session, name_en, gender, industry, test_room, original_photo_path, face_encoding) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                val = (full_app_no, exam_session, name_en, gender, industry, room, photo_filename, face_encoding_json)
                cursor.execute(sql, val)
                
                if cursor.rowcount > 0:
                    success_count += 1

            conn.commit()
            cursor.close()
            conn.close()

            flash(f'បញ្ចូលទិន្នន័យជោគជ័យចំនួន {success_count} នាក់ សម្រាប់វគ្គ {session_code_prefix}!', 'success')
            if error_list:
                flash(f'បញ្ហាខ្លះៗ: {", ".join(error_list[:3])}...', 'warning') 

        except Exception as e:
            flash(f'មានបញ្ហាក្នុងការអាន File: {str(e)}', 'danger')

        return redirect(url_for('dashboard'))
    
  
# មុខងារសម្រាប់ថតរូបថ្មី ទុកជាប្រវត្តិរូបយោង (Update Reference Photo)
@app.route('/update_reference_photo', methods=['POST'])
def update_reference_photo():
    if 'loggedin' not in session:
        return {"status": "error", "message": "សូម Login ជាមុនសិន!"}, 401
        
    data = request.json
    app_no = data.get('application_no')
    image_data = data.get('image') # រូបភាពផ្ទាល់ពីកាមេរ៉ា
    
    if not app_no or not image_data:
        return {"status": "error", "message": "ទិន្នន័យមិនគ្រប់គ្រាន់"}
        
    try:
        # ១. បំប្លែងរូបភាពពីកាមេរ៉ា (Base64) មកជា File រូបភាព
        image_bytes = base64.b64decode(image_data.split(',')[1])
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        
        # ២. ស្កេនរកផ្ទៃមុខក្នុងរូបភាពថ្មីនេះ
        unknown_image = np.array(image)
        encodings = face_recognition.face_encodings(unknown_image)
        
        if len(encodings) == 0:
            return {"status": "error", "message": "មើលមុខមិនច្បាស់ ឬគ្មានមនុស្សនៅមុខកាមេរ៉ាទេ! សូមថតម្តងទៀត។"}
            
        # ទាញយកទិន្នន័យមុខ (Face Encoding)
        face_encoding_json = json.dumps(encodings[0].tolist())
        
        # ៣. Save រូបថតនេះចូលទៅក្នុង Folder របស់ប្រព័ន្ធ
        photo_filename = f"{app_no}_PT.png"
        photo_path = os.path.join(app.config['PHOTO_FOLDER'], photo_filename)
        image.save(photo_path)
        
        # ៤. ធ្វើបច្ចុប្បន្នភាពទិន្នន័យ (Update Database)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE candidates 
            SET original_photo_path = %s, face_encoding = %s 
            WHERE application_no = %s
        """, (photo_filename, face_encoding_json, app_no))
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"status": "success", "message": "ថតរូប និង Update ប្រវត្តិរូបថ្មីបានជោគជ័យ! 🎉"}
        
    except Exception as e:
        return {"status": "error", "message": f"មានបញ្ហាប្រព័ន្ធ: {str(e)}"}

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ----------------- ផ្នែកសម្រាប់ថ្ងៃប្រឡង (Exam Day) -----------------


from flask import request, jsonify

# ==================================================================
# ១. API សម្រាប់ចុះឈ្មោះក្រយៅដៃ (Enroll Fingerprint) ទុកក្នុង DB
# ==================================================================
import json
from datetime import datetime

@app.route('/api/enroll_fingerprint', methods=['POST'])
def enroll_fingerprint():
    data = request.get_json()
    app_no = data.get('application_no')
    
    fp_right = data.get('right_thumb') 
    fp_left = data.get('left_thumb')

    if not app_no or not fp_right or not fp_left:
        return jsonify({'status': 'error', 'message': 'ទិន្នន័យក្រយៅដៃមិនពេញលេញ! (ត្រូវការទាំងស្តាំ និងឆ្វេង)'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) # ប្រើ Dictionary ដើម្បីងាយស្រួលទាញទិន្នន័យ
    try:
        # ១. ឆែកមើលសិនថា តើពិតជាមានបេក្ខជននេះមែនឬអត់?
        cursor.execute("SELECT application_no FROM candidates WHERE application_no = %s", (app_no,))
        if not cursor.fetchone():
            return jsonify({'status': 'error', 'message': 'រកមិនឃើញបេក្ខជនលេខនេះក្នុងប្រព័ន្ធទេ!'})

        # ២. បើមាន ធ្វើការចងក្រយៅដៃទាំង២ ទៅជា JSON
        combined_templates = {
            "right_thumb": fp_right,
            "left_thumb": fp_left
        }
        json_string_to_save = json.dumps(combined_templates)

        # ៣. ធ្វើការ Update ទិន្នន័យ និងកត់ត្រាវត្តមាន (is_present = 1)
        now = datetime.now()
        sql = """
            UPDATE candidates 
            SET fingerprint_template = %s, 
                is_present = 1, 
                attendance_time = %s 
            WHERE application_no = %s
        """
        cursor.execute(sql, (json_string_to_save, now, app_no))
        conn.commit()

        # ទោះបីជា MySQL ប្រាប់ថាមាន 0 ជួរដេកបានកែប្រែ (ដោយសារទិន្នន័យដូចចាស់បេះបិទ) 
        # ក៏យើងចាត់ទុកថាជោគជ័យដែរ ព្រោះយើងបានឆែករួចហើយថាមានបេក្ខជននេះមែន
        return jsonify({'status': 'success', 'message': 'បានចុះឈ្មោះក្រយៅដៃ និងកត់ត្រាវត្តមានជោគជ័យ!'})

    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

import json
import numpy as np
import base64
import io
import os  
from PIL import Image
#import face_recognition
import cv2
from datetime import datetime
from flask import request, session, jsonify

@app.route('/api/identify_biometrics', methods=['POST'])
def identify_biometrics():
    if 'loggedin' not in session:
        return {"status": "error", "message": "សូម Login ជាមុនសិន!", "position_ok": False}, 401
        
    current_session = session.get('active_session')
    if not current_session:
        return {"status": "error", "message": "មិនទាន់ជ្រើសរើសវគ្គប្រឡងនៅលើ Dashboard ទេ!", "position_ok": False}

    data = request.json
    image_data = data.get('image')
    station_type = data.get('station_type', 'skill_test') 
    
    application_no = data.get('application_no') 
    
    if not image_data or not application_no:
        return {"status": "error", "message": "សូមបញ្ជូនលេខកូដ UBT ជាមុនសិន!", "position_ok": False}
        
    application_no = str(application_no).strip()
    conn = get_db_connection()
    
    # 💡 [ចំណុចបន្ថែមថ្មី] បង្ខំឱ្យ MySQL បោះបង់ទិន្នន័យចាស់ចោល ហើយអានទិន្នន័យថ្មីបំផុត (Flush Snapshot)
    conn.commit() 
    
    cursor = conn.cursor(dictionary=True)

    try:
        # ==========================================
        # 🚀 ១. ទាញយកទិន្នន័យពី Database
        # ==========================================
        if station_type == 'skill_test':
            cursor.execute("""
                SELECT 
                    s.application_no, s.name_en, s.gender, s.dob, 
                    c.id_card_no, c.passport_no, s.test_date, 
                    s.group_no, s.seat_no, s.entry_time,
                    s.specialized_tasks AS industry, 
                    c.latest_scan_photo, c.original_photo_path, c.face_encoding 
                FROM skill_test_candidates s
                JOIN candidates c ON s.application_no = c.application_no
                WHERE c.session_code = %s 
                AND s.application_no = %s
            """, (current_session, application_no))
        else:
            cursor.execute("""
                SELECT 
                    c.application_no, c.name_en, c.gender, c.dob, 
                    c.id_card_no, c.passport_no, 
                    '-' AS test_date, 
                    c.SeatNo AS seat_no, 
                    '-' AS group_no, 
                    c.exam_session AS entry_time,
                    c.industry, 
                    c.latest_scan_photo, c.original_photo_path, c.face_encoding 
                FROM candidates c
                JOIN skill_test_candidates s ON c.application_no = s.application_no
                WHERE c.session_code = %s 
                AND c.application_no = %s 
                AND s.is_final_passer = 1 
            """, (current_session, application_no))

        db_candidate = cursor.fetchone()

        if not db_candidate:
            return {"status": "error", "message": f"រកមិនឃើញលេខកូដ ឬបេក្ខជនគ្មានសិទ្ធិ (ប្រឡងធ្លាក់)!", "position_ok": True}

        # ==========================================
        # 🚀 ២. បំប្លែងរូបភាពពីកាមេរ៉ាផ្ទាល់ និងចាប់យកមុខធំជាងគេ
        # ==========================================
        image_bytes = base64.b64decode(image_data.split(',')[1])
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        image.thumbnail((480, 480))
        unknown_image = np.array(image)
        
        face_locations = face_recognition.face_locations(unknown_image)
        if len(face_locations) == 0:
            return {"status": "error", "message": "មិនឃើញមុខទេ! សូមតម្រង់មុខឱ្យចំកាមេរ៉ា", "position_ok": False}

        # 💡 [ចំណុចពិសេស] រើសយកតែផ្ទៃមុខណាដែល "ធំជាងគេ" (ការពារការចាប់យកអ្នកឈរពីក្រោយ)
        largest_face = max(face_locations, key=lambda rect: (rect[2] - rect[0]) * (rect[1] - rect[3]))

        unknown_image_bgr = cv2.cvtColor(unknown_image, cv2.COLOR_RGB2BGR)
        is_real, spoof_msg = check_liveness_ai(unknown_image_bgr, largest_face)
        if not is_real:
            return {"status": "error", "message": f"❌ {spoof_msg}", "position_ok": True}

        # បំប្លែងកូដមុខតែម្នាក់គត់ដែលធំជាងគេ
        unknown_encoding = face_recognition.face_encodings(unknown_image, known_face_locations=[largest_face])[0]

        # ==========================================
        # 🚀 ៣. ប្រមូលទិន្នន័យមុខយោងទាំងអស់ (Triple-Check System)
        # ==========================================
        known_encodings = []
        
        # ៣.១៖ ទាញយកកូដមុខពី Database (បើមាន)
        if db_candidate.get('face_encoding'):
            try:
                known_encodings.append(np.array(json.loads(db_candidate['face_encoding'])))
            except Exception:
                pass
                
        # ៣.២៖ ទាញយករូបដើម (Original)
        original_photo = db_candidate.get('original_photo_path')
        if original_photo:
            try:
                ori_path = os.path.join('static', 'uploads', 'reference_photos', original_photo)
                if os.path.exists(ori_path):
                    ori_img = face_recognition.load_image_file(ori_path)
                    ori_locs = face_recognition.face_locations(ori_img)
                    if ori_locs:
                        # រើសមុខធំបំផុតក្នុងរូបដើម
                        ori_largest = max(ori_locs, key=lambda rect: (rect[2] - rect[0]) * (rect[1] - rect[3]))
                        ori_encs = face_recognition.face_encodings(ori_img, known_face_locations=[ori_largest])
                        if ori_encs: known_encodings.append(ori_encs[0])
            except Exception:
                pass

        # ៣.៣៖ ទាញយករូបថ្មីបំផុត (Exam)
        latest_photo = db_candidate.get('latest_scan_photo')
        if latest_photo:
            try:
                lat_path = os.path.join('static', 'latest_scans', latest_photo)
                if os.path.exists(lat_path):
                    lat_img = face_recognition.load_image_file(lat_path)
                    lat_locs = face_recognition.face_locations(lat_img)
                    if lat_locs:
                        # រើសមុខធំបំផុតក្នុងរូប Exam
                        lat_largest = max(lat_locs, key=lambda rect: (rect[2] - rect[0]) * (rect[1] - rect[3]))
                        lat_encs = face_recognition.face_encodings(lat_img, known_face_locations=[lat_largest])
                        if lat_encs: known_encodings.append(lat_encs[0])
            except Exception:
                pass

        if not known_encodings:
            return {"status": "error", "message": "បេក្ខជននេះមិនទាន់មានរូបថតនៅក្នុងប្រព័ន្ធទាល់តែសោះ!", "position_ok": True}

        # ==========================================
        # 🚀 ៤. ផ្ទឹមមុខ ១ ទល់នឹង ១ 
        # ==========================================
        face_distances = face_recognition.face_distance(known_encodings, unknown_encoding)
        
        best_match_index = np.argmin(face_distances)
        similarity_percent = round((1 - face_distances[best_match_index]) * 100, 2)

        STANDARD_THRESHOLD = 60.00 if station_type == 'skill_test' else 65.00 
            
        if similarity_percent >= STANDARD_THRESHOLD:
            app_no = db_candidate['application_no']
            
            # Update វត្តមាន
            if station_type == 'skill_test':
                cursor.execute("UPDATE skill_test_candidates SET is_present = 1, attendance_time = NOW() WHERE application_no = %s", (app_no,))
            elif station_type == 'health_reg':
                cursor.execute("UPDATE candidates SET health_reg_present = 1, health_reg_time = NOW() WHERE application_no = %s", (app_no,))
            elif station_type == 'health_check':
                cursor.execute("UPDATE candidates SET health_check_present = 1, health_check_time = NOW() WHERE application_no = %s", (app_no,))
            elif station_type == 'job_app':
                cursor.execute("UPDATE candidates SET job_app_present = 1, job_app_time = NOW() WHERE application_no = %s", (app_no,))
            elif station_type == 'contract':
                cursor.execute("UPDATE candidates SET contract_present = 1, contract_time = NOW() WHERE application_no = %s", (app_no,))
            elif station_type == 'departure':
                cursor.execute("UPDATE candidates SET departure_present = 1, departure_time = NOW() WHERE application_no = %s", (app_no,))
            
            conn.commit()

            latest_photo = db_candidate.get('latest_scan_photo')
            original_photo = db_candidate.get('original_photo_path')
            photo_url = f"/static/latest_scans/{latest_photo}" if latest_photo else (f"/static/uploads/reference_photos/{original_photo}" if original_photo else "/static/default_avatar.png")

            return {
                "status": "success", "match": True, "percent": similarity_percent, "position_ok": True,
                "candidate": {
                    "application_no": app_no,
                    "name_en": db_candidate.get('name_en') or '-',
                    "photo_url": photo_url 
                }
            }
        else:
            return {"status": "fail", "message": f"មុខនេះមិនមែនជាម្ចាស់លេខកូដ UBT នេះទេ! ({similarity_percent}%)", "percent": similarity_percent, "position_ok": True}

    except Exception as e:
        return {"status": "error", "message": f"Server Error: {str(e)}", "position_ok": True}
    
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/api/verify_exam_fingerprint', methods=['POST'])
def verify_exam_fingerprint():
    data = request.json
    app_no = data.get('application_no')
    scanned_template = data.get('template')
    station_type = data.get('station_type', 'skill_test') 

    is_match = True 
    
    if is_match:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if station_type == 'skill_test':
                cursor.execute("""
                    SELECT s.application_no, s.name_en, s.gender, s.dob, c.id_card_no, c.passport_no, s.test_date, s.group_no, s.seat_no, s.entry_time, s.specialized_tasks AS industry, c.latest_scan_photo, c.original_photo_path 
                    FROM skill_test_candidates s JOIN candidates c ON s.application_no = c.application_no WHERE s.application_no = %s
                """, (app_no,))
            else:
                # 💡 [កែសម្រួល] ដក AS id_card_no ចេញ ទាញយកដាច់ដោយឡែក
                cursor.execute("""
                    SELECT application_no, name_en, gender, dob, id_card_no, passport_no, '-' AS test_date, SeatNo AS seat_no, '-' AS group_no, exam_session AS entry_time, industry, latest_scan_photo, original_photo_path 
                    FROM candidates WHERE application_no = %s
                """, (app_no,))
            
            matched_candidate = cursor.fetchone()

            if matched_candidate:
                if station_type == 'skill_test':
                    cursor.execute("UPDATE skill_test_candidates SET is_present = 1, attendance_time = NOW() WHERE application_no = %s", (app_no,))
                elif station_type == 'health_reg':
                    cursor.execute("UPDATE candidates SET health_reg_present = 1, health_reg_time = NOW() WHERE application_no = %s", (app_no,))
                elif station_type == 'health_check':
                    cursor.execute("UPDATE candidates SET health_check_present = 1, health_check_time = NOW() WHERE application_no = %s", (app_no,))
                elif station_type == 'job_app':
                    cursor.execute("UPDATE candidates SET job_app_present = 1, job_app_time = NOW() WHERE application_no = %s", (app_no,))
                elif station_type == 'contract':
                    cursor.execute("UPDATE candidates SET contract_present = 1, contract_time = NOW() WHERE application_no = %s", (app_no,))
                elif station_type == 'departure':
                    cursor.execute("UPDATE candidates SET departure_present = 1, departure_time = NOW() WHERE application_no = %s", (app_no,))
                
                conn.commit()

                latest_photo = matched_candidate.get('latest_scan_photo')
                original_photo = matched_candidate.get('original_photo_path')
                photo_url = f"/static/latest_scans/{latest_photo}" if latest_photo else (f"/static/uploads/reference_photos/{original_photo}" if original_photo else "/static/default_avatar.png")

                group_str = matched_candidate.get('group_no') or '-'
                seat_str = matched_candidate.get('seat_no') or '-'
                entry_time = matched_candidate.get('entry_time') or '-'
                room_info = f"ក្រុមទី {group_str} / តុ {seat_str} ({entry_time})" if station_type == 'skill_test' else f"តុលេខ {seat_str} ({entry_time})"

                candidate_data = {
                    "application_no": app_no,
                    "name_en": matched_candidate.get('name_en') or '-',
                    "gender": "ប្រុស / MALE" if matched_candidate.get('gender') == 'M' else ("ស្រី / FEMALE" if matched_candidate.get('gender') == 'F' else "-"),
                    "dob": matched_candidate.get('dob') if isinstance(matched_candidate.get('dob'), str) else (matched_candidate['dob'].strftime('%Y-%m-%d') if matched_candidate.get('dob') else "-"),
                    "id_card_no": matched_candidate.get('id_card_no') or "-",    # 💡 ត្រូវប្រាកដថាទាញបាន
                    "passport_no": matched_candidate.get('passport_no') or "-",  # 💡 ត្រូវប្រាកដថាទាញបាន
                    "test_date": matched_candidate.get('test_date') if isinstance(matched_candidate.get('test_date'), str) else (matched_candidate['test_date'].strftime('%Y-%m-%d') if matched_candidate.get('test_date') else "-"),
                    "room_session": room_info,
                    "industry": matched_candidate.get('industry') or "-",
                    "photo_url": photo_url 
                }

                return jsonify({"status": "success", "match": True, "candidate": candidate_data})
            else:
                return jsonify({"status": "success", "match": True}) 
                
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
        finally:
            cursor.close()
            conn.close()
    else:
        return jsonify({'status': 'success', 'match': False})

# ==================================================================
# ២. API សម្រាប់ផ្ទៀងផ្ទាត់ក្រយៅដៃពេលប្រឡង (Verify Fingerprint & Mark Attendance)
# ==================================================================
@app.route('/api/verify_fingerprint', methods=['POST'])
def verify_fingerprint():
    data = request.get_json()
    app_no = data.get('application_no')
    scanned_template = data.get('template') # ទិន្នន័យក្រយៅដៃដែលទើបស្កែនថ្មីៗ

    if not app_no or not scanned_template:
        return jsonify({'status': 'error', 'message': 'ទិន្នន័យមិនគ្រប់គ្រាន់សម្រាប់ការផ្ទៀងផ្ទាត់!'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # ១. ទាញយក Template ចាស់របស់បេក្ខជនពី Database
        cursor.execute("SELECT fingerprint_template FROM candidates WHERE application_no = %s", (app_no,))
        candidate = cursor.fetchone()

        if not candidate:
            return jsonify({'status': 'error', 'message': 'រកមិនឃើញបេក្ខជនក្នុងប្រព័ន្ធទេ!'})
        
        saved_template = candidate.get('fingerprint_template')

        if not saved_template:
            return jsonify({'status': 'error', 'message': 'បេក្ខជននេះមិនទាន់បានចុះឈ្មោះក្រយៅដៃក្នុងប្រព័ន្ធទេ!'})

        # ២. ធ្វើការប្រៀបធៀប (Match) ក្រយៅដៃ 
        # (ចំណាំ៖ ជាទូទៅ ការ Match ក្រយៅដៃត្រូវបានធ្វើឡើងដោយ ZKTeco SDK ផ្ទាល់។
        # បើ SDK របស់អ្នក Match រួចហើយ ទើបបាញ់មក API នេះ នោះអ្នកគ្រាន់តែ Update វត្តមានតែម្តង)
        
        # សន្មតថាស្កែនត្រូវ (Match = True)
        is_match = True # កន្លែងនេះត្រូវហៅ Function របស់ ZKTeco បើអ្នកចង់ Match ក្នុង Server

        if is_match:
            # កត់ត្រាវត្តមានថ្ងៃប្រឡង (Update is_present និង attendance_time)
            now = datetime.now()
            update_sql = """
                UPDATE candidates 
                SET is_present = 1, attendance_time = %s 
                WHERE application_no = %s
            """
            cursor.execute(update_sql, (now, app_no))
            conn.commit()

            return jsonify({
                'status': 'success', 
                'match': True,
                'message': 'ក្រយៅដៃត្រឹមត្រូវ! វត្តមានត្រូវបានកត់ត្រា។',
                'time': now.strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            return jsonify({
                'status': 'success', 
                'match': False,
                'message': 'ក្រយៅដៃមិនត្រឹមត្រូវទេ! (Mismatch)'
            })

    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/exam', methods=['GET', 'POST'])
def exam_dashboard():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    candidate = None
    if request.method == 'POST':
        raw_input = request.form['application_no'].strip()
        current_session = session.get('active_session', '').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ==========================================
        # 💡 យុទ្ធសាស្ត្រស្វែងរកដែលលឿន និងមិនធ្វើឱ្យគាំង
        # ==========================================
        
        try:
            # ជំហានទី ១៖ ករណីវាយលេខកូដ UBT ពេញ (លឿនបំផុត)
            if len(raw_input) > 8:
                cursor.execute("SELECT * FROM candidates WHERE application_no = %s LIMIT 1", (raw_input,))
                candidate = cursor.fetchone()

            # ជំហានទី ២៖ ករណីវាយតែកន្ទុយលេខកូដ (ឧ. ៣ ខ្ទង់, ៤ ខ្ទង់, ឬ ៨ ខ្ទង់)
            else:
                if current_session:
                    # ប្រើការកាត់លេខកន្ទុយ (RIGHT) ដើម្បីប្រៀបធៀប គឺលឿនជាងការប្រើ LIKE មុខក្រោយ
                    # ហើយប្រៀបធៀប session_code ដាច់ដោយឡែក ដើម្បីបង្រួមទិន្នន័យឱ្យតូចមុននឹងឆែកកន្ទុយ
                    input_length = len(raw_input)
                    
                    cursor.execute("""
                        SELECT * FROM candidates 
                        WHERE session_code = %s 
                        AND RIGHT(application_no, %s) = %s
                        LIMIT 1
                    """, (current_session, input_length, raw_input))
                    candidate = cursor.fetchone()
                else:
                    # ករណីគ្មាន Session
                    input_length = len(raw_input)
                    cursor.execute("""
                        SELECT * FROM candidates 
                        WHERE RIGHT(application_no, %s) = %s 
                        LIMIT 1
                    """, (input_length, raw_input))
                    candidate = cursor.fetchone()

            # បង្ហាញសារជូនដំណឹងបើរកមិនឃើញ
            if not candidate:
                prefix_msg = f" ក្នុងវគ្គ {current_session}" if current_session else ""
                flash(f'រកមិនឃើញបេក្ខជនដែលមានលេខកូដ [ {raw_input} ]{prefix_msg} ទេ!', 'danger')

        except Exception as e:
            # ការពារករណី Error ផ្សេងៗកុំឱ្យគាំង Page
            flash('មានបញ្ហាក្នុងការស្វែងរកទិន្នន័យ សូមព្យាយាមម្តងទៀត។', 'warning')
            print(f"Error in exam_dashboard search: {e}")
            
        finally:
            cursor.close()
            conn.close()

    return render_template('exam.html', candidate=candidate, full_name=session.get('full_name', ''))



import cv2
import numpy as np
import base64
import json
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
#import face_recognition
import io
from PIL import Image
import onnxruntime as ort  # 💡 បណ្ណាល័យថ្មីសម្រាប់រត់ AI Model

# ==========================================================
# 💡 បើកដំណើរការ AI Model (ទុកជាមុន ដើម្បកុំឱ្យយឺតពេលស្កេន)
# ==========================================================
liveness_session = None
liveness_input_name = None
try:
    # កំណត់ទីតាំង File AI ទី២ របស់យើង
    model_path = os.path.join('static', 'models', 'liveness_model.onnx')
    if os.path.exists(model_path):
        liveness_session = ort.InferenceSession(model_path)
        liveness_input_name = liveness_session.get_inputs()[0].name
        print("✅ ប្រព័ន្ធ AI Anti-Spoofing ដំណើរការបានជោគជ័យ!")
    else:
        print("⚠️ រកមិនឃើញឯកសារ liveness_model.onnx ទេ! សូមពិនិត្យ Folder ម្តងទៀត។")
except Exception as e:
    print(f"⚠️ កំហុសក្នុងការបើក AI Model: {e}")

# ==========================================================
# ១. មុខងារទប់ស្កាត់ការបន្លំកម្រិតធនាគារ (Deep Learning Anti-Spoofing)
# ==========================================================
def check_liveness_ai(frame_bgr, face_location):
    if liveness_session is None:
        return True, "រំលង (មិនទាន់មាន AI Model)"
        
    try:
        top, right, bottom, left = face_location
        
        # 💡 កែតម្រូវទី១៖ ពង្រីកប្រអប់ឱ្យធំខ្លាំង ដើម្បីឱ្យ AI មើលឃើញ "គែមទូរសព្ទដៃ" និង "ផ្ទៃខាងក្រោយ"
        h_frame, w_frame = frame_bgr.shape[:2]
        face_w = right - left
        face_h = bottom - top
        
        # ពង្រីកប្រអប់ ៦០% ជុំវិញផ្ទៃមុខ
        top_exp = max(0, int(top - face_h * 0.6))
        bottom_exp = min(h_frame, int(bottom + face_h * 0.6))
        left_exp = max(0, int(left - face_w * 0.6))
        right_exp = min(w_frame, int(right + face_w * 0.6))
        
        face_crop = frame_bgr[top_exp:bottom_exp, left_exp:right_exp]
        
        # 💡 កែតម្រូវទី២៖ រៀបចំទិន្នន័យឱ្យត្រូវស្តង់ដារ AI របស់ Intel (Normalization & RGB)
        resized_face = cv2.resize(face_crop, (128, 128))
        rgb_face = cv2.cvtColor(resized_face, cv2.COLOR_BGR2RGB) # ប្តូរទៅពណ៌ RGB ជាចាំបាច់
        
        # ចែកនឹង 255 (សំខាន់បំផុតដើម្បីឱ្យ AI ស្គាល់ទម្រង់ស្តង់ដារ)
        input_data = rgb_face.astype(np.float32) / 255.0 
        input_data = np.transpose(input_data, (2, 0, 1))
        input_data = np.expand_dims(input_data, axis=0)
        
        # បញ្ជូនរូបភាពចូលទៅក្នុងខួរក្បាល AI ដើម្បីវិភាគ
        outputs = liveness_session.run(None, {liveness_input_name: input_data})
        logits = outputs[0][0] 
        
        # បំប្លែងពិន្ទុទៅជាភាគរយ (Softmax Algorithm)
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        
        # 💡 កែតម្រូវទី៣៖ កំណត់អត្ថន័យពិន្ទុឱ្យត្រូវ (Intel Model: Index 0 គឺបន្លំ, Index 1 គឺមនុស្សពិត)
        spoof_score = probs[0] # ភាគរយជារូបថត/ទូរសព្ទ
        real_score = probs[1]  # ភាគរយជាមនុស្សពិត
        
        # បង្ហាញពិន្ទុក្នុង Terminal ដើម្បីងាយស្រួលឱ្យអ្នកតាមដានមើលវាលោតលេខ
        print(f"📊 [AI Scanner] ភាគរយបន្លំ: {spoof_score*100:.1f}% | មនុស្សពិត: {real_score*100:.1f}%")
        
        # បើ AI ប្រាប់ថាភាគរយនៃការបន្លំមានលើសពី ៤០% គឺទាត់ចោលភ្លាមៗ!
        if spoof_score > 0.4:
            return False, f"រកឃើញការប្រើប្រាស់រូបថត ឬទូរសព្ទ! [កម្រិត: {spoof_score*100:.1f}%]"
            
        return True, "មនុស្សពិត"
        
    except Exception as e:
        print(f"Liveness AI Error: {e}")
        return True, "រំលង (មានកំហុសបច្ចេកទេស)"

# ==========================================================
# ២. មុខងារផ្ទៀងផ្ទាត់ផ្ទៃមុខ 
# ==========================================================
@app.route('/verify_face', methods=['POST'])
def verify_face():
    if 'loggedin' not in session:
        return {"status": "error", "message": "សូម Login ជាមុនសិន!"}, 401
        
    data = request.json
    app_no = data.get('application_no')
    image_data = data.get('image')
    # 💡 ត្រៀមទទួលកូដម្រាមដៃពី ZKTeco នាពេលខាងមុខ
    fingerprint_template = data.get('fingerprint_template') 
    
    if not app_no or not image_data:
        return {"status": "error", "message": "ទិន្នន័យមិនគ្រប់គ្រាន់"}
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ទាញយកទិន្នន័យបេក្ខជន
        cursor.execute("SELECT original_photo_path, face_encoding FROM candidates WHERE application_no = %s", (app_no,))
        candidate = cursor.fetchone()
        
        if not candidate:
            return {"status": "error", "message": "រកមិនឃើញលេខកូដបេក្ខជននេះទេ"}

        known_encoding = None

        if candidate['face_encoding']:
            known_encoding = np.array(json.loads(candidate['face_encoding']))
        else:
            photo_filename = candidate['original_photo_path']
            if not photo_filename:
                 return {"status": "error", "message": "មិនមានរូបថតសម្រាប់បេក្ខជននេះទេ"}
                 
            photo_path = os.path.join(app.config['PHOTO_FOLDER'], photo_filename)
            if not os.path.exists(photo_path):
                return {"status": "error", "message": "រកមិនឃើញរូបថតដើមក្នុង Folder ទេ!"}

            ref_image = face_recognition.load_image_file(photo_path)
            ref_encodings = face_recognition.face_encodings(ref_image)

            if len(ref_encodings) == 0:
                 return {"status": "error", "message": "ប្រព័ន្ធមើលមិនឃើញផ្ទៃមុខក្នុងរូបថតដើមទេ!"}
            
            known_encoding = ref_encodings[0]
            cursor.execute("UPDATE candidates SET face_encoding = %s WHERE application_no = %s", 
                           (json.dumps(known_encoding.tolist()), app_no))
            conn.commit()

        # ==========================================================
        # ៣. ដំណើរការរូបភាពពីកាមេរ៉ា និង ទប់ស្កាត់ការបន្លំ (ដោយ AI ទី២)
        # ==========================================================
        image_bytes = base64.b64decode(image_data.split(',')[1])
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        unknown_image = np.array(image)

        face_locations = face_recognition.face_locations(unknown_image)
        if len(face_locations) == 0:
            return {"status": "error", "message": "មើលមុខមិនច្បាស់ទេ! សូមមើលចំកាមេរ៉ា។"}

        # 💡 បំប្លែងរូបភាព និងឆែកមើលការបន្លំជាមួយ AI របស់ Intel
        unknown_image_bgr = cv2.cvtColor(unknown_image, cv2.COLOR_RGB2BGR)
        is_real, spoof_msg = check_liveness_ai(unknown_image_bgr, face_locations[0])
        
        if not is_real:
            # លោតពណ៌ក្រហមបដិសេធភ្លាមៗ បើ AI ឆែកឃើញទូរសព្ទ
            return {
                "status": "success", 
                "match": False, 
                "percent": "0.00", 
                "message": f"❌ {spoof_msg}"
            }

        unknown_encodings = face_recognition.face_encodings(unknown_image, known_face_locations=face_locations)
        unknown_encoding = unknown_encodings[0]

        # ==========================================================
        # ៤. ស្កេនប្រៀបធៀបជាមួយ "បញ្ជីខ្មៅ (Blacklist)"
        # ==========================================================
        cursor.execute("""
            SELECT application_no, name_en, face_encoding, ban_reason, ban_until,
                   gender, dob, id_card_no, passport_no, test_date, test_room, exam_session, industry
            FROM candidates 
            WHERE is_banned = TRUE AND face_encoding IS NOT NULL
        """)
        banned_list = cursor.fetchall()
        
        if banned_list:
            banned_encodings = [np.array(json.loads(b['face_encoding'])) for b in banned_list]
            blacklist_distances = face_recognition.face_distance(banned_encodings, unknown_encoding)
            
            if len(blacklist_distances) > 0:
                best_match_index = np.argmin(blacklist_distances)
                best_distance = blacklist_distances[best_match_index]
                best_similarity = round((1 - best_distance) * 100, 2)
                
                if best_similarity >= 60.0:
                    bad_guy = banned_list[best_match_index]
                    
                    now_date = datetime.now().date()
                    ban_end_date = bad_guy['ban_until']
                    time_left_str = "ជាប់ពិន័យរហូត (Permanent)"
                    
                    if ban_end_date and ban_end_date >= now_date:
                        diff = relativedelta(ban_end_date, now_date)
                        time_left_str = f"{diff.years} ឆ្នាំ, {diff.months} ខែ, {diff.days} ថ្ងៃ"
                    elif ban_end_date and ban_end_date < now_date:
                        pass 
                    
                    if ban_end_date is None or ban_end_date >= now_date:
                        gender_str = "ប្រុស / MALE" if bad_guy.get('gender') == 'M' else "ស្រី / FEMALE"
                        dob_str = bad_guy.get('dob').strftime('%Y-%m-%d') if bad_guy.get('dob') else "-"
                        id_str = bad_guy.get('id_card_no') or ""
                        pass_str = bad_guy.get('passport_no') or ""
                        passport_id_str = f"{id_str} {pass_str}".strip() or "-"
                        room_session_str = f"{bad_guy.get('test_room') or '-'} ({bad_guy.get('exam_session') or '-'})"

                        return {
                            "status": "banned",
                            "banned_name": bad_guy['name_en'],
                            "ban_reason": bad_guy['ban_reason'],
                            "time_left": time_left_str,
                            "percent": best_similarity,
                            "gender": gender_str,
                            "dob": dob_str,
                            "passport_id": passport_id_str,
                            "test_date": bad_guy.get('test_date').strftime('%Y-%m-%d') if bad_guy.get('test_date') else "-",
                            "room_session": room_session_str,
                            "industry": bad_guy.get('industry') or "-",
                            "message": f"មុខនេះត្រូវគ្នានឹងបេក្ខជនជាប់ពិន័យ ({best_similarity}%)"
                        }

        # ==========================================================
        # ៥. ធ្វើការផ្ទៀងផ្ទាត់វត្តមាន (1:1) និង Update ជីវមាត្រ
        # ==========================================================
        face_distances = face_recognition.face_distance([known_encoding], unknown_encoding)
        distance = face_distances[0]
        similarity_percent = round((1 - distance) * 100, 2)
        
        STANDARD_THRESHOLD = 60.00 
        match = similarity_percent >= STANDARD_THRESHOLD
        
        if match:
            # -------------------------------------------------------------
            # 💡 [កែប្រែថ្មី] រក្សាទុករូបថតដោយប្រើឈ្មោះ [application_no]_PT.png
            # -------------------------------------------------------------
            new_filename = f"{app_no}_PT.png"
            filepath = os.path.join(app.config['LATEST_SCANS_FOLDER'], new_filename)

            # Save រូបភាពជា File
            with open(filepath, "wb") as f:
                f.write(image_bytes)

            # Update វត្តមាន ព្រមទាំងរូបថត និងម្រាមដៃចូល Database ក្នុងពេលតែមួយ
            cursor.execute("""
                UPDATE candidates 
                SET is_present = TRUE, 
                    attendance_time = NOW(),
                    latest_scan_photo = %s,
                    fingerprint_template = IFNULL(%s, fingerprint_template)
                WHERE application_no = %s
            """, (new_filename, fingerprint_template, app_no))
            
            conn.commit()
            # -------------------------------------------------------------

            return {
                "status": "success", 
                "message": f"ត្រឹមត្រូវ! កត់វត្តមាន និងរក្សាទុករូបថតថ្មីជោគជ័យ។ ({similarity_percent}%)", 
                "match": True,
                "percent": similarity_percent
            }
        else:
            return {
                "status": "success", 
                "message": f"មិនត្រឹមត្រូវ! ភាពដូចគ្នាទាបពេក ({similarity_percent}%)", 
                "match": False,
                "percent": similarity_percent
            }
  
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"បញ្ហាប្រព័ន្ធ: {str(e)}"}
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# ==========================================================
# ដំណាក់កាលទី ២៖ ផ្ទាំងប្រឡងតេស្តជំនាញ (Skill Test - No ID Input)
# ==========================================================
@app.route('/skill_test')
def skill_test_page():
    if 'loggedin' not in session: return redirect(url_for('login'))
    return render_template('skill_test.html', full_name=session.get('full_name', ''))

# ==========================================================
# 💡 ប្រព័ន្ធ RAM Caching សម្រាប់បង្កើនល្បឿនកាមេរ៉ា (Super Fast Auto-Scan)
# ==========================================================
# អថេរ Global សម្រាប់ផ្ទុកទិន្នន័យមុខក្នុង RAM 
SKILL_TEST_CACHE = {
    'session_code': None,
    'encodings': [],
    'candidates': []
}

def load_skill_test_cache(session_code):
    """អនុគមន៍សម្រាប់ទាញទិន្នន័យពី DB មកទុកក្នុង RAM តែម្តងគត់"""
    print(f"🔄 កំពុងទាញយកទិន្នន័យផ្ទៃមុខវគ្គ {session_code} ចូលទៅក្នុង RAM...")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 💡 បន្ថែម c.original_photo_path
    cursor.execute("""
        SELECT 
            stc.application_no, stc.name_en, stc.gender, stc.dob, stc.test_date, 
            stc.entry_time, stc.group_no, stc.seat_no, stc.specialized_tasks,
            c.face_encoding, c.latest_scan_photo, c.original_photo_path, c.id_card_no, c.passport_no
        FROM skill_test_candidates stc
        JOIN candidates c ON stc.application_no = c.application_no
        WHERE c.face_encoding IS NOT NULL AND c.session_code = %s
    """, (session_code,))
    
    passers = cursor.fetchall()
    cursor.close()
    conn.close()

    encodings_list = []
    candidates_list = []
    
    for p in passers:
        try:
            # បំប្លែងទិន្នន័យពី JSON ទៅជា Numpy Array ទុកក្នុង RAM
            encoding = np.array(json.loads(p['face_encoding']))
            encodings_list.append(encoding)
            candidates_list.append(p)
        except:
            continue
            
    SKILL_TEST_CACHE['session_code'] = session_code
    SKILL_TEST_CACHE['encodings'] = encodings_list
    SKILL_TEST_CACHE['candidates'] = candidates_list
    print(f"✅ រក្សាទុកក្នុង RAM ជោគជ័យ! ចំនួនបេក្ខជនសរុប៖ {len(encodings_list)} នាក់។")



# 💡 មុខងារបន្ថែមសម្រាប់ Refresh ទិន្នន័យ (ហៅប្រើពេលមានការ Import ទិន្នន័យថ្មី)
@app.route('/refresh_camera_cache', methods=['POST'])
def refresh_camera_cache():
    if 'loggedin' not in session:
        return jsonify({"status": "error"}), 401
    current_session = session.get('active_session')
    if current_session:
        load_skill_test_cache(current_session)
        return jsonify({"status": "success", "message": "បានទាញទិន្នន័យចូល RAM ជោគជ័យ!"})
    return jsonify({"status": "error", "message": "មិនមានវគ្គប្រឡង"})


# ១. Route សម្រាប់ទទួលការចាត់តាំងបន្ទប់
@app.route('/assign_room', methods=['POST'])
def assign_room():
    if 'loggedin' not in session: return redirect(url_for('login'))
    
    user_id = request.form['user_id']
    test_room = request.form['test_room']

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # លុបចាស់ចេញ (បើមាន) ហើយបញ្ចូលថ្មី
        cursor.execute("DELETE FROM proctor_rooms WHERE user_id = %s", (user_id,))
        cursor.execute("INSERT INTO proctor_rooms (user_id, test_room) VALUES (%s, %s)", (user_id, test_room))
        conn.commit()
        flash(f'បានចាត់តាំងបន្ទប់ {test_room} ជូន Proctor នេះរួចរាល់!', 'success')
    except Exception as e:
        flash(f'មានបញ្ហា: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('manage_users'))


# ==========================================
# ១. មុខងារគ្រប់គ្រងអ្នកប្រើប្រាស់ (Manage Users)
# ==========================================
@app.route('/users', methods=['GET', 'POST'])
def manage_users():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ====================================================
    # ១. ពេលចុចប៊ូតុង "បង្កើតគណនី" (POST Request)
    # ====================================================
    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        role_id = request.form['role_id']
        email = request.form['email'].strip() if request.form.get('email') else None
        phone_number = request.form['phone_number'].strip() if request.form.get('phone_number') else None
        gender = request.form.get('gender')
        telegram_username = request.form['telegram_username'].strip() if request.form.get('telegram_username') else None
        created_by = session.get('id') 

        # រៀបចំ Upload រូបថត (Profile Image)
        profile_image_name = None
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                profile_image_name = f"{username}_{filename}"
                upload_folder = os.path.join('static', 'uploads', 'profiles')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, profile_image_name)
                file.save(file_path)

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        try:
            # ១.១ Insert គណនីថ្មីចូល Table
            cursor.execute("""
                INSERT INTO users (
                    role_id, username, password_hash, full_name, email, 
                    phone_number, gender, telegram_username, profile_image, created_by, is_active
                ) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            """, (role_id, username, password_hash, full_name, email, phone_number, gender, telegram_username, profile_image_name, created_by))
            
            # ទាញយក ID របស់ User ដែលទើបបង្កើតថ្មីៗ
            new_user_id = cursor.lastrowid
            
            # 💡 ១.២ Copy សិទ្ធិពី Role ដើម យកមកដាក់អោយ User ថ្មីនេះ (Auto Assign Permissions)
            if new_user_id and role_id:
                cursor.execute("SELECT permission_id FROM role_permissions WHERE role_id = %s", (role_id,))
                role_perms = cursor.fetchall()
                if role_perms:
                    insert_data = [(new_user_id, rp['permission_id']) for rp in role_perms]
                    cursor.executemany("INSERT INTO user_permissions (user_id, permission_id) VALUES (%s, %s)", insert_data)

            conn.commit() 
            
            # ១.៣ កូដបង្កើត Notification ស្វ័យប្រវត្តិ
            try:
                message = f'គណនីថ្មី "{full_name}" ត្រូវបានបង្កើតដោយ {session.get("full_name")}'
                cursor.execute("""
                    SELECT u.id FROM users u
                    JOIN roles r ON u.role_id = r.role_id
                    WHERE r.name IN ('Admin', 'Super Admin')
                """)
                admins = cursor.fetchall()
                for admin in admins:
                    cursor.execute("""
                        INSERT INTO notifications (user_id, message, type) 
                        VALUES (%s, %s, 'info')
                    """, (admin['id'], message))
                conn.commit() 
            except Exception as notif_error:
                print(f"បញ្ហាក្នុងការបង្កើត Notification: {notif_error}")

            flash('បង្កើតគណនីថ្មីបានជោគជ័យ!', 'success')
            
        except Exception as err:
            conn.rollback()
            flash(f'មានបញ្ហា: {str(err)}', 'danger')
            
        finally:
            cursor.close()
            conn.close()
            return redirect(url_for('manage_users'))

    # ====================================================
    # ២. ពេលបើកមើលទំព័រដំបូង (GET Request)
    # ====================================================
    try:
        cursor.execute("SELECT role_id, name FROM roles") 
        roles_list = cursor.fetchall()
        
        cursor.execute("SELECT DISTINCT test_room FROM candidates WHERE test_room IS NOT NULL ORDER BY test_room ASC")
        rooms_list = cursor.fetchall()

        cursor.execute("""
            SELECT u.*, r.name AS role_name, pr.test_room
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.role_id
            LEFT JOIN proctor_rooms pr ON u.id = pr.user_id
            ORDER BY u.id DESC
        """)
        users_list = cursor.fetchall()

        # ១. ទាញយកឈ្មោះសិទ្ធិគោលទាំងអស់
        cursor.execute("SELECT id, name, description FROM permissions ORDER BY id ASC")
        raw_permissions = cursor.fetchall()

        # 💡 បង្កើត Dictionary សម្រាប់ចាត់ថ្នាក់សិទ្ធិឱ្យដូច Sidebar ទាំងស្រុង
        category_map = {
            # ក្រុមទី ១
            'view_dashboard': '១. ផ្ទាំងគ្រប់គ្រងទូទៅ (Dashboard)',
            'scan_face': '១. ផ្ទាំងគ្រប់គ្រងទូទៅ (Dashboard)',
            'scan_face_universal': '១. ផ្ទាំងគ្រប់គ្រងទូទៅ (Dashboard)',
            
            # ក្រុមទី ២
            'manage_counter_calling': '២. ប្រព័ន្ធលេខរង់ចាំ (Queue System)',
            'view_kiosk': '២. ប្រព័ន្ធលេខរង់ចាំ (Queue System)',
            'manage_kiosk': '២. ប្រព័ន្ធលេខរង់ចាំ (Queue System)',
            'view_queue_tv': '២. ប្រព័ន្ធលេខរង់ចាំ (Queue System)',
            
            # ក្រុមទី ៣ (រួមបញ្ចូលទាំងប៊ូតុងថ្មីៗក្នុងទំព័រ Skill Test)
            'manage_candidates_ubt': '៣. ការគ្រប់គ្រងបេក្ខជន (Candidate Management)',
            'manage_candidates_skill': '៣. ការគ្រប់គ្រងបេក្ខជន (Candidate Management)',
            'manage_applications': '៣. ការគ្រប់គ្រងបេក្ខជន (Candidate Management)',
            'mark_all_present_skill': '៣. ការគ្រប់គ្រងបេក្ខជន (Candidate Management)',
            'generate_qr_skill': '៣. ការគ្រប់គ្រងបេក្ខជន (Candidate Management)',
            'download_report_skill': '៣. ការគ្រប់គ្រងបេក្ខជន (Candidate Management)',
            'view_reports': '៣. ការគ្រប់គ្រងបេក្ខជន (Candidate Management)',
            
            # ក្រុមទី ៤
            'import_ubt_data': '៤. នាំចូលទិន្នន័យ (Import Data)',
            'import_skill_data': '៤. នាំចូលទិន្នន័យ (Import Data)',
            'import_excel': '៤. នាំចូលទិន្នន័យ (Import Data)',
            
            # ក្រុមទី ៥
            'manage_correction_requests': '៥. រដ្ឋបាល & ការកំណត់ (Admin)',
            'manage_sessions': '៥. រដ្ឋបាល & ការកំណត់ (Admin)',
            'manage_blacklists': '៥. រដ្ឋបាល & ការកំណត់ (Admin)',
            'manage_users': '៥. រដ្ឋបាល & ការកំណត់ (Admin)',
            'manage_roles': '៥. រដ្ឋបាល & ការកំណត់ (Admin)',
            'manage_counters': '៥. រដ្ឋបាល & ការកំណត់ (Admin)',
            'manage_tv_settings': '៥. រដ្ឋបាល & ការកំណត់ (Admin)',
            'manage_qr_settings': '៥. រដ្ឋបាល & ការកំណត់ (Admin)',
            
            # ក្រុមទី ៦
            'manage_occupations': '៦. ការកំណត់ទូទៅ (General Settings)',
            'manage_relationships': '៦. ការកំណត់ទូទៅ (General Settings)',
            'manage_education': '៦. ការកំណត់ទូទៅ (General Settings)',
            'manage_banks': '៦. ការកំណត់ទូទៅ (General Settings)',
            'manage_addresses': '៦. ការកំណត់ទូទៅ (General Settings)',
            'search_addresses': '៦. ការកំណត់ទូទៅ (General Settings)',
            'manage_settings': '៦. ការកំណត់ទូទៅ (General Settings)'
        }

        # 💡 ចងក្រងសិទ្ធិជាក្រុមបញ្ជូនទៅ HTML
        grouped_permissions = {}
        # រៀបចំលំដាប់ឱ្យត្រឹមត្រូវ
        order = ['១. ផ្ទាំងគ្រប់គ្រងទូទៅ (Dashboard)', '២. ប្រព័ន្ធលេខរង់ចាំ (Queue System)', '៣. ការគ្រប់គ្រងបេក្ខជន (Candidate Management)', '៤. នាំចូលទិន្នន័យ (Import Data)', '៥. រដ្ឋបាល & ការកំណត់ (Admin)', '៦. ការកំណត់ទូទៅ (General Settings)', '៧. ផ្សេងៗ (Others)']
        for cat in order: grouped_permissions[cat] = []

        for p in raw_permissions:
            cat = category_map.get(p['name'], '៧. ផ្សេងៗ (Others)')
            grouped_permissions[cat].append(p)
            
        # លុបក្រុមណាដែលអត់មានសិទ្ធិចោល
        grouped_permissions = {k: v for k, v in grouped_permissions.items() if v}

        # ២. ទាញយកសិទ្ធិ Matrix របស់ User ម្នាក់ៗ (កូដនៅរក្សាទុកដដែល)
        cursor.execute("SELECT user_id, permission_id, can_view, can_create, can_edit, can_delete FROM user_permissions")
        raw_user_perms = cursor.fetchall()
        
        user_perms = {}
        for rp in raw_user_perms:
            uid = rp['user_id']
            pid = rp['permission_id']
            if uid not in user_perms:
                user_perms[uid] = {}
            user_perms[uid][pid] = {
                'can_view': rp['can_view'],
                'can_create': rp['can_create'],
                'can_edit': rp['can_edit'],
                'can_delete': rp['can_delete']
            }
        
    except Exception as e:
        print(f"Database Error: {e}")
        # ... កូដចាស់ដដែល ...

    # 💡 ត្រង់ Return នេះ កុំភ្លេចប្តូរពី all_permissions ទៅជា grouped_permissions វិញ
    return render_template('users.html', users=users_list, roles=roles_list, rooms=rooms_list, 
                           grouped_permissions=grouped_permissions, user_perms=user_perms, 
                           full_name=session.get('full_name'))

# ==========================================
# 💡 មុខងារកំណត់សិទ្ធិផ្តាច់មុខតាម User
# ==========================================
@app.route('/update_user_permissions/<int:user_id>', methods=['POST'])
def update_user_permissions(user_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    # 💡 បន្ថែម dictionary=True នៅទីនេះ ទើបវាស្គាល់ p['id']
    cursor = conn.cursor(dictionary=True) 
    
    try:
        # ១. លុបសិទ្ធិចាស់ៗទាំងអស់ចេញសិន
        cursor.execute("DELETE FROM user_permissions WHERE user_id = %s", (user_id,))
        
        # ២. ទាញយក Permission ID ទាំងអស់ពី Database ដើម្បី Loop ឆែកមើល
        cursor.execute("SELECT id FROM permissions")
        all_perms = cursor.fetchall()
        
        insert_data = []
        for p in all_perms:
            pid = p['id']
            # ចាប់យកតម្លៃពី Checkbox (កុងតាក់) នីមួយៗក្នុង HTML
            can_view = 1 if request.form.get(f'perm_{pid}_view') else 0
            can_create = 1 if request.form.get(f'perm_{pid}_create') else 0
            can_edit = 1 if request.form.get(f'perm_{pid}_edit') else 0
            can_delete = 1 if request.form.get(f'perm_{pid}_delete') else 0
            
            # បើមានបើកកុងតាក់ (Tick) យ៉ាងហោចណាស់ ១ ក្នុងជួរនោះ យើងនឹង Insert វាចូល
            if can_view or can_create or can_edit or can_delete:
                insert_data.append((user_id, pid, can_view, can_create, can_edit, can_delete))

        if insert_data:
            insert_query = """
                INSERT INTO user_permissions (user_id, permission_id, can_view, can_create, can_edit, can_delete) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(insert_query, insert_data)

        conn.commit()
        flash('បានរក្សាទុកសិទ្ធិសម្រាប់គណនីនេះដោយជោគជ័យ!', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"Error saving permissions: {e}") # បង្ហាញ Error ក្នុង Terminal ឱ្យយើងឃើញ
        flash(f'មានបញ្ហាក្នុងការកំណត់សិទ្ធិ: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('manage_users'))

# ==============================================================
# 💡 មុខងារពិសេសសម្រាប់ឆែកសិទ្ធិ (Global Permission Checker)
# មុខងារនេះនឹងបញ្ជូនសិទ្ធិទៅកាន់គ្រប់ទំព័រ HTML ទាំងអស់ដោយស្វ័យប្រវត្តិ
# ==============================================================
@app.context_processor
def inject_permissions():
    user_perms_dict = {}
    if 'id' in session:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            # ទាញយកសិទ្ធិទាំងអស់របស់ User ដែលកំពុង Login
            cursor.execute("""
                SELECT p.name, up.can_view, up.can_create, up.can_edit, up.can_delete 
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = %s
            """, (session['id'],))
            
            for row in cursor.fetchall():
                user_perms_dict[row['name']] = row
                
        except Exception as e:
            print("Permission Check Error:", e)
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals(): conn.close()
            
    # បង្កើតអនុគមន៍ has_perm សម្រាប់ប្រើក្នុង HTML (ឧ. has_perm('view_queue_tv'))
    def has_perm(perm_name, action='can_view'):
        return user_perms_dict.get(perm_name, {}).get(action) == 1
        
    return dict(has_perm=has_perm)

# ==========================================
# ២. មុខងារកែប្រែអ្នកប្រើប្រាស់ (Edit User)
# ==========================================
@app.route('/edit_user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    full_name = request.form['full_name'].strip()
    username = request.form['username'].strip()
    email = request.form['email'].strip() if request.form.get('email') else None
    phone_number = request.form['phone_number'].strip() if request.form.get('phone_number') else None
    new_role_id = request.form['role_id']
    password = request.form.get('password', '').strip()
    gender = request.form.get('gender')
    telegram_username = request.form['telegram_username'].strip() if request.form.get('telegram_username') else None

    profile_image_name = None
    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            profile_image_name = f"{username}_{filename}"
            upload_folder = os.path.join('static', 'uploads', 'profiles')
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, profile_image_name))

    try:
        # 💡 ឆែកមើលថាតើគាត់បានផ្លាស់ប្តូរ Role ដែរឬទេ?
        cursor.execute("SELECT role_id FROM users WHERE id = %s", (user_id,))
        old_role_id = cursor.fetchone()['role_id']

        # រៀបចំ SQL Update ទិន្នន័យ
        update_fields = [
            "full_name=%s", "username=%s", "email=%s", "phone_number=%s", 
            "role_id=%s", "gender=%s", "telegram_username=%s"
        ]
        params = [full_name, username, email, phone_number, new_role_id, gender, telegram_username]

        if password:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            update_fields.append("password_hash=%s")
            params.append(hashed_pw)
            
        if profile_image_name:
            update_fields.append("profile_image=%s")
            params.append(profile_image_name)

        params.append(user_id) 
        sql = f"UPDATE users SET {', '.join(update_fields)} WHERE id=%s"
        cursor.execute(sql, tuple(params))

        # 💡 ប្រសិនបើប្តូរ Role យើងត្រូវ Reset សិទ្ធិរបស់គាត់អោយត្រូវតាម Role ថ្មី
        if str(new_role_id) != str(old_role_id):
            cursor.execute("DELETE FROM user_permissions WHERE user_id = %s", (user_id,))
            cursor.execute("SELECT permission_id FROM role_permissions WHERE role_id = %s", (new_role_id,))
            role_perms = cursor.fetchall()
            if role_perms:
                insert_data = [(user_id, rp['permission_id']) for rp in role_perms]
                cursor.executemany("INSERT INTO user_permissions (user_id, permission_id) VALUES (%s, %s)", insert_data)

        conn.commit()
        flash('កែប្រែព័ត៌មានបានជោគជ័យ!', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'មានបញ្ហា: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('manage_users'))

# ==========================================
# ៣. លុប និង ផ្លាស់ប្តូរស្ថានភាព
# ==========================================
@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'loggedin' not in session: return redirect(url_for('login'))
    if user_id == session.get('id'):
        flash('អ្នកមិនអាចលុបគណនីខ្លួនឯងកំពុងប្រើប្រាស់បានទេ!', 'danger')
        return redirect(url_for('manage_users'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM proctor_rooms WHERE user_id = %s", (user_id,))
        cursor.execute("UPDATE counters SET status='Available', current_user_id=NULL WHERE current_user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        flash('លុបគណនី និងទិន្នន័យពាក់ព័ន្ធបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'មានបញ្ហា: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('manage_users'))

@app.route('/toggle_user_status/<int:user_id>/<int:status>', methods=['POST'])
def toggle_user_status(user_id, status):
    if 'loggedin' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_active = %s WHERE id = %s", (status, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    flash('បានផ្លាស់ប្តូរស្ថានភាពគណនីជោគជ័យ!', 'success')
    return redirect(url_for('manage_users'))

# ==========================================
# ផ្នែកគ្រប់គ្រងតួនាទី (Role Management)
# ==========================================

@app.route('/roles', methods=['GET', 'POST'])
def manage_roles():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ១. បង្កើតតួនាទីថ្មី (Add Role)
    if request.method == 'POST':
        name = request.form['name'].strip()
        description = request.form['description'].strip()

        try:
            cursor.execute("INSERT INTO roles (name, description) VALUES (%s, %s)", (name, description))
            conn.commit()
            flash('បន្ថែមតួនាទីថ្មីបានជោគជ័យ!', 'success')
        except mysql.connector.Error as err:
            if err.errno == 1062:
                flash('ឈ្មោះតួនាទីនេះមានរួចហើយ!', 'danger')
            else:
                flash(f'មានបញ្ហា: {str(err)}', 'danger')

    # ២. ទាញយកបញ្ជីតួនាទីទាំងអស់មកបង្ហាញ
    # ដូរពី ORDER BY id ASC ទៅ ORDER BY role_id ASC
    cursor.execute("SELECT * FROM roles ORDER BY role_id ASC")
    roles_list = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template('roles.html', roles=roles_list, full_name=session.get('full_name', ''))

# ៣. កែប្រែតួនាទី (Edit Role)
@app.route('/edit_role/<int:role_id>', methods=['POST'])
def edit_role(role_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    name = request.form['name'].strip()
    description = request.form['description'].strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE roles SET name = %s, description = %s WHERE role_id = %s", (name, description, role_id))
        conn.commit()
        flash('កែប្រែព័ត៌មានតួនាទីបានជោគជ័យ!', 'success')
    except Exception as e:
        flash(f'មានបញ្ហា: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_roles'))

# ៤. លុបតួនាទី (Delete Role)
@app.route('/delete_role/<int:role_id>', methods=['POST'])
def delete_role(role_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM roles WHERE role_id = %s", (role_id,))
        conn.commit()
        flash('លុបតួនាទីបានជោគជ័យ!', 'success')
    except mysql.connector.Error as err:
        # ការពារមិនឱ្យលុបតួនាទីដែលកំពុងមានអ្នកប្រើប្រាស់ (Foreign Key Constraint)
        if err.errno == 1451:
            flash('មិនអាចលុបបានទេ! តួនាទីនេះកំពុងត្រូវបានប្រើប្រាស់ដោយគណនីណាមួយក្នុងប្រព័ន្ធ។', 'danger')
        else:
            flash(f'មានបញ្ហា: {str(err)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_roles'))


import math 

@app.route('/candidates', methods=['GET'])
def manage_candidates():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ១. កែតម្រូវ Session Variables
    user_role = session.get('role_name', '') 
    user_id = session.get('id') 

    # ២. ទាញយកបន្ទប់ដែល Proctor ត្រូវគ្រប់គ្រង
    proctor_assigned_rooms = []
    if user_role and user_role.lower() == 'proctor':
        cursor.execute("SELECT test_room FROM proctor_rooms WHERE user_id = %s", (user_id,))
        rooms_data = cursor.fetchall()
        proctor_assigned_rooms = [r['test_room'] for r in rooms_data]

    # ទាញយកទិន្នន័យសម្រាប់ Dropdown
    cursor.execute("SELECT * FROM sessions ORDER BY session_code DESC")
    sessions_list = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT test_date FROM candidates WHERE test_date IS NOT NULL ORDER BY test_date DESC")
    dates_list = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT exam_session FROM candidates WHERE exam_session IS NOT NULL AND exam_session != '' ORDER BY exam_session ASC")
    times_list = cursor.fetchall()

    # ៣. កំណត់ Dropdown បន្ទប់
    if user_role and user_role.lower() == 'proctor':
        rooms_list = [{'test_room': r} for r in proctor_assigned_rooms]
    else:
        cursor.execute("SELECT DISTINCT test_room FROM candidates WHERE test_room IS NOT NULL ORDER BY test_room ASC")
        rooms_list = cursor.fetchall()

    # ការកំណត់ទំព័រ (Pagination)
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
        
    per_page = 48 
    offset = (page - 1) * per_page

    # ចាប់យកតម្លៃពី Filter (Parameters)
    selected_session = session.get('active_session', '') 
    selected_date = request.args.get('test_date', '')
    selected_time = request.args.get('exam_session', '')
    selected_room = request.args.get('test_room', '')
    search_query = request.args.get('search_query', '').strip()
    attendance_status = request.args.get('present', '')
    min_score_str = request.args.get('min_score', '')
    
    # 💡 ចាប់យកតម្លៃពី Filter លទ្ធផលចុងក្រោយ (ថ្មី)
    status_filter = request.args.get('status_filter', '')

    # តម្រៀប (Sorting)
    sort_by = request.args.get('sort_by', 'application_no') 
    order = request.args.get('order', 'ASC').upper()
    allowed_columns = {'application_no', 'name_en', 'gender', 'dob', 'id_card_no', 'score', 'SeatNo'}
    if sort_by not in allowed_columns:
        sort_by = 'application_no'
    if order not in ['ASC', 'DESC']:
        order = 'ASC'
    
    # បង្ខំ Select បន្ទប់ដោយស្វ័យប្រវត្តិ សម្រាប់ Proctor
    if user_role and user_role.lower() == 'proctor' and proctor_assigned_rooms:
        if len(proctor_assigned_rooms) == 1:
            selected_room = proctor_assigned_rooms[0]
        elif selected_room not in proctor_assigned_rooms:
            selected_room = proctor_assigned_rooms[0]

    # ==========================================
    # រៀបចំ SQL WHERE Clauses រួមមួយ
    # ==========================================
    where_base = "WHERE 1=1"
    params = []

    if selected_session:
        where_base += " AND c.session_code = %s"
        params.append(selected_session)

    # ចាក់សោរទិន្នន័យ (Security)
    if user_role and user_role.lower() == 'proctor':
        if proctor_assigned_rooms:
            format_strings = ','.join(['%s'] * len(proctor_assigned_rooms))
            where_base += f" AND c.test_room IN ({format_strings})"
            params.extend(proctor_assigned_rooms)
        else:
            where_base += " AND 1=0" 
    else:
        if selected_room:
            where_base += " AND c.test_room = %s"
            params.append(selected_room)

    # Filter ទូទៅ
    if selected_date:
        where_base += " AND c.test_date = %s"
        params.append(selected_date)
    if selected_time:
        where_base += " AND c.exam_session = %s"
        params.append(selected_time)

    if attendance_status == '1':
        where_base += " AND c.is_present = 1"
    elif attendance_status == '0':
        where_base += " AND c.is_present = 0"
    elif attendance_status == 'none':
        where_base += " AND c.is_present IS NULL"

    # 💡 បន្ថែមលក្ខខណ្ឌ Filter សម្រាប់ "លទ្ធផលចុងក្រោយ" (ថ្មី)
    if status_filter == 'final_passer':
        where_base += " AND c.is_final_passer = 1"
    elif status_filter == 'skill_test_failed':
        where_base += " AND c.is_present = 1 AND c.is_final_passer = 0"

    if search_query:
        where_base += " AND (c.application_no LIKE %s OR c.name_en LIKE %s OR c.id_card_no LIKE %s OR c.passport_no LIKE %s)"
        s_term = f"%{search_query}%"
        params.extend([s_term, s_term, s_term, s_term])

    # 💡 បន្ថែម Filter សម្រាប់រាប់អ្នកជាប់ពិន្ទុ
    total_passed = 0
    female_passed = 0
    min_score_val = None

    if min_score_str:
        try:
            min_score_val = float(min_score_str)
            # បង្កើត WHERE clause ដាច់ដោយឡែកសម្រាប់រាប់ចំនួន (Count) ប៉ុន្តែផ្អែកលើ Filter ដើម
            count_where = where_base + " AND c.score >= %s"
            count_params = params.copy()
            count_params.append(min_score_val)

            # រាប់ចំនួនអ្នកជាប់សរុប និងអ្នកជាប់ជាស្ត្រី
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as t_pass, 
                    SUM(CASE WHEN c.gender='F' THEN 1 ELSE 0 END) as f_pass 
                FROM candidates c 
                {count_where}
            """, tuple(count_params))
            
            result = cursor.fetchone()
            if result:
                total_passed = result['t_pass'] or 0
                female_passed = result['f_pass'] or 0
                
        except ValueError:
            pass # មិនធ្វើអ្វីសោះ បើវាយមិនមែនជាតួលេខ

    # ==========================================
    # រាប់ចំនួនទិន្នន័យសរុប (Total Records & Females)
    # ==========================================
    cursor.execute(f"SELECT COUNT(*) as total FROM candidates c {where_base}", tuple(params))
    total_records = cursor.fetchone()['total']
    total_pages = math.ceil(total_records / per_page) if total_records > 0 else 1

    cursor.execute(f"SELECT COUNT(*) as total_female FROM candidates c {where_base} AND c.gender = 'F'", tuple(params))
    total_female_row = cursor.fetchone()
    total_female = total_female_row['total_female'] if total_female_row else 0

    # ==========================================
    # ទាញយកទិន្នន័យបេក្ខជនទាំងអស់សម្រាប់បង្ហាញលើតារាង
    # ==========================================
    query_select = f"""
        SELECT c.*, cr.status as req_status, cr.correction_note, cr.seat_no as req_seat_no 
        FROM candidates c
        LEFT JOIN change_requests cr ON c.application_no = cr.application_no AND cr.status = 'Pending'
        {where_base} 
        ORDER BY c.{sort_by} {order}
        LIMIT %s OFFSET %s
    """
    cursor.execute(query_select, tuple(params + [per_page, offset]))
    candidates_list = cursor.fetchall()

    cursor.close()
    conn.close()

    # បញ្ជូនអថេរទាំងអស់ រួមទាំងអថេរថ្មីទៅឱ្យ HTML វិញ
    return render_template('candidates.html', 
                           sessions=sessions_list, dates=dates_list, rooms=rooms_list,
                           times=times_list, 
                           candidates=candidates_list, page=page, total_pages=total_pages, 
                           total_records=total_records, total_female=total_female,
                           selected_session=selected_session, 
                           selected_date=selected_date, selected_time=selected_time, 
                           selected_room=selected_room, search_query=search_query,
                           sort_by=sort_by, order=order, 
                           attendance_status=attendance_status, 
                           full_name=session.get('full_name', ''),
                           user_role=user_role,
                           min_score=min_score_str,
                           total_passed=total_passed,
                           female_passed=female_passed,
                           status_filter=status_filter) # 💡 បញ្ជូនអថេរ status_filter ទៅ UI វិញ
# មុខងារចុចនាឡិកាពណ៌ខៀវ ដើម្បីប្តូរស្ថានភាពវត្តមាន (Toggle)
@app.route('/toggle_attendance/<application_no>', methods=['POST'])
def toggle_attendance(application_no):
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'សូមចូលប្រព័ន្ធជាមុនសិន!'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT is_present FROM candidates WHERE application_no = %s", (application_no,))
        candidate = cursor.fetchone()

        if candidate:
            current_status = candidate['is_present']

            if current_status == 0 or current_status == 1:
                # ករណីប្តូរមក "រង់ចាំ" វិញ -> ដកវត្តមាន, លុបលេខតុ និងលុបសំណើចោល
                cursor.execute("UPDATE candidates SET is_present = NULL, SeatNo = NULL WHERE application_no = %s", (application_no,))
                cursor.execute("DELETE FROM change_requests WHERE application_no = %s AND status = 'Pending'", (application_no,))
            else:
                # ករណីចុចដាក់ "វត្តមាន" ដោយផ្ទាល់
                cursor.execute("UPDATE candidates SET is_present = 1 WHERE application_no = %s", (application_no,))

            conn.commit()
            return jsonify({'status': 'success'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

# ==========================================
# ផ្នែកគ្រប់គ្រងការដាក់ពិន័យ (Blacklist Management)
# ==========================================

@app.route('/manage_penalties', methods=['GET'])
def manage_penalties():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # ទាញយកបញ្ជីបេក្ខជនដែលកំពុងជាប់ពិន័យទាំងអស់
    cursor.execute("""
        SELECT application_no, name_en, ban_reason, ban_until 
        FROM candidates 
        WHERE is_banned = TRUE 
        ORDER BY name_en ASC
    """)
    banned_candidates = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('penalties.html', 
                           banned_candidates=banned_candidates, 
                           full_name=session.get('full_name', ''))

@app.route('/add_penalty', methods=['POST'])
def add_penalty():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    app_no = request.form.get('application_no').strip()
    reason = request.form.get('ban_reason').strip()
    is_permanent = request.form.get('is_permanent') # ទទួលតម្លៃពី Checkbox
    ban_until = request.form.get('ban_until')
    
    if not app_no or not reason:
        flash("សូមបញ្ចូលលេខកូដបេក្ខជន និងមូលហេតុឱ្យបានត្រឹមត្រូវ!", "danger")
        return redirect(url_for('manage_penalties'))
        
    # បើគូសធីក "ពិន័យរហូត" នោះ ban_until នឹងក្លាយជា NULL ក្នុង Database
    final_ban_date = None if is_permanent else ban_until
    
    if not is_permanent and not ban_until:
        flash("សូមជ្រើសរើសថ្ងៃផុតកំណត់ ឬគូសធីក 'ពិន័យរហូត'!", "warning")
        return redirect(url_for('manage_penalties'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # ឆែកមើលថាតើមានលេខកូដនេះក្នុងប្រព័ន្ធឬទេ
    cursor.execute("SELECT name_en FROM candidates WHERE application_no = %s", (app_no,))
    candidate = cursor.fetchone()
    
    if candidate:
        cursor.execute("""
            UPDATE candidates 
            SET is_banned = TRUE, ban_reason = %s, ban_until = %s 
            WHERE application_no = %s
        """, (reason, final_ban_date, app_no))
        conn.commit()
        flash(f"បានបញ្ចូលបេក្ខជន {candidate['name_en']} ទៅក្នុងបញ្ជីខ្មៅដោយជោគជ័យ!", "success")
    else:
        flash("រកមិនឃើញលេខកូដបេក្ខជននេះទេ! សូមពិនិត្យម្តងទៀត។", "danger")
        
    cursor.close()
    conn.close()
    return redirect(url_for('manage_penalties'))

@app.route('/revoke_penalty/<app_no>', methods=['POST'])
def revoke_penalty(app_no):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    # ដកបម្រាម ដោយលុបតម្លៃពិន័យចោលវិញ
    cursor.execute("""
        UPDATE candidates 
        SET is_banned = FALSE, ban_reason = NULL, ban_until = NULL 
        WHERE application_no = %s
    """, (app_no,))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash(f"បានដកការដាក់ពិន័យសម្រាប់កូដ {app_no} ដោយជោគជ័យ!", "success")
    return redirect(url_for('manage_penalties'))

# ១. មុខងារកំណត់អវត្តមាន (Mark Absent)
@app.route('/mark_absent', methods=['POST'])
def mark_absent():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'សូមចូលប្រព័ន្ធជាមុនសិន!'})

    data = request.get_json()
    app_no = data.get('application_no')
    seat_no = data.get('seat_no')

    if not app_no or not seat_no:
        return jsonify({'status': 'error', 'message': 'ទិន្នន័យមិនគ្រប់គ្រាន់!'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # កំណត់ថាអវត្តមាន និងរក្សាទុកលេខតុ
        cursor.execute("UPDATE candidates SET is_present = 0, SeatNo = %s WHERE application_no = %s", (seat_no, app_no))
        
        # 💡 លុបសំណើកែប្រែចោល ព្រោះគាត់មិនបានចូលប្រឡងទេ (ទោះស្នើកែពីមុនក៏ចាត់ទុកជាមោឃៈ)
        cursor.execute("DELETE FROM change_requests WHERE application_no = %s AND status = 'Pending'", (app_no,))
        
        conn.commit()
        return jsonify({'status': 'success', 'message': 'បានកំណត់អវត្តមានជោគជ័យ'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

# ២. មុខងារស្នើកែព័ត៌មាន (Request Correction)

@app.route('/request_correction', methods=['POST'])
def request_correction():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'សូមចូលប្រព័ន្ធជាមុនសិន!'})

    data = request.get_json()
    app_no = data.get('application_no')
    seat_no = data.get('seat_no')
    correction_note = data.get('correction_note')

    if not app_no:
        return jsonify({'status': 'error', 'message': 'រកមិនឃើញលេខកូដបេក្ខជន!'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # ១. Update លេខតុចូលទៅកាន់តារាង candidates 
        if seat_no:
            cursor.execute("UPDATE candidates SET SeatNo = %s WHERE application_no = %s", (seat_no, app_no))

        # ២. លុបរាល់សំណើចាស់ៗ (Pending) របស់បេក្ខជននេះចោលសិន
        cursor.execute("DELETE FROM change_requests WHERE application_no = %s AND status = 'Pending'", (app_no,))

        # 💡 ៣. បង្កើតសំណើថ្មី (លុប requested_by ចេញដើម្បីឱ្យត្រូវនឹង Database របស់អ្នក)
        cursor.execute("""
            INSERT INTO change_requests (application_no, seat_no, correction_note, status) 
            VALUES (%s, %s, %s, 'Pending')
        """, (app_no, seat_no, correction_note))

        conn.commit()
        return jsonify({'status': 'success', 'message': 'សំណើត្រូវបានរក្សាទុកជោគជ័យ'})

    except Exception as e:
        conn.rollback() 
        return jsonify({'status': 'error', 'message': f'មានបញ្ហាទិន្នន័យ: {str(e)}'})
    finally:
        cursor.close()
        conn.close()
    
    
    
@app.route('/admin/requests', methods=['GET'])
def admin_requests():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    status_filter = request.args.get('status', 'Pending') 
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search_query = request.args.get('search_query', '').strip()

    # ==========================================
    # 💡 ផ្នែកទី ១.១៖ សង្ខេបព័ត៌មាន "ថ្ងៃនេះ" (Today)
    # ==========================================
    cursor.execute("""
        SELECT 
            COUNT(cr.id) as total_today,
            SUM(CASE WHEN c.gender = 'F' THEN 1 ELSE 0 END) as total_female_today,
            SUM(CASE WHEN cr.status = 'Pending' THEN 1 ELSE 0 END) as pending_today,
            SUM(CASE WHEN cr.status = 'Pending' AND c.gender = 'F' THEN 1 ELSE 0 END) as pending_female_today,
            SUM(CASE WHEN cr.status = 'Approved' THEN 1 ELSE 0 END) as approved_today,
            SUM(CASE WHEN cr.status = 'Approved' AND c.gender = 'F' THEN 1 ELSE 0 END) as approved_female_today,
            SUM(CASE WHEN cr.status = 'Rejected' THEN 1 ELSE 0 END) as rejected_today,
            SUM(CASE WHEN cr.status = 'Rejected' AND c.gender = 'F' THEN 1 ELSE 0 END) as rejected_female_today
        FROM change_requests cr
        LEFT JOIN candidates c ON cr.application_no = c.application_no
        WHERE DATE(cr.created_at) = CURDATE()
    """)
    today_summary = cursor.fetchone() or {}

    # ==========================================
    # 💡 ផ្នែកទី ១.២៖ សង្ខេបព័ត៌មាន "គ្រប់ថ្ងៃទាំងអស់" (All-Time)
    # ==========================================
    cursor.execute("""
        SELECT 
            COUNT(cr.id) as total_all,
            SUM(CASE WHEN c.gender = 'F' THEN 1 ELSE 0 END) as total_female_all,
            SUM(CASE WHEN cr.status = 'Pending' THEN 1 ELSE 0 END) as pending_all,
            SUM(CASE WHEN cr.status = 'Pending' AND c.gender = 'F' THEN 1 ELSE 0 END) as pending_female_all,
            SUM(CASE WHEN cr.status = 'Approved' THEN 1 ELSE 0 END) as approved_all,
            SUM(CASE WHEN cr.status = 'Approved' AND c.gender = 'F' THEN 1 ELSE 0 END) as approved_female_all,
            SUM(CASE WHEN cr.status = 'Rejected' THEN 1 ELSE 0 END) as rejected_all,
            SUM(CASE WHEN cr.status = 'Rejected' AND c.gender = 'F' THEN 1 ELSE 0 END) as rejected_female_all
        FROM change_requests cr
        LEFT JOIN candidates c ON cr.application_no = c.application_no
    """)
    all_time_summary = cursor.fetchone() or {}

    # ==========================================
    # ផ្នែកទី ២៖ ទាញយកបញ្ជីសំណើទាំងអស់ (Query ដើម)
    # ==========================================
    query = "SELECT * FROM change_requests WHERE 1=1"
    params = []
    
    if status_filter != 'All':
        query += " AND status = %s"
        params.append(status_filter)
        
    if start_date and end_date:
        query += " AND DATE(created_at) BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    elif start_date:
        query += " AND DATE(created_at) >= %s"
        params.append(start_date)
    elif end_date:
        query += " AND DATE(created_at) <= %s"
        params.append(end_date)
        
    if search_query:
        query += " AND (application_no LIKE %s OR correction_note LIKE %s)"
        s_term = f"%{search_query}%"
        params.extend([s_term, s_term])
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, tuple(params))
    requests_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin_requests.html', 
                           requests=requests_list, 
                           today_summary=today_summary, 
                           all_time_summary=all_time_summary, # 💡 បញ្ជូនអថេរថ្មីនេះទៅ HTML
                           status_filter=status_filter, 
                           start_date=start_date,
                           end_date=end_date,
                           search_query=search_query,
                           full_name=session.get('full_name', ''))


@app.route('/admin/process_request', methods=['POST'])
def process_request():
    if 'loggedin' not in session:
        return {"status": "error", "message": "សូម Login ជាមុនសិន!"}
        
    data = request.json
    req_id = data.get('id')
    status = data.get('status') # អាចជា 'Approved', 'Rejected', ឬ 'Deleted'
    admin_name = session.get('full_name', 'Admin') 
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM change_requests WHERE id = %s", (req_id,))
        req_data = cursor.fetchone()
        
        if not req_data:
            return {"status": "error", "message": "រកមិនឃើញសំណើនេះទេ!"}

        app_no = req_data.get('application_no')

        # 💡 ទាញយកទិន្នន័យពី candidates ទុកជា backup ការពារក្រែងលោតារាង change_requests ខ្វះទិន្នន័យ
        cursor.execute("""
            SELECT name_en, gender, dob, id_card_no, test_date, test_room, exam_session 
            FROM candidates WHERE application_no = %s
        """, (app_no,))
        candidate_data = cursor.fetchone() or {}

        # ករណីទី១៖ បើចុច "យល់ព្រម" (Approve)
        if status == 'Approved':
            note = req_data.get('correction_note', '')
            
            if candidate_data:
                cursor.execute("""
                    INSERT INTO candidates_history 
                    (application_no, name_en, gender, dob, id_card_no, test_date, test_room, exam_session, history_action, history_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'BEFORE_UPDATE', %s)
                """, (
                    app_no, candidate_data.get('name_en'), candidate_data.get('gender'), 
                    candidate_data.get('dob'), candidate_data.get('id_card_no'), 
                    candidate_data.get('test_date'), candidate_data.get('test_room'), 
                    candidate_data.get('exam_session'), admin_name
                ))
            
            # Update ចូល candidates
            matches = re.findall(r'\[(.*?)\s*ពី:.*?ទៅជា:\s*(.*?)\]', note)
            updates = []
            values = []
            for field, new_val in matches:
                field = field.strip()
                new_val = new_val.strip()
                if 'ឈ្មោះ' in field: updates.append("name_en = %s"); values.append(new_val)
                elif 'ភេទ' in field: updates.append("gender = %s"); values.append(new_val)
                elif 'ថ្ងៃកំណើត' in field: updates.append("dob = %s"); values.append(new_val)
                elif 'ID' in field or 'Passport' in field: updates.append("id_card_no = %s"); values.append(new_val)
            
            if updates:
                query = f"UPDATE candidates SET {', '.join(updates)} WHERE application_no = %s"
                values.append(app_no)
                cursor.execute(query, tuple(values))

        # រៀបចំទិន្នន័យបញ្ចូលប្រវត្តិ ដោយប្រើ .get() ការពារ Error (បើគ្មានទាញយកពី candidate_data ជំនួស)
        seat_no = req_data.get('seat_no') or req_data.get('SeatNo')
        test_date = req_data.get('test_date') or candidate_data.get('test_date')
        exam_session = req_data.get('exam_session') or candidate_data.get('exam_session')
        test_room = req_data.get('test_room') or candidate_data.get('test_room')
        correction_note = req_data.get('correction_note', '')

        # ករណីទី២៖ បើចុច "បោះបង់" (Deleted)
        if status == 'Deleted':
            cursor.execute("""
                INSERT INTO change_requests_history 
                (application_no, seat_no, test_date, exam_session, test_room, correction_note, status, history_action, history_by)
                VALUES (%s, %s, %s, %s, %s, %s, 'Deleted', 'ACTION_DISCARDED', %s)
            """, (app_no, seat_no, test_date, exam_session, test_room, correction_note, admin_name))
            
            cursor.execute("DELETE FROM change_requests WHERE id = %s", (req_id,))
            msg = "សំណើត្រូវបានបោះបង់ និងលុបចោលដោយជោគជ័យ!"
            
        # ករណីទី៣៖ បើចុច "បដិសេធ" ធម្មតា
        else:
            cursor.execute("UPDATE change_requests SET status = %s WHERE id = %s", (status, req_id))
            cursor.execute("""
                INSERT INTO change_requests_history 
                (application_no, seat_no, test_date, exam_session, test_room, correction_note, status, history_action, history_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (app_no, seat_no, test_date, exam_session, test_room, correction_note, status, f'ACTION_{status.upper()}', admin_name))
            msg = f"សំណើត្រូវបានកំណត់ជា {status} រួចរាល់!"
        
        conn.commit()
        return {"status": "success", "message": msg}
        
    except Exception as e:
        error_msg = str(e)
        print("Error processing request:", error_msg)
        # 💡 បញ្ជូន Error ពិតប្រាកដទៅកាន់ Browser ឱ្យ Admin មើលឃើញផ្ទាល់ភ្នែក!
        return {"status": "error", "message": f"កំហុស Database: {error_msg}"}
    
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# ==========================================================
# មុខងារ Upload បញ្ជីឈ្មោះបេក្ខជនដើម (UBT ប្រើ File ២)
# ==========================================================
@app.route('/import_data', methods=['GET', 'POST'])
def import_data():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        file_part1 = request.files.get('file_part1')
        file_part2 = request.files.get('file_part2')
        session_code_prefix = request.form.get('session_code').strip()

        if not file_part1 or not file_part2 or not session_code_prefix:
            flash('សូមបញ្ចូល File ទាំង ២ និងជ្រើសរើសវគ្គប្រឡងឱ្យបានត្រឹមត្រូវ!', 'danger')
            return redirect(url_for('import_data'))

        try:
            df1 = pd.read_excel(file_part1) if file_part1.filename.endswith(('.xls', '.xlsx')) else pd.read_csv(file_part1)
            df2 = pd.read_excel(file_part2) if file_part2.filename.endswith(('.xls', '.xlsx')) else pd.read_csv(file_part2)

            df1.columns = df1.columns.str.strip()
            df2.columns = df2.columns.str.strip()

            merge_key = 'Application No' 
            if merge_key not in df1.columns or merge_key not in df2.columns:
                merge_key = 'Receipt No'
                if merge_key not in df1.columns or merge_key not in df2.columns:
                    flash(f'មិនអាចរកឃើញ Column លេខកូដបេក្ខជន ដើម្បីតភ្ជាប់ File ទេ!', 'danger')
                    return redirect(url_for('import_data'))

            merged_df = pd.merge(df1, df2, on=merge_key, how='left')
            
            # បង្កើត List សម្រាប់វេចខ្ចប់ទិន្នន័យបញ្ជូនទៅ Database ម្តងតែម្តង (Bulk Insert)
            values_list = []
            error_list = []
            
            for index, row in merged_df.iterrows():
                raw_app_no = str(row[merge_key]).strip()
                if not raw_app_no or raw_app_no.lower() == 'nan':
                    continue

                last_5_digits = raw_app_no[-5:] 
                full_app_no = f"{session_code_prefix}{last_5_digits}"

                name_en = str(row.get('Name_x', row.get('Name_y', row.get('Name', '')))).strip()
                gender_raw = str(row.get('Gender_x', row.get('Gender_y', row.get('Gender', '')))).strip().upper()
                gender = 'M' if gender_raw.startswith('M') else 'F'
                industry = str(row.get('Type of industry', row.get('Industry', ''))).strip() 

                raw_room = str(row.get('Room', '')).strip()
                test_room = raw_room
                if 'UBT Test room(1)' in raw_room: test_room = 'UBT 1'
                elif 'UBT Test room(2)' in raw_room: test_room = 'UBT 2'
                elif 'UBT Test room(3)' in raw_room: test_room = 'UBT 3'
                elif 'UBT Test room(4)' in raw_room: test_room = 'UBT 4'

                exam_session = str(row.get('Session', '')).strip()
                if exam_session.lower() == 'nan': exam_session = None

                raw_test_date = row.get('Test Date')
                test_date = None
                if pd.notnull(raw_test_date):
                    try:
                        if isinstance(raw_test_date, (int, float)):
                            test_date = pd.to_datetime(raw_test_date, unit='D', origin='1899-12-30').strftime('%Y-%m-%d')
                        else:
                            test_date = pd.to_datetime(raw_test_date).strftime('%Y-%m-%d')
                    except:
                        pass
                
                raw_dob = str(row.get('aplyerBirth', '')).strip()
                dob = None
                if raw_dob and raw_dob.lower() != 'nan' and len(raw_dob.split('.')[0]) == 8: 
                    clean_dob = raw_dob.split('.')[0] 
                    dob = f"{clean_dob[:4]}-{clean_dob[4:6]}-{clean_dob[6:]}"
                
                raw_doc_no = str(row.get('Passport No', '')).strip()
                id_card_no = None
                passport_no = None
                if raw_doc_no and raw_doc_no.lower() != 'nan':
                    if raw_doc_no.upper().startswith('N'):
                        passport_no = raw_doc_no.upper()
                    else:
                        id_card_no = raw_doc_no

                # រៀបចំឈ្មោះរូបថត (គ្រាន់តែឆែកមើលថាមានរូបឬអត់ តែមិនស្កេន AI ទេ ដើម្បីឱ្យលឿន)
                photo_filename = f"{full_app_no}_PT.png"
                photo_path = os.path.join(app.config['PHOTO_FOLDER'], photo_filename)
                
                if not os.path.exists(photo_path):
                    error_list.append(f"បាត់រូបថត: {photo_filename}")

                # វេចខ្ចប់ទិន្នន័យ១ជួរ ដាក់ចូលទៅក្នុង List
                values_list.append((
                    full_app_no, session_code_prefix, name_en, gender, dob, industry, 
                    test_room, test_date, exam_session, id_card_no, passport_no, 
                    photo_filename, None, None 
                ))

            # បញ្ជូនទិន្នន័យរាប់ពាន់ជួរទៅក្នុង Database
            if values_list:
                sql = """
                    INSERT INTO candidates 
                    (application_no, session_code, name_en, gender, dob, industry, test_room, test_date, exam_session, id_card_no, passport_no, original_photo_path, face_encoding, is_present)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    session_code = VALUES(session_code), name_en = VALUES(name_en), gender = VALUES(gender),
                    dob = VALUES(dob), industry = VALUES(industry), test_room = VALUES(test_room),
                    test_date = VALUES(test_date), exam_session = VALUES(exam_session),
                    id_card_no = VALUES(id_card_no), passport_no = VALUES(passport_no),
                    original_photo_path = VALUES(original_photo_path),
                    is_present = VALUES(is_present)
                """
                
                chunk_size = 500
                for i in range(0, len(values_list), chunk_size):
                    chunk = values_list[i:i + chunk_size]
                    cursor.executemany(sql, chunk) 
                    conn.commit() 

            flash(f'ទាញបញ្ចូលទិន្នន័យបានសម្រេច! ចំនួនបេក្ខជនសរុប៖ {len(values_list)} នាក់។', 'success')
            
            if error_list:
                short_errors = error_list[:10]
                more = f" និង {len(error_list) - 10} នាក់ទៀត..." if len(error_list) > 10 else ""
                flash(f'ចំណាំ: មានបេក្ខជន {len(error_list)} នាក់ មិនទាន់មានរូបថតយោង (ឧ. {", ".join(short_errors)}{more})', 'warning') 

        except Exception as e:
            flash(f'មានបញ្ហាក្នុងការអាន File Excel: {str(e)}', 'danger')
            if conn.is_connected():
                cursor.close()
                conn.close()
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

    # ទាញយកបញ្ជីវគ្គប្រឡងមកបង្ហាញវិញ
    cursor.execute("SELECT * FROM sessions ORDER BY session_code DESC")
    sessions_list = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('import_data.html', sessions=sessions_list, full_name=session.get('full_name', ''))

# ==========================================================
# មុខងារបង្ហាញទំព័រ Upload បញ្ជីឈ្មោះតេស្តជំនាញ
# ==========================================================
@app.route('/import_skill_test', methods=['GET'])
def import_skill_test_page():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    return render_template('import_skill_test_data.html', full_name=session.get('full_name', ''), role_name=session.get('role_name', 'System Admin'))

# ==========================================================
# មុខងារ Upload បញ្ជីឈ្មោះអ្នកតេស្តជំនាញ (2nd Round Skill Test)
# ==========================================================
@app.route('/import_skill_test_data', methods=['POST'])
def import_skill_test_data():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('សូមជ្រើសរើសឯកសារជាមុនសិន!', 'danger')
        return redirect(request.referrer or url_for('dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('មិនមានឯកសារត្រូវបានជ្រើសរើសទេ!', 'danger')
        return redirect(request.referrer)

    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls') or file.filename.endswith('.csv')):
        try:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            if file.filename.endswith('.csv'):
                df = pd.read_csv(filepath, dtype=str)
            else:
                df = pd.read_excel(filepath, dtype=str)

            df = df.where(pd.notnull(df), None)

            conn = get_db_connection()
            cursor = conn.cursor()

            success_count = 0
            
            # 💡 កែប្រែ Query: បន្ថែម is_final_passer និងកំណត់តម្លៃវាទៅជា NULL ជានិច្ចពេល Import ដំបូង
            insert_query = """
                INSERT INTO skill_test_candidates (
                    application_no, second_test_register_no, gender, dob, name_en, 
                    test_date, entry_time, group_no, seat_no, specialized_tasks, cardio_test, is_present, is_final_passer
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL)
                ON DUPLICATE KEY UPDATE
                    second_test_register_no=VALUES(second_test_register_no),
                    test_date=VALUES(test_date),
                    entry_time=VALUES(entry_time),
                    group_no=VALUES(group_no),
                    seat_no=VALUES(seat_no),
                    specialized_tasks=VALUES(specialized_tasks),
                    cardio_test=VALUES(cardio_test),
                    is_final_passer=NULL
            """

            for index, row in df.iterrows():
                app_no_col = [col for col in df.columns if 'EPS-TOPIK Register No' in str(col)]
                if not app_no_col: continue 
                
                app_no = str(row[app_no_col[0]]).strip()
                if not app_no or app_no == 'None': continue

                def get_val(keyword):
                    col = [c for c in df.columns if keyword.lower() in str(c).lower()]
                    val = str(row[col[0]]).strip() if col and row[col[0]] is not None else None
                    return val if val != 'None' else None

                sec_reg_no = get_val('2nd Test Register No')
                gender = get_val('Gender')
                
                dob_raw = get_val('Birth Date')
                dob_formatted = None
                if dob_raw:
                    try:
                        dob_formatted = pd.to_datetime(dob_raw).strftime('%Y-%m-%d')
                    except:
                        dob_formatted = dob_raw

                name = get_val('Name')
                
                test_date_raw = get_val('Test Date')
                test_date_formatted = None
                if test_date_raw:
                    try:
                        test_date_formatted = pd.to_datetime(test_date_raw).strftime('%Y-%m-%d')
                    except:
                        test_date_formatted = test_date_raw

                entry_time = get_val('Entry Time')
                group_no = get_val('Group No')
                seat_no = get_val('Seat No')
                spec_tasks = get_val('Specialized tasks')
                cardio = get_val('Cardio test')

                # បញ្ជូន Parameter ចំនួន ១១ ទៅកាន់ Query ខាងលើ
                cursor.execute(insert_query, (
                    app_no, sec_reg_no, gender, dob_formatted, name,
                    test_date_formatted, entry_time, group_no, seat_no, spec_tasks, cardio
                ))
                success_count += 1

            conn.commit()
            cursor.close()
            conn.close()

            flash(f'✅ ជោគជ័យ! ទិន្នន័យបេក្ខជនចំនួន {success_count} នាក់ ត្រូវបានបញ្ជូលទៅក្នុងបញ្ជីតេស្តជំនាញ។', 'success')
            
        except Exception as e:
            import traceback
            traceback.print_exc() 
            flash(f'❌ មានបញ្ហាក្នុងការបញ្ចូលទិន្នន័យ៖ {str(e)}', 'danger')

        return redirect(request.referrer)
    else:
        flash('❌ សូមបញ្ជូលឯកសារជាទម្រង់ .xlsx, .xls, ឬ .csv ប៉ុណ្ណោះ។', 'danger')
        return redirect(request.referrer)

# ==========================================================
# ទំព័រគ្រប់គ្រងបញ្ជីឈ្មោះអ្នកប្រឡងតេស្តជំនាញ (Skill Test Candidates)
# ==========================================================
import math
from datetime import datetime, timezone, timedelta # 💡 កែប្រែការ Import ត្រង់នេះ

@app.route('/skill_test_candidates', methods=['GET'])
def manage_skill_test_candidates():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    user_role = session.get('role_name', '') 
    
    # ទាញយកទិន្នន័យសម្រាប់ Dropdown Filter
    cursor.execute("SELECT * FROM sessions ORDER BY session_code DESC")
    sessions_list = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT test_date FROM skill_test_candidates WHERE test_date IS NOT NULL ORDER BY test_date DESC")
    dates_list = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT entry_time FROM skill_test_candidates WHERE entry_time IS NOT NULL ORDER BY entry_time ASC")
    times_list = cursor.fetchall()
    
    # 🌟 កែសម្រួលការ Sort Group No អោយត្រូវតាមលំដាប់លេខ 🌟
    cursor.execute("SELECT DISTINCT group_no FROM skill_test_candidates WHERE group_no IS NOT NULL ORDER BY LENGTH(group_no) ASC, group_no ASC")
    groups_list = cursor.fetchall()

    # ==============================================================
    # 💡 ផ្នែកគ្រប់គ្រង Filter (ដោះស្រាយបញ្ហា Timezone លើ VPS)
    # ==============================================================
    # កំណត់តំបន់ម៉ោងកម្ពុជា (UTC+7) ជាដាច់ខាត ដើម្បីកុំឱ្យជាន់ម៉ោង Server
    cambodia_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(cambodia_tz).strftime('%Y-%m-%d')
    
    raw_selected_date = request.args.get('test_date')
    
    # ពិនិត្យមើលថាតើគួរប្រើថ្ងៃណាជាលំនាំដើម
    if raw_selected_date is None: 
        # បើទើបបើកទំព័រដំបូង (អត់មានប៉ារ៉ាម៉ែត្រ) ប្រើថ្ងៃនេះរបស់កម្ពុជា
        selected_date = today_str
    elif raw_selected_date == 'all': 
        # បើគាត់ចុចរើសយក "ទាំងអស់" នោះយើងឱ្យវាទទេ ដើម្បីកុំឱ្យវា Filter ថ្ងៃ
        selected_date = ''
    else:
        # បើគាត់រើសថ្ងៃជាក់លាក់ណាមួយ គឺយកថ្ងៃនោះ
        selected_date = raw_selected_date

    selected_session = session.get('active_session', '') 
    selected_time = request.args.get('entry_time', '')
    selected_group = request.args.get('group_no', '')
    search_query = request.args.get('search_query', '').strip()
    attendance_status = request.args.get('present', '')
    status_filter = request.args.get('status_filter', '')

    # ការកំណត់ទំព័រ (Pagination)
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    per_page = 48 
    offset = (page - 1) * per_page

    # ==============================================================
    # 💡 ផ្នែករៀបចំ Query ទាញយកទិន្នន័យ
    # ==============================================================
    query_base = """
        FROM skill_test_candidates stc
        JOIN candidates c ON stc.application_no = c.application_no
        WHERE 1=1
    """
    params = []

    if selected_session:
        query_base += " AND c.session_code = %s"
        params.append(selected_session)
        
    # ប្រើប្រាស់ selected_date បន្ទាប់ពីការកំណត់លក្ខខណ្ឌរួចរាល់
    if selected_date:
        query_base += " AND stc.test_date = %s"
        params.append(selected_date)
        
    if selected_time:
        query_base += " AND stc.entry_time = %s"
        params.append(selected_time)
        
    if selected_group:
        query_base += " AND stc.group_no = %s"
        params.append(selected_group)

    if attendance_status == '1':
        query_base += " AND stc.is_present = 1"
    elif attendance_status == '0':
        query_base += " AND stc.is_present = 0"

    if status_filter == 'final_passer':
        query_base += " AND stc.is_final_passer = 1"
    elif status_filter == 'skill_test_failed':
        query_base += " AND stc.is_present = 1 AND stc.is_final_passer = 0"

    if search_query:
        query_base += " AND (stc.application_no LIKE %s OR stc.name_en LIKE %s OR stc.second_test_register_no LIKE %s)"
        s_term = f"%{search_query}%"
        params.extend([s_term, s_term, s_term])

    # រាប់ចំនួនទិន្នន័យសរុប (Total Records)
    cursor.execute(f"SELECT COUNT(*) as total {query_base}", tuple(params))
    total_records = cursor.fetchone()['total']
    total_pages = math.ceil(total_records / per_page) if total_records > 0 else 1

    # រាប់ចំនួនសិស្សស្រី (Total Females)
    cursor.execute(f"SELECT COUNT(*) as total_f {query_base} AND stc.gender = 'F'", tuple(params))
    total_female_row = cursor.fetchone()
    total_female = total_female_row['total_f'] if total_female_row else 0

    # 🌟 ទាញយកទិន្នន័យជាក់ស្តែង និង កែសម្រួលការ Sort អោយបានត្រឹមត្រូវ 🌟
    query_select = f"""
        SELECT stc.*, c.original_photo_path, c.session_code 
        {query_base} 
        ORDER BY 
            LENGTH(stc.group_no) ASC, stc.group_no ASC, 
            LENGTH(stc.seat_no) ASC, stc.seat_no ASC
        LIMIT %s OFFSET %s
    """
    
    final_params = params + [per_page, offset]
    cursor.execute(query_select, tuple(final_params))
    candidates_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('skill_test_candidates.html', 
                           sessions=sessions_list, 
                           dates=dates_list, 
                           groups=groups_list, 
                           times=times_list, 
                           candidates=candidates_list, 
                           page=page, 
                           total_pages=total_pages, 
                           total_records=total_records, 
                           total_female=total_female,
                           selected_session=selected_session, 
                           selected_date=selected_date, 
                           selected_time=selected_time, 
                           selected_group=selected_group, 
                           search_query=search_query, 
                           attendance_status=attendance_status, 
                           status_filter=status_filter, 
                           full_name=session.get('full_name', ''), 
                           user_role=user_role,
                           today_date=today_str)

# មុខងារចុចប្តូរវត្តមានដោយដៃ ៣ ជំហាន (3-Way Toggle សម្រាប់តេស្តជំនាញ)
@app.route('/toggle_skill_attendance/<application_no>', methods=['POST'])
def toggle_skill_attendance(application_no):
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'សូមចូលប្រព័ន្ធជាមុនសិន!'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT is_present FROM skill_test_candidates WHERE application_no = %s", (application_no,))
        candidate = cursor.fetchone()
        
        if candidate:
            current_status = candidate['is_present']
            
            # លក្ខខណ្ឌវិលជុំ៖ NULL -> 1 -> 0 -> NULL
            if current_status is None:
                new_status = 1      # ពីរង់ចាំ (NULL) ទៅជា វត្តមាន (1)
            elif current_status == 1:
                new_status = 0      # ពីវត្តមាន (1) ទៅជា អវត្តមាន (0)
            else:
                new_status = None   # ពីអវត្តមាន (0) ត្រឡប់ទៅ រង់ចាំវិញ (NULL)
            
            cursor.execute("UPDATE skill_test_candidates SET is_present = %s, attendance_time = NOW() WHERE application_no = %s", (new_status, application_no))
            conn.commit()
            return jsonify({'status': 'success'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

# ==========================================================
# 💡 API សម្រាប់ដាក់វត្តមានបេក្ខជនទាំងអស់តាមការ Filter (Bulk Update)
# ==========================================================
@app.route('/api/bulk_mark_present', methods=['POST'])
def bulk_mark_present():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'សូមចូលគណនីជាមុនសិន!'})

    data = request.json
    test_date = data.get('test_date')
    entry_time = data.get('entry_time')
    group_no = data.get('group_no')

    # 🔒 ការពារសុវត្ថិភាព៖ ត្រូវតែមាន "ថ្ងៃប្រឡង" ទើបអនុញ្ញាតឱ្យ Update
    if not test_date or test_date == 'all':
        return jsonify({'status': 'error', 'message': 'សូមជ្រើសរើស "ថ្ងៃប្រឡង" ជាក់លាក់ណាមួយជាមុនសិន!'})
    
    # =========================================================
    # 🔒 ចាក់សោរ៖ ឆែកមើលថ្ងៃប្រឡង និង Role របស់ User
    # =========================================================
    from datetime import date
    today_str = date.today().strftime('%Y-%m-%d')
    user_role = session.get('role_name', '').lower()
    # ប្រសិនបើថ្ងៃប្រឡងតូចជាងថ្ងៃនេះ (ថ្ងៃចាស់) ហាមឃាត់អ្នកដែលមិនមែនជា Super Admin
    if test_date < today_str and user_role != 'super admin':
        return jsonify({
            'status': 'error', 
            'message': '🔒 ហាមឃាត់៖ មិនអាចកែប្រែវត្តមានសម្រាប់ថ្ងៃដែលរំលងផុតឡើយ! (មានតែ Super Admin ប៉ុណ្ណោះដែលអាចកែប្រែបាន)'
        })

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 💡 រៀបចំកូដ SQL សម្រាប់ Update (បញ្ចូល attendance_time = NOW() ដូចកូដចាស់)
        # និង Update តែអ្នកដែលមិនទាន់មានវត្តមាន ឬអវត្តមានប៉ុណ្ណោះ
        query = """
            UPDATE skill_test_candidates 
            SET is_present = 1, attendance_time = NOW() 
            WHERE test_date = %s AND (is_present IS NULL OR is_present = 0)
        """
        params = [test_date]

        # បើមានរើសម៉ោង បន្ថែមលក្ខខណ្ឌម៉ោង
        if entry_time:
            query += " AND entry_time = %s"
            params.append(entry_time)
            
        # បើមានរើសក្រុម បន្ថែមលក្ខខណ្ឌក្រុម
        if group_no:
            query += " AND group_no = %s"
            params.append(group_no)

        cursor.execute(query, tuple(params))
        affected_rows = cursor.rowcount # រាប់មើលថា Update ត្រូវប៉ុន្មាននាក់
        conn.commit()

        if affected_rows > 0:
            return jsonify({'status': 'success', 'message': f'បានដាក់វត្តមានបេក្ខជនសរុប {affected_rows} នាក់ ដោយជោគជ័យ!'})
        else:
            return jsonify({'status': 'success', 'message': 'មិនមានបេក្ខជនថ្មីត្រូវដាក់វត្តមានទេ (ឬពួកគេមានវត្តមានរួចហើយ)!'})
            
    except Exception as e:
        conn.rollback()
        print("Bulk Update Error:", e)
        return jsonify({'status': 'error', 'message': 'មានបញ្ហាប្រព័ន្ធពេលកែប្រែទិន្នន័យ!'})
    finally:
        cursor.close()
        conn.close() 

# ==========================================================
# របាយការណ៍បេក្ខជនអវត្តមានប្រចាំថ្ងៃ (Daily Absentee Report)
# ==========================================================
@app.route('/report/daily_attendance', methods=['GET'])
def report_daily_attendance():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    test_date = request.args.get('test_date', '')
    entry_time = request.args.get('entry_time', '')
    group_no = request.args.get('group_no', '')
    
    # 🌟 ១. ចាប់យកចំណងជើងរបាយការណ៍ពី URL (បើគ្មាន ប្រើ Default)
    report_title = request.args.get('report_title', 'របាយការណ៍វត្តមានបេក្ខជនប្រចាំថ្ងៃ (Skill Test)')

    if not test_date:
        flash("សូមជ្រើសរើសថ្ងៃប្រឡងជាមុនសិន", "warning")
        return redirect(url_for('manage_skill_test_candidates'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT stc.*, c.industry 
        FROM skill_test_candidates stc
        LEFT JOIN candidates c ON stc.application_no = c.application_no
        WHERE stc.test_date = %s
    """
    params = [test_date]

    if entry_time:
        query += " AND LEFT(stc.entry_time, 5) = LEFT(%s, 5)"
        params.append(entry_time)
    if group_no:
        query += " AND stc.group_no = %s"
        params.append(group_no)

    query += " ORDER BY CAST(stc.group_no AS UNSIGNED) ASC, CAST(stc.seat_no AS UNSIGNED) ASC"
    
    cursor.execute(query, tuple(params))
    all_candidates = cursor.fetchall()
    
    total_present = 0
    total_absent = 0
    
    # បង្កើត List ថ្មីដើម្បីផ្ទុកតែអ្នកអវត្តមាន
    absent_candidates = []
    
    for c in all_candidates:
        val = c.get('is_present')
        if isinstance(val, bytearray):
            val = ord(val)
            
        if val == 1 or str(val) == '1' or val is True:
            c['clean_present'] = '1'
            total_present += 1
        elif val == 0 or str(val) == '0' or val is False:
            c['clean_present'] = '0'
            total_absent += 1
            absent_candidates.append(c)  # ទាញបញ្ចូលតែអ្នកអវត្តមានប៉ុណ្ណោះ
        else:
            c['clean_present'] = 'none'

    total_candidates = len(all_candidates)

    cursor.close()
    conn.close()

    return render_template('report_daily_attendance_SkillTest.html', 
                           report_title=report_title, # 🌟 ២. បញ្ជូនចំណងជើងទៅ HTML
                           candidates=absent_candidates,
                           test_date=test_date, 
                           entry_time=entry_time, 
                           group_no=group_no,
                           total_candidates=total_candidates,
                           total_present=total_present,
                           total_absent=total_absent)     


# ==========================================================
# របាយការណ៍បេក្ខជនអវត្តមានប្រចាំវេន (Session Absentee Report)
# ==========================================================
@app.route('/report/session_attendance', methods=['GET'])
def report_session_attendance():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    test_date = request.args.get('test_date', '')
    entry_time = request.args.get('entry_time', '')
    
    # 🌟 ១. ចាប់យកចំណងជើងរបាយការណ៍ពី URL (នេះជាកន្លែងដែលវាទាញអក្សរពី URL មក)
    report_title = request.args.get('report_title', 'របាយការណ៍វត្តមានបេក្ខជនប្រចាំវេន (Skill Test)')

    if not test_date or not entry_time:
        flash("សូមជ្រើសរើស ថ្ងៃប្រឡង និង ម៉ោងចូល ជាមុនសិន!", "warning")
        return redirect(url_for('manage_skill_test_candidates'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT stc.*, c.industry 
        FROM skill_test_candidates stc
        LEFT JOIN candidates c ON stc.application_no = c.application_no
        WHERE stc.test_date = %s 
        AND LEFT(stc.entry_time, 5) = LEFT(%s, 5)
        ORDER BY CAST(stc.group_no AS UNSIGNED) ASC, CAST(stc.seat_no AS UNSIGNED) ASC
    """
    cursor.execute(query, (test_date, entry_time))
    all_candidates = cursor.fetchall()
    
    total_present = 0
    total_absent = 0
    total_male = 0
    total_female = 0
    
    # បង្កើត List ថ្មីដើម្បីផ្ទុកតែអ្នកអវត្តមាន
    absent_candidates = []
    
    for c in all_candidates:
        if c.get('gender') == 'M':
            total_male += 1
        elif c.get('gender') == 'F':
            total_female += 1

        val = c.get('is_present')
        if isinstance(val, bytearray):
            val = ord(val)
            
        if val == 1 or str(val) == '1' or val is True:
            c['clean_present'] = '1'
            total_present += 1
        elif val == 0 or str(val) == '0' or val is False:
            c['clean_present'] = '0'
            total_absent += 1
            absent_candidates.append(c) # ទាញបញ្ចូលតែអ្នកអវត្តមានប៉ុណ្ណោះ
        else:
            c['clean_present'] = 'none'

    total_candidates = len(all_candidates)

    cursor.close()
    conn.close()

    return render_template('report_session_attendance_SkillTest.html', 
                           report_title=report_title, # 🌟 ២. បញ្ជូនចំណងជើងដែលចាប់បាន ទៅអោយ HTML
                           candidates=absent_candidates,
                           test_date=test_date, 
                           entry_time=entry_time,
                           total_candidates=total_candidates,
                           total_present=total_present,
                           total_absent=total_absent,
                           total_male=total_male,
                           total_female=total_female)

from datetime import date
import math

# ==========================================================
# ទំព័រស្វែងរកម៉ោង និងលេខតុប្រឡង (Public Page សម្រាប់ស្កេន QR)
# ==========================================================
from datetime import datetime
import pytz
import math

@app.route('/exam_schedule', methods=['GET'])
def exam_schedule():
    # ១. កំណត់ Timezone កម្ពុជាឱ្យបានត្រឹមត្រូវបំផុត
    cambodia_tz = pytz.timezone('Asia/Phnom_Penh')
    now_khmer = datetime.now(cambodia_tz)
    today_date = now_khmer.strftime('%Y-%m-%d')

    # ២. ឆែកមើលសិទ្ធិចូលប្រើប្រាស់ QR (វានឹងយក request.path ទៅឆែកក្នុង DB)
    is_allowed, setting = check_qr_access() 

    if not is_allowed:
        return render_template('qr_closed.html', 
                               message=f"ទំព័រ «{setting['qr_name'] if setting else 'នេះ'}» ត្រូវបានបិទ ឬមិនស្ថិតក្នុងកាលវិភាគកំណត់ឡើយ។",
                               start_time=setting['start_datetime'] if setting else None,
                               end_time=setting['end_datetime'] if setting else None)

    # ៣. ចាប់យកពាក្យស្វែងរក និងទំព័រ (Pagination)
    search_query = request.args.get('search_query', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 24 
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ៤. រៀបចំលក្ខខណ្ឌ (WHERE Clause) ឱ្យស៊ីគ្នាទាំងការរាប់ និងការទាញទិន្នន័យ
    where_clause = ""
    query_params = []

    if search_query:
        where_clause = " AND (stc.application_no LIKE %s OR c.name_en LIKE %s)"
        query_params.extend([f"%{search_query}%", f"%{search_query}%"])
    else:
        where_clause = " AND stc.test_date = %s"
        query_params.append(today_date)

    # ៥. រាប់ចំនួនសរុប (Total Records)
    count_sql = f"""
        SELECT COUNT(*) as total
        FROM skill_test_candidates stc
        LEFT JOIN candidates c ON stc.application_no = c.application_no
        WHERE 1=1 {where_clause}
    """
    cursor.execute(count_sql, tuple(query_params))
    total_records = cursor.fetchone()['total']
    total_pages = math.ceil(total_records / per_page) if total_records > 0 else 1

    # ៦. ទាញយកទិន្នន័យបេក្ខជនតាមទំព័រ
    # បន្ថែម c.gender ទៅក្នុង Select ដើម្បីបង្ហាញ "ប្រុស/ស្រី" លើ Mobile
    data_sql = f"""
        SELECT stc.application_no, c.name_en, c.gender, stc.test_date, stc.entry_time, stc.group_no, stc.seat_no
        FROM skill_test_candidates stc
        LEFT JOIN candidates c ON stc.application_no = c.application_no
        WHERE 1=1 {where_clause}
        ORDER BY stc.test_date ASC, 
                 LEFT(stc.entry_time, 5) ASC, 
                 CAST(stc.group_no AS UNSIGNED) ASC, 
                 CAST(stc.seat_no AS UNSIGNED) ASC
        LIMIT %s OFFSET %s
    """
    
    # បន្ថែម limit និង offset ចូលទៅក្នុង params
    data_params = query_params + [per_page, offset]
    cursor.execute(data_sql, tuple(data_params))
    candidates = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('public_exam_schedule.html',
                           candidates=candidates,
                           today_date=today_date,
                           search_query=search_query,
                           page=page,
                           total_pages=total_pages,
                           per_page=per_page)

@app.route('/reset_face_data/<app_no>', methods=['POST'])
def reset_face_data(app_no):
    if 'loggedin' not in session:
        return jsonify({"status": "error", "message": "សូម Login!"})
        
    conn = get_db_connection()
    cursor = conn.cursor()
    # លុប Encoding ចាស់ និងរូបភាពចាស់ចេញ ដើម្បីបង្ខំឱ្យបេក្ខជនស្កេនថ្មី
    cursor.execute("UPDATE candidates SET face_encoding = NULL, latest_scan_photo = NULL WHERE application_no = %s", (app_no,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"status": "success", "message": "បាន Reset ទិន្នន័យផ្ទៃមុខជោគជ័យ"})        

import time # បន្ថែម module នេះនៅខាងលើបង្អស់នៃ app.py បើមិនទាន់មាន

# ==========================================================
# មុខងារសម្រាប់ថតរូបថ្មី និង Update ទិន្នន័យមុខចូល Folder latest_scans
# ==========================================================
@app.route('/api/update_candidate_photo', methods=['POST'])
def update_candidate_photo():
    if 'loggedin' not in session:
        return {"status": "error", "message": "មិនទាន់ Login!"}, 401

    data = request.json
    app_no = data.get('application_no')
    image_data = data.get('image')

    if not app_no or not image_data:
        return {"status": "error", "message": "ទិន្នន័យមិនគ្រប់គ្រាន់"}

    try:
        # ១. ដំណើរការរូបភាពពីកាមេរ៉ា (Webcam)
        image_bytes = base64.b64decode(image_data.split(',')[1])
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        image.thumbnail((600, 600))
        unknown_image = np.array(image)
        
        # ស្កេនរកផ្ទៃមុខក្នុងរូបថតថ្មី
        face_locations = face_recognition.face_locations(unknown_image)
        if len(face_locations) == 0:
            return {"status": "error", "message": "មិនឃើញមុខក្នុងរូបថតថ្មីទេ! សូមឱ្យបេក្ខជនមើលចំកាមេរ៉ា។"}
            
        unknown_encodings = face_recognition.face_encodings(unknown_image, known_face_locations=face_locations)
        face_encoding_json = json.dumps(unknown_encodings[0].tolist())

        # ២. 💡 រៀបចំឈ្មោះរូបថត និងទីតាំងរក្សាទុកឱ្យច្បាស់លាស់ (Target Folder)
        import time
        import os
        
        timestamp = int(time.time())
        new_filename = f"{app_no}_retake_{timestamp}.jpg"
        
        # 💡 ចង្អុលទៅកាន់ Folder 'static/latest_scans' ដោយផ្ទាល់
        latest_scans_dir = os.path.join(app.root_path, 'static', 'latest_scans')
        
        # បង្កើត Folder នេះដោយស្វ័យប្រវត្តិ ប្រសិនបើវាមិនទាន់មាន
        if not os.path.exists(latest_scans_dir):
            os.makedirs(latest_scans_dir)
            
        filepath = os.path.join(latest_scans_dir, new_filename)
        
        # Save រូបភាពជាទម្រង់ JPEG ឱ្យស្រាល
        image.save(filepath, format='JPEG', quality=85)

        # ៣. Update ចូល Database 
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE candidates 
            SET face_encoding = %s, latest_scan_photo = %s 
            WHERE application_no = %s
        """, (face_encoding_json, new_filename, app_no))
        
        # 💡 ប្រសិនបើរកមិនឃើញលេខកូដនេះក្នុង Database ទេ
        if cursor.rowcount == 0:
            conn.rollback() # បោះបង់ការ Save
            if os.path.exists(filepath):
                os.remove(filepath) # លុបរូបដែលទើប Save ចោលវិញ
            return {"status": "error", "message": f"❌ រកមិនឃើញលេខកូដបេក្ខជន '{app_no}' ក្នុងប្រព័ន្ធទេ! សូមពិនិត្យម្តងទៀត។"}

        conn.commit()
        
        # ៤. ធ្វើបច្ចុប្បន្នភាពទិន្នន័យក្នុង RAM
        current_session = session.get('active_session')
        if current_session: 
            load_skill_test_cache(current_session)
        
        cursor.close()
        conn.close()

        return {"status": "success", "message": "បាន Update ផ្ទៃមុខ និងរូបថតថ្មីជោគជ័យ!"}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"បញ្ហាប្រព័ន្ធ: {str(e)}"}
    
import base64
import os
from flask import request, jsonify

# Route សម្រាប់ទទួលរូបថតថ្មី និង Save ចូល Folder
@app.route('/api/save_new_photo', methods=['POST'])
def save_new_photo():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'សូមចូលគណនីជាមុនសិន!'})

    try:
        data = request.json
        app_no = data.get('application_no')
        image_base64 = data.get('image_data')

        if not app_no or not image_base64:
            return jsonify({'status': 'error', 'message': 'ទិន្នន័យមិនគ្រប់គ្រាន់ទេ'})

        # កាត់ពាក្យ 'data:image/jpeg;base64,' ចេញពីក្បាល
        header, encoded = image_base64.split(",", 1)
        image_bytes = base64.b64decode(encoded)

        # កំណត់ឈ្មោះរូប និងទីតាំងរក្សាទុក (ឧទាហរណ៍ Save ចូល static/latest_scans)
        filename = f"{app_no}.jpg"
        save_path = os.path.join(app.root_path, 'static', 'latest_scans', filename)

        # បង្កើត Folder បើវាមិនទាន់មាន
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Save រូបភាពចូលក្នុងម៉ាស៊ីន
        with open(save_path, "wb") as f:
            f.write(image_bytes)

        # 💡 [ជាជម្រើស] បើចង់ Update ឈ្មោះរូបចូល Database អាចសរសេរកូដនៅទីនេះ:
        # conn = get_db_connection()
        # cursor = conn.cursor()
        # cursor.execute("UPDATE candidates SET latest_scan_photo = %s WHERE application_no = %s", (filename, app_no))
        # conn.commit()
        # cursor.close()
        # conn.close()

        return jsonify({'status': 'success', 'message': 'រក្សាទុករួចរាល់', 'filename': filename})

    except Exception as e:
        print(f"Error saving photo: {e}")
        return jsonify({'status': 'error', 'message': 'មានបញ្ហាប្រព័ន្ធ Server'})    
    
# 💡 API ថ្មីសម្រាប់ស្វែងរកបេក្ខជនក្នុងទំព័រ Exam ដោយមិនបាច់ Reload ទំព័រ
@app.route('/api/search_candidate', methods=['POST'])
def api_search_candidate():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'សូមចូលគណនីជាមុនសិន!'})

    data = request.json
    search_query = data.get('search_query', '').strip()

    if not search_query:
        return jsonify({'status': 'error', 'message': 'សូមវាយបញ្ចូលលេខកូដ'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # ស្វែងរកតាមលេខកូដ UBT ឬ Passport
        query = """
            SELECT application_no, name_en, gender, dob, passport_no, id_card_no, 
                   test_date, test_room, exam_session, industry, original_photo_path 
            FROM candidates 
            WHERE application_no LIKE %s OR passport_no = %s OR id_card_no = %s
            LIMIT 1
        """
        like_search = f"%{search_query}"
        cursor.execute(query, (like_search, search_query, search_query))
        candidate = cursor.fetchone()

        if candidate:
            # បំប្លែងថ្ងៃខែទៅជាអក្សរ (String) ដើម្បីកុំឱ្យ Error ពេលបញ្ជូនជា JSON
            if candidate['dob']:
                candidate['dob'] = candidate['dob'].strftime('%Y-%m-%d')
            if candidate['test_date']:
                candidate['test_date'] = candidate['test_date'].strftime('%Y-%m-%d')

            return jsonify({'status': 'success', 'candidate': candidate})
        else:
            return jsonify({'status': 'error', 'message': 'រកមិនឃើញបេក្ខជននេះទេ!'})

    except Exception as e:
        print(f"Error searching candidate API: {e}")
        return jsonify({'status': 'error', 'message': 'មានបញ្ហាប្រព័ន្ធ Database'})
    finally:
        cursor.close()
        conn.close()    

@app.route('/import_final_passers', methods=['POST'])
def import_final_passers():
    if 'loggedin' not in session: 
        return redirect(url_for('login'))
    
    file = request.files.get('file')
    if not file:
        flash('សូមជ្រើសរើស File', 'danger')
        return redirect(request.referrer)

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file, header=None, dtype=str)
        else:
            df = pd.read_excel(file, header=None, dtype=str)

        # ស្វែងរកជួរ Header (PKNo)
        header_row_index = -1
        for index, row in df.iterrows():
            row_str = ' '.join([str(val) for val in row.values if pd.notna(val)])
            if 'PKNo' in row_str:
                header_row_index = index
                break
        
        if header_row_index == -1:
            flash('មិនអាចអាន File បានទេ ព្រោះរកមិនឃើញ Column ឈ្មោះ "PKNo"!', 'danger')
            return redirect(request.referrer)

        df.columns = df.iloc[header_row_index]
        df = df.iloc[header_row_index + 1:].reset_index(drop=True)
        df.columns = df.columns.astype(str).str.strip()

        # ប្រមូលលេខកូដអ្នកជាប់
        passer_list = []
        for _, row in df.iterrows():
            app_no = str(row.get('PKNo', '')).strip()
            if app_no and app_no.lower() != 'nan':
                passer_list.append(app_no)

        conn = get_db_connection()
        cursor = conn.cursor()

        # ==========================================
        # 💡 ដំណើរការ Update លទ្ធផលជា ៣ ដំណាក់កាល
        # ==========================================

        # ទី ១៖ Reset លទ្ធផលចាស់ៗទាំងអស់ឱ្យទៅជា NULL វិញ (ទទេ)
        cursor.execute("UPDATE skill_test_candidates SET is_final_passer = NULL")

        passed_count = 0
        # ទី ២៖ Update អ្នកដែលមានឈ្មោះក្នុង File ឱ្យជាប់ (លេខ 1)
        if passer_list:
            chunk_size = 1000
            for i in range(0, len(passer_list), chunk_size):
                chunk = passer_list[i:i+chunk_size]
                format_strings = ','.join(['%s'] * len(chunk))
                cursor.execute(f"UPDATE skill_test_candidates SET is_final_passer = 1 WHERE application_no IN ({format_strings})", tuple(chunk))
                passed_count += cursor.rowcount

        # ទី ៣៖ Update អ្នកដែលបានមកប្រឡង តែអត់មានឈ្មោះ ឱ្យធ្លាក់ (លេខ 0)
        cursor.execute("UPDATE skill_test_candidates SET is_final_passer = 0 WHERE is_present = 1 AND is_final_passer IS NULL")
        failed_count = cursor.rowcount # រាប់ចំនួនអ្នកធ្លាក់ពិតប្រាកដ

        conn.commit()
        cursor.close()
        conn.close()
        
        # 💡 បង្ហាញសារជូនដំណឹងយ៉ាងច្បាស់លាស់
        flash(f'ជោគជ័យ! បេក្ខជនជាប់ស្ថាពរ: {passed_count} នាក់ | ធ្លាក់ស្ថាពរ: {failed_count} នាក់', 'success')
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'មានបញ្ហាប្រព័ន្ធ៖ {str(e)}', 'danger')
        
    return redirect(url_for('manage_skill_test_candidates'))

import os
from werkzeug.utils import secure_filename
import traceback # បន្ថែមដើម្បី print error លម្អិត

# កំណត់ Folder សម្រាប់រក្សាទុកឯកសារដែលបេក្ខជន Upload
app.config['UPLOAD_FOLDER_APPS'] = 'static/uploads/applications'
os.makedirs(app.config['UPLOAD_FOLDER_APPS'], exist_ok=True)

# ==========================================================
# ផ្នែកបេក្ខជន (Candidate Portal)
# ==========================================================

# ១. Route សម្រាប់បង្ហាញទំព័រ Login របស់បេក្ខជន
@app.route('/candidate_login')
@limiter.exempt  # 👈 ត្រូវប្រាកដថាមានបន្ទាត់នេះ
def candidate_login_page():
    # ១. ឆែកមើលសិទ្ធិ និងម៉ោងកំណត់សម្រាប់ candidate_login
    
    is_allowed, setting = check_qr_access() # ✅ ត្រូវ (ដកអក្សរក្នុងវង់ក្រចកចេញ)
    
    if not is_allowed:
        return render_template('qr_closed.html', 
                               message=f"ប្រព័ន្ធ {setting['qr_name'] if setting else ''} ត្រូវបានបិទ ឬហួសកាលកំណត់។",
                               start_time=setting['start_datetime'] if setting else None,
                               end_time=setting['end_datetime'] if setting else None)
    # បើធ្លាប់ Login រួចហើយ ឱ្យលោតទៅទំព័រទម្រង់តែម្តង
    if 'candidate_logged_in' in session:
        return redirect(url_for('candidate_application_form'))
    return render_template('candidate_login.html')

import cv2
import numpy as np
import base64
#import face_recognition
import os
from flask import request, jsonify, session, url_for, flash, redirect

# ==============================================================================
# 💡 Route 1: Face Login (ស្កេនមុខ) - កំណែទម្រង់លឿនជាងមុន
# ==============================================================================
@app.route('/candidate/face_login', methods=['POST'])
def candidate_face_login():
    data = request.get_json()
    image_data = data.get('image')
    app_no = data.get('application_no') # 🔴 ទទួលយកលេខកូដ ១៦ ខ្ទង់

    if not image_data or not app_no:
        return jsonify({'status': 'error', 'message': 'ទិន្នន័យមិនគ្រប់គ្រាន់ទេ!'})

    conn = None
    cursor = None
    try:
        # ១. បំប្លែងរូបភាពដែលទើបស្កេន (Captured Image)
        encoded_data = image_data.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        captured_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_frame = cv2.cvtColor(captured_image, cv2.COLOR_BGR2RGB)

        captured_face_locations = face_recognition.face_locations(rgb_frame)
        if len(captured_face_locations) != 1:
            return jsonify({'status': 'error', 'message': 'សូមដាក់មុខឲ្យចំកាមេរ៉ា និងនៅតែម្នាក់ឯង។'})
            
        captured_encoding = face_recognition.face_encodings(rgb_frame, captured_face_locations)[0]

        # ២. ទាញយករូបថតយោង "តែមួយសន្លឹកគត់" (1:1 Verification)
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT c.application_no, c.name_en, c.original_photo_path 
            FROM candidates c
            INNER JOIN skill_test_candidates stc ON c.application_no = stc.application_no
            WHERE c.application_no = %s AND stc.is_final_passer = 1
        """
        cursor.execute(query, (app_no,))
        candidate = cursor.fetchone()

        if not candidate or not candidate['original_photo_path']:
            return jsonify({'status': 'error', 'message': 'លេខកូដនេះមិនមានសិទ្ធិ ឬមិនមានរូបថតក្នុងប្រព័ន្ធទេ!'})

        # ៣. ប្រៀបធៀបផ្ទៃមុខ (Face Compare)
        ref_photo_path = os.path.join('static', 'uploads', 'reference_photos', candidate['original_photo_path'])
        if not os.path.exists(ref_photo_path):
            return jsonify({'status': 'error', 'message': 'រកមិនឃើញរូបថតដើមក្នុងម៉ាស៊ីនមេទេ!'})

        ref_image = face_recognition.load_image_file(ref_photo_path)
        ref_encodings = face_recognition.face_encodings(ref_image)
        
        if not ref_encodings:
            return jsonify({'status': 'error', 'message': 'រូបថតដើមមិនមានផ្ទៃមុខច្បាស់លាស់។'})

        # វាស់គម្លាត (កាន់តែតូចកាន់តែដូច)
        face_distances = face_recognition.face_distance([ref_encodings[0]], captured_encoding)
        distance = face_distances[0]
        
        STRICT_TOLERANCE = 0.48 

        if distance < STRICT_TOLERANCE:
            # ជោគជ័យ
            session['candidate_logged_in'] = True
            session['candidate_app_no'] = candidate['application_no']
            session['candidate_name'] = candidate['name_en']
            return jsonify({'status': 'success', 'redirect': url_for('candidate_application_form')})
        else:
            # បរាជ័យ
            return jsonify({'status': 'error', 'message': 'មុខមិនដូចរូបថតក្នុងឯកសារទេ។ សូមសាកល្បងម្តងទៀត!'})

    except Exception as e:
        print(f"Face Login Error: {e}")
        return jsonify({'status': 'error', 'message': 'មានបញ្ហាប្រព័ន្ធ Server កំឡុងពេលវិភាគផ្ទៃមុខ!'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==============================================================================
# 💡 Route 2: Manual Login (វាយបញ្ចូលទិន្នន័យ) - សុវត្ថិភាពខ្ពស់
# ==============================================================================
@app.route('/candidate/manual_login', methods=['POST'])
def candidate_manual_login():
    application_no = request.form.get('application_no', '').strip()
    id_passport = request.form.get('id_passport', '').strip()
    
    dob_day = request.form.get('dob_day', '').strip()
    dob_month = request.form.get('dob_month', '').strip()
    dob_year = request.form.get('dob_year', '').strip()

    if not application_no or not id_passport or not dob_day or not dob_month or not dob_year:
        flash('សូមបញ្ចូលព័ត៌មានឲ្យបានគ្រប់ជ្រុងជ្រោយ (រួមទាំងថ្ងៃខែឆ្នាំកំណើត)!', 'danger')
        return redirect(url_for('candidate_login_page'))

    dob = f"{dob_year}-{dob_month}-{dob_day}"

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 🔴 INNER JOIN ដើម្បីយកតែអ្នកដែល is_final_passer = 1
        query = """
            SELECT c.application_no, c.name_en 
            FROM candidates c
            INNER JOIN skill_test_candidates stc ON c.application_no = stc.application_no
            WHERE c.application_no = %s 
              AND c.dob = %s 
              AND (c.id_card_no = %s OR c.passport_no = %s)
              AND stc.is_final_passer = 1
        """
        cursor.execute(query, (application_no, dob, id_passport, id_passport))
        candidate = cursor.fetchone()

        if candidate:
            session['candidate_logged_in'] = True
            session['candidate_app_no'] = candidate['application_no']
            session['candidate_name'] = candidate['name_en']
            return redirect(url_for('candidate_application_form'))
        else:
            # 💡 យើងអាចបន្ថែម Logic មួយតង់ទៀតដើម្បីប្រាប់គាត់ចំៗថា "គាត់ធ្លាក់" ឬ "វាយទិន្នន័យខុស"
            # តែជាបឋម យើងដាក់សាររួមសិន ដើម្បីការពារសុវត្ថិភាព
            flash('ព័ត៌មានមិនត្រឹមត្រូវ ឬអ្នកមិនមានសិទ្ធិដាក់ពាក្យ (មិនជាប់តេស្តជំនាញស្ថាពរ)!', 'danger')
            return redirect(url_for('candidate_login_page'))

    except Exception as e:
        print(f"Candidate Manual Login Error: {e}")
        flash('មានបញ្ហាក្នុងការភ្ជាប់ទិន្នន័យ!', 'danger')
        return redirect(url_for('candidate_login_page'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

from datetime import datetime, time, timedelta # ត្រូវប្រាកដថាបាន import ទាំងនេះ
import pytz

@app.route('/candidate/application_form', methods=['GET', 'POST'])
def candidate_application_form():
    # ១. ពិនិត្យមើលថាបេក្ខជនបាន Login ហើយឬនៅ?
    if 'candidate_logged_in' not in session:
        return redirect(url_for('candidate_login_page'))

    app_no = session.get('candidate_app_no')
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # -------------------------------------------------------------
        # ២. ពិនិត្យការបិទ/បើកប្រព័ន្ធ (System Settings & Time ប្រើម៉ោងខ្មែរ)
        # -------------------------------------------------------------
        cursor.execute("SELECT * FROM system_settings WHERE id = 1")
        settings = cursor.fetchone() or {}

        if settings:
            # ១. កំណត់ម៉ោងបច្ចុប្បន្នជាម៉ោងកម្ពុជាជានិច្ច
            kh_timezone = pytz.timezone('Asia/Phnom_Penh')
            now_kh = datetime.now(kh_timezone)
            current_date = now_kh.date()
            current_time = now_kh.time()

            # ២. ពិនិត្យ Master Switch (បិទប្រព័ន្ធទាំងស្រុង)
            if settings.get('is_system_open') == 0:
                return render_template('system_closed.html', message="ប្រព័ន្ធទទួលពាក្យត្រូវបានបិទជាបណ្តោះអាសន្ន!")

            # ៣. ពិនិត្យកាលបរិច្ឆេទ (ថ្ងៃចាប់ផ្តើម - ថ្ងៃបញ្ចប់)
            start_date = settings.get('app_start_date')
            end_date = settings.get('app_end_date')
            
            if start_date and current_date < start_date:
                start_date_str = start_date.strftime('%d/%m/%Y') if hasattr(start_date, 'strftime') else start_date
                return render_template('system_closed.html', message=f"ប្រព័ន្ធនឹងចាប់ផ្តើមបើកទទួលពាក្យនៅថ្ងៃទី {start_date_str}។")
            
            if end_date and current_date > end_date:
                return render_template('system_closed.html', message="កាលបរិច្ឆេទនៃការទទួលពាក្យត្រូវបានបញ្ចប់ហើយ!")

            # ៤. មុខងារជំនួយប្តូរ Time ពី Database មកជា Python Time object
            def convert_to_time_obj(val):
                if not val:
                    return None
                if isinstance(val, timedelta):
                    total_seconds = int(val.total_seconds())
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    return time(hours, minutes, seconds)
                if isinstance(val, time):
                    return val
                if isinstance(val, str):
                    try:
                        parts = val.split(':')
                        h = int(parts[0])
                        m = int(parts[1]) if len(parts) > 1 else 0
                        s = int(parts[2]) if len(parts) > 2 else 0
                        return time(h, m, s)
                    except ValueError:
                        return None
                return None

            # ៥. ទាញយកម៉ោងកំណត់ពី DB
            am_start = convert_to_time_obj(settings.get('am_start_time'))
            am_end = convert_to_time_obj(settings.get('am_end_time'))
            pm_start = convert_to_time_obj(settings.get('pm_start_time'))
            pm_end = convert_to_time_obj(settings.get('pm_end_time'))

            # ៦. ពិនិត្យមើលថាតើម៉ោងបច្ចុប្បន្នស្ថិតក្នុងចន្លោះ AM ឬ PM ដែរឬទេ
            is_am_valid = (am_start and am_end) and (am_start <= current_time <= am_end)
            is_pm_valid = (pm_start and pm_end) and (pm_start <= current_time <= pm_end)

            if not (is_am_valid or is_pm_valid):
                return render_template('system_closed.html', message="ប្រព័ន្ធទទួលពាក្យកំពុងសម្រាក ឬបិទ។ សូមចូលមកកាន់ប្រព័ន្ធតាមម៉ោងកំណត់។")

        # -------------------------------------------------------------
        # ៣. ទាញយកទិន្នន័យបេក្ខជន (Smart Sync)
        # -------------------------------------------------------------
        sql_candidate = """
            SELECT c.*, a.id AS details_id, a.new_photo_file_path AS uploaded_photo
            FROM candidates c
            LEFT JOIN application_details a ON c.application_no = a.application_no
            WHERE c.application_no = %s
        """
        cursor.execute(sql_candidate, (app_no,))
        candidate_data = cursor.fetchone()
        
        if not candidate_data:
            session.pop('candidate_logged_in', None)
            return redirect(url_for('candidate_logout'))
            
        has_details = candidate_data.get('details_id') is not None 

        # 🔴 [កែតម្រូវចម្បង] ឱ្យតែបេក្ខជនធ្លាប់មានទិន្នន័យ Form រួចហើយ គឺត្រូវរុញគាត់ទៅ Dashboard ជានិច្ច ទោះគាត់ជាប់ Status អ្វីក៏ដោយ!
        if has_details:
            return redirect(url_for('candidate_application_success'))
        
        # [Safety Net] បើគាត់អត់ទាន់មានទិន្នន័យ Form ទេ តែ Status គាត់លោតថា PENDING/APPROVED/REJECTED ដោយសារ Error អ្វីមួយ គឺត្រូវ Reset វាសិន
        app_status = candidate_data.get('job_app_status')
        if not has_details and app_status is not None:
            cursor.execute("UPDATE candidates SET job_app_status = NULL WHERE application_no = %s", (app_no,))
            conn.commit()

        # -------------------------------------------------------------
        # ៤. ទាញយកទិន្នន័យ Reference សម្រាប់ Dropdowns
        # -------------------------------------------------------------
        cursor.execute("SELECT * FROM ref_banks ORDER BY bank_full_name ASC")
        banks = cursor.fetchall()
        
        cursor.execute("SELECT * FROM ref_education_levels ORDER BY id ASC")
        education_levels = cursor.fetchall()

        cursor.execute("SELECT * FROM ref_provinces ORDER BY name_kh ASC")
        provinces = cursor.fetchall()

        cursor.execute("SELECT * FROM ref_occupations ORDER BY job_name_kh ASC")
        occupations = cursor.fetchall()

        cursor.execute("SELECT id, relation_name_kh FROM ref_relationships ORDER BY id ASC")
        relationships = cursor.fetchall()

        # -------------------------------------------------------------
        # ៥. បញ្ជូនទិន្នន័យទាំងអស់ទៅកាន់ HTML
        # -------------------------------------------------------------
        return render_template('application_form.html', 
                               candidate=candidate_data, 
                               banks=banks, 
                               education_levels=education_levels,
                               provinces=provinces,
                               settings=settings,
                               occupations=occupations,
                               relationships=relationships) 

    except Exception as e:
        import traceback
        print(f"\n=== System Error ===\n{str(e)}\n{traceback.format_exc()}\n================\n")
        return "មានបញ្ហាប្រព័ន្ធ សូមព្យាយាមម្តងទៀត!"
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ==============================================================================
# Route សម្រាប់ទទួលទិន្នន័យ និង Save ចូល Database 
# ==============================================================================
import os
import re
from flask import request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from datetime import datetime

# ======================================================================
# 💡 កែសម្រួល Function បង្កើតលេខ Queue (ការពារការជាន់គ្នា ១០០%)
# ======================================================================
def generate_queue_number(conn):
    # យើងបង្កើត cursor ថ្មីនៅទីនេះ តែវានៅតែស្ថិតក្នុង Transaction របស់ conn ដដែល
    cursor = conn.cursor(dictionary=True)
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # ១. ព្យាយាមបង្កើត Record សម្រាប់ថ្ងៃថ្មីមុនគេ (បើមានរួចហើយ វាស់ IGNORE មិន Error)
        # ចំណាំ: ដើម្បីអោយ INSERT IGNORE ដើរស្រួល, តារាង queue_sequence គួរតែមាន PRIMARY KEY លើ queue_date
        cursor.execute("INSERT IGNORE INTO queue_sequence (queue_date, last_number) VALUES (%s, 0)", (today_date,))
        
        # ២. ប្រើ "FOR UPDATE" ដើម្បី Lock ជួរទិន្នន័យ (Row) នេះ។ 
        # បើបេក្ខជនទី២ មកដល់ទីនេះ គាត់ត្រូវរង់ចាំបេក្ខជនទី១ ធ្វើការចប់ (commit) សិន។
        cursor.execute("SELECT last_number FROM queue_sequence WHERE queue_date = %s FOR UPDATE", (today_date,))
        seq_record = cursor.fetchone()

        if seq_record:
            # ៣. បូកលេខថែម ១ ហើយ Update
            new_number = seq_record['last_number'] + 1
            cursor.execute("UPDATE queue_sequence SET last_number = %s WHERE queue_date = %s", (new_number, today_date))
        else:
            # ករណីកម្រ (Fallback): បើរកមិនឃើញសោះ ផ្តើមពី ១ (ធម្មតាមិនគួរធ្លាក់មកដល់ទីនេះទេ ព្រោះយើងបាន INSERT IGNORE ខាងលើហើយ)
            new_number = 1
            cursor.execute("INSERT INTO queue_sequence (queue_date, last_number) VALUES (%s, %s)", (today_date, new_number))
            
        # ៤. កំណត់ទម្រង់លេខ A-001
        return f"A-{new_number:03d}"
        
    except Exception as e:
        print(f"Error generating queue number: {e}")
        # យើងមិន rollback នៅទីនេះទេ ទុកអោយ Function ដែលហៅវា (ដូចជា submit_application) ជាអ្នក rollback
        raise e

# ======================================================================
# Route Submit Application Form
# ======================================================================
# ======================================================================
# Route Submit Application Form (🔥 ដាក់ប្រព័ន្ធតាមដាន - Ultimate Debug Mode)
# ======================================================================
# ======================================================================
# Route Submit Application Form
# ======================================================================
from datetime import datetime 
import pytz # 💡 បន្ថែមការប្រើប្រាស់ pytz នៅខាងលើកូដ

# ==============================================================================
# 🟢 Route: សម្រាប់បេក្ខជន Submit ពាក្យសុំ
# ==============================================================================
@app.route('/candidate/submit_application', methods=['POST'])
def candidate_submit_application():
    print("\n" + "="*50)
    print("🚀 [DEBUG] STARTING FORM SUBMISSION...")
    
    app_no = session.get('candidate_app_no')
    print(f"👉 [DEBUG] Application No: {app_no}")
    
    if not app_no or 'candidate_logged_in' not in session:
        print("❌ [DEBUG] Session Timeout!")
        flash('សេវាកម្មបានផុតកំណត់ (Session Timeout) សូម Login ម្តងទៀត!', 'warning')
        return redirect(url_for('candidate_login_page'))

    form = request.form
    errors = []

    # --- Helper Functions ---
    def clean_val(key):
        val = form.get(key, '').strip()
        return val if val and val not in ['None', 'null', 'NULL', ''] else None

    def format_phone(phone_str):
        if not phone_str: return None
        digits = re.sub(r'\D', '', phone_str)
        if len(digits) == 9: return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
        elif len(digits) >= 10: return f"{digits[:3]} {digits[3:6]} {digits[6:10]}"
        return phone_str

    def save_file(file_obj, prefix):
        if file_obj and file_obj.filename != '':
            try:
                ext = os.path.splitext(file_obj.filename)[1].lower()
                filename = secure_filename(f"{app_no}_{prefix}{ext}")
                save_path = os.path.join(app.config['UPLOAD_FOLDER_APPS'], filename)
                file_obj.save(save_path)
                return filename
            except Exception as e:
                print(f"❌ [DEBUG] Error saving file {prefix}: {e}")
                return None
        return None

    # --- Validation ---
    first_name_kh = clean_val('first_name_kh')
    last_name_kh = clean_val('last_name_kh')
    id_card_no = clean_val('id_card_no')
    passport_no = clean_val('passport_no')
    marital_status = clean_val('marital_status')
    gender_val = clean_val('gender')
    
    if not first_name_kh or not last_name_kh:
        errors.append("សូមបញ្ចូលឈ្មោះជាភាសាខ្មែរឱ្យបានត្រឹមត្រូវ។")

    if errors:
        for error in errors: flash(error, 'danger')
        return redirect(url_for('candidate_application_form'))

    print("✅ [DEBUG] Validation Passed. Saving files...")
    passport_doc = save_file(request.files.get('passport_file'), 'PP')
    bank_book_doc = save_file(request.files.get('bank_book_file'), 'BA')
    
    conn = None
    cursor = None
    try:
        # 🌟 កំណត់ម៉ោងកម្ពុជាសម្រាប់ប្រើទូទាំង Function នេះ
        khmer_tz = pytz.timezone('Asia/Phnom_Penh')
        current_kh_time = datetime.now(khmer_tz).strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        conn.start_transaction()
        print("✅ [DEBUG] Database Connected & Transaction Started.")

        # ==============================================================
        print("⏳ [DEBUG STEP 1] រៀបចំអាសយដ្ឋាន...")
        prov_id = clean_val('province_id')
        dist_id = clean_val('district_id')
        comm_id = clean_val('commune_id')
        vill_id = clean_val('village_id')
        address_detail_text = None
        
        if prov_id and dist_id and comm_id and vill_id:
            cursor.execute("""
                SELECT v.name_en as vill, c.name_en as comm, d.name_en as dist, p.name_en as prov
                FROM ref_provinces p, ref_districts d, ref_communes c, ref_villages v
                WHERE p.id=%s AND d.id=%s AND c.id=%s AND v.id=%s
            """, (prov_id, dist_id, comm_id, vill_id))
            addr_row = cursor.fetchone()
            if addr_row:
                address_detail_text = f"{addr_row['vill']}/{addr_row['comm']}/{addr_row['dist']}/{addr_row['prov']}"
        print("✅ [DEBUG STEP 1] អាសយដ្ឋានជោគជ័យ!")

        # ==============================================================
        print("⏳ [DEBUG STEP 2] Update/Insert ចូល application_details...")
        cursor.execute("SELECT id, passport_file_path, bank_book_file_path FROM application_details WHERE application_no = %s", (app_no,))
        existing_app = cursor.fetchone()

        app_data = [
            last_name_kh, first_name_kh, id_card_no, clean_val('height'), clean_val('weight'), 
            marital_status, format_phone(clean_val('phone_number')), clean_val('email'), 
            clean_val('facebook_link'), clean_val('tiktok_link'),
            prov_id, dist_id, comm_id, vill_id, address_detail_text, 
            clean_val('worked_in_korea_last_5yrs'), clean_val('alien_registration_no'),
            clean_val('education_level_id'), clean_val('khmer_school_name'), clean_val('khmer_school_province_id'),
            clean_val('korean_school_name'), clean_val('korean_school_province_id'),
            passport_no, clean_val('passport_issue_date'), clean_val('bank_id'), clean_val('bank_account_no')
        ]

        if existing_app:
            print("👉 [DEBUG] ធ្វើការ UPDATE ទិន្នន័យចាស់...")
            final_pass = passport_doc or existing_app.get('passport_file_path')
            final_bank = bank_book_doc or existing_app.get('bank_book_file_path')
            
            # 🌟 ប្រើប្រាស់ current_kh_time បញ្ចូលសម្រាប់ពេល Update ប្រសិនបើមាន Field updated_at នៅក្នុងតារាង (ជាជម្រើស)
            sql_update = """
                UPDATE application_details SET 
                    last_name_kh=%s, first_name_kh=%s, id_card_no=%s, height=%s, weight=%s, marital_status=%s,
                    phone_number=%s, email=%s, facebook_link=%s, tiktok_link=%s, province_id=%s, 
                    district_id=%s, commune_id=%s, village_id=%s, address_detail=%s, 
                    worked_in_korea_last_5yrs=%s, alien_registration_no=%s, education_level_id=%s, 
                    khmer_school_name=%s, khmer_school_province_id=%s, korean_school_name=%s, 
                    korean_school_province_id=%s, passport_no=%s, passport_issue_date=%s, 
                    bank_id=%s, bank_account_no=%s, passport_file_path=%s, bank_book_file_path=%s,
                    status_id=1, remark=NULL
                WHERE application_no = %s
            """
            app_data.extend([final_pass, final_bank, app_no])
            cursor.execute(sql_update, tuple(app_data))
        else:
            print("👉 [DEBUG] ធ្វើការ INSERT ទិន្នន័យថ្មី...")
            sql_insert = """
                INSERT INTO application_details (
                    last_name_kh, first_name_kh, id_card_no, height, weight, marital_status,
                    phone_number, email, facebook_link, tiktok_link, province_id, district_id, 
                    commune_id, village_id, address_detail, worked_in_korea_last_5yrs, 
                    alien_registration_no, education_level_id, khmer_school_name, 
                    khmer_school_province_id, korean_school_name, korean_school_province_id,
                    passport_no, passport_issue_date, bank_id, bank_account_no,
                    passport_file_path, bank_book_file_path, status_id, application_no
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, 1, %s)
            """
            app_data.extend([passport_doc, bank_book_doc, app_no])
            cursor.execute(sql_insert, tuple(app_data))
        print("✅ [DEBUG STEP 2] application_details ជោគជ័យ!")

        # ==============================================================
        print("⏳ [DEBUG STEP 3] បញ្ចូលទិន្នន័យគ្រួសារ (family_members)...")
        cursor.execute("DELETE FROM family_members WHERE application_no = %s", (app_no,))
        
        sql_fam = """
            INSERT INTO family_members (application_no, relationship_id, last_name_kh, first_name_kh, 
            last_name_en, first_name_en, dob, status, occupation_id, phone_number, children_count, 
            province_id, district_id, commune_id, village_id, address_detail, guarantor_role) 
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        def get_rel_id(name_en):
            cursor.execute("SELECT id FROM ref_relationships WHERE relation_name_en = %s", (name_en,))
            res = cursor.fetchone()
            return res['id'] if res else None

        p_prov = clean_val('parent_province_id')
        p_dist = clean_val('parent_district_id')
        p_comm = clean_val('parent_commune_id')
        p_vill = clean_val('parent_village_id')
        p_addr = None
        
        if p_prov and p_dist and p_comm and p_vill:
            cursor.execute("""
                SELECT v.name_en as vill, c.name_en as comm, d.name_en as dist, p.name_en as prov
                FROM ref_provinces p, ref_districts d, ref_communes c, ref_villages v
                WHERE p.id=%s AND d.id=%s AND c.id=%s AND v.id=%s
            """, (p_prov, p_dist, p_comm, p_vill))
            p_addr_row = cursor.fetchone()
            if p_addr_row:
                p_addr = f"{p_addr_row['vill']}/{p_addr_row['comm']}/{p_addr_row['dist']}/{p_addr_row['prov']}"

        if clean_val('father_first_name'):
            cursor.execute(sql_fam, (app_no, get_rel_id('Father'), clean_val('father_last_name'), clean_val('father_first_name'), 
                                     None, None, None, clean_val('father_status'), clean_val('father_occupation_id'), 
                                     format_phone(clean_val('father_phone')), 0, 
                                     p_prov, p_dist, p_comm, p_vill, p_addr, None))

        if clean_val('mother_first_name'):
            cursor.execute(sql_fam, (app_no, get_rel_id('Mother'), clean_val('mother_last_name'), clean_val('mother_first_name'), 
                                     None, None, None, clean_val('mother_status'), clean_val('mother_occupation_id'), 
                                     format_phone(clean_val('mother_phone')), 0, 
                                     p_prov, p_dist, p_comm, p_vill, p_addr, None))

        if marital_status == 'Married' and clean_val('spouse_first_name'):
            rel_spouse = get_rel_id('Wife') if gender_val in ['M', 'Male'] else get_rel_id('Husband')
            cursor.execute(sql_fam, (app_no, rel_spouse, None, None, clean_val('spouse_last_name'), clean_val('spouse_first_name'),
                                     clean_val('spouse_dob'), 'Alive', clean_val('spouse_occupation_id'), 
                                     format_phone(clean_val('spouse_phone')), clean_val('spouse_children_count') or 0, 
                                     None, None, None, None, None, None))

        if clean_val('guarantor_first_name_en'):
            cursor.execute(sql_fam, (app_no, clean_val('guarantor_relation_id'), None, None, clean_val('guarantor_last_name_en'), 
                                     clean_val('guarantor_first_name_en'), None, 'Alive', None, 
                                     format_phone(clean_val('guarantor_phone')), 0, 
                                     clean_val('guarantor_province_id'), None, None, None, None, 'Guarantor'))
        print("✅ [DEBUG STEP 3] family_members ជោគជ័យ!")
        
        # ==============================================================
        print("⏳ [DEBUG STEP 4] បង្កើត Queue Ticket...")
        
        # ឆែករកមើលលេខរង់ចាំដែលកំពុងសកម្មថ្ងៃនេះ 
        # 🌟 (ប្តូរ CURDATE() ទៅប្រើម៉ោងកម្ពុជាផ្ទាល់)
        today_kh_date = datetime.now(khmer_tz).strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT id, queue_number FROM queue_tickets 
            WHERE application_no = %s AND status IN ('Waiting', 'Processing') 
            AND DATE(created_at) = %s
            ORDER BY id DESC LIMIT 1
        """, (app_no, today_kh_date))
        active_q_row = cursor.fetchone()
        
        if active_q_row:
            queue_ticket_number = active_q_row['queue_number']
            print(f"👉 [DEBUG] ប្រើប្រាស់លេខចាស់ដែលនៅសកម្ម: {queue_ticket_number}")
        else:
            queue_ticket_number = generate_queue_number(conn) 
            print(f"👉 [DEBUG] បង្កើតលេខថ្មី: {queue_ticket_number}")
            
            # ឆែកក្រែងលោមានការ Create ពី Kiosk ទុកចោល
            cursor.execute("SELECT id FROM queue_tickets WHERE queue_number = %s AND DATE(created_at) = %s LIMIT 1", (queue_ticket_number, today_kh_date))
            existing_ticket = cursor.fetchone()

            if existing_ticket:
                print("👉 [DEBUG] អាប់ដេតសំបុត្របញ្ចូល App No...")
                # 🌟 ជំនួស NOW() ដោយ current_kh_time
                cursor.execute("""
                    UPDATE queue_tickets 
                    SET application_no = %s, status = 'Waiting', updated_at = %s 
                    WHERE id = %s
                """, (app_no, current_kh_time, existing_ticket['id']))
            else:
                print("👉 [DEBUG] បញ្ចូលសំបុត្រថ្មី (Insert)...")
                # 🌟 ជំនួស NOW() ដោយ current_kh_time
                cursor.execute("""
                    INSERT INTO queue_tickets (application_no, queue_number, status, created_at, updated_at) 
                    VALUES (%s, %s, 'Waiting', %s, %s)
                """, (app_no, queue_ticket_number, current_kh_time, current_kh_time))

        cursor.execute("UPDATE candidates SET job_app_status = 'PENDING' WHERE application_no = %s", (app_no,))
        print("✅ [DEBUG STEP 4] Queue Ticket ជោគជ័យ!")

        # រក្សាទុកទិន្នន័យចុងក្រោយ
        conn.commit()
        print("🚀 [DEBUG] TRANSACTION COMMITTED SUCCESSFULLY!")
        print("="*50 + "\n")
        
        session['my_queue_number'] = queue_ticket_number 
        flash('រក្សាទុកជោគជ័យ!', 'success')
        return redirect(url_for('candidate_application_success'))

    except Exception as e:
        if conn: conn.rollback()
        import traceback
        error_msg = str(e)
        print("\n" + "❌"*25)
        print("=== CRITICAL ERROR IN MOBILE SUBMIT ===")
        print(f"ERROR: {error_msg}")
        print(traceback.format_exc())
        print("❌"*25 + "\n")
        
        flash(f'បរាជ័យ (DEBUG ERROR): {error_msg}', 'danger')
        return redirect(url_for('candidate_application_form'))
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==============================================================================
# 🟢 Route 1: សម្រាប់បង្ហាញទំព័រជោគជ័យ និង ទំព័របដិសេធ
# ==============================================================================
@app.route('/candidate/application_success')
def candidate_application_success():
    if 'candidate_logged_in' not in session or 'candidate_app_no' not in session:
        return redirect(url_for('candidate_login_page'))
    
    app_no = session.get('candidate_app_no')
    name = session.get('candidate_name_en', "មិនមានឈ្មោះ") 
    queue_number = session.get('my_queue_number', "N/A") 
    has_requested = False
    status_id = 1 
    remark = None
    apply_date_time = "មិនមានទិន្នន័យ"
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT q.queue_number, q.created_at, c.name_en
            FROM queue_tickets q
            JOIN candidates c ON q.application_no = c.application_no
            WHERE q.application_no = %s 
            ORDER BY q.id DESC LIMIT 1
        """, (app_no,))
        ticket = cursor.fetchone()
        
        if ticket:
            if ticket.get('queue_number'): queue_number = ticket['queue_number']
            if ticket.get('name_en'): name = ticket['name_en']
            
            if ticket.get('created_at'):
                db_time = ticket['created_at']
                
                # ដោយសារយើងបាន Insert ម៉ោងភ្នំពេញ (UTC+7) ពី Python ហើយ 
                # ដូច្នេះ Database លែងមានផ្ទុកម៉ោង UTC ទៀតហើយ។
                # យើងគ្រាន់តែ Format វាបង្ហាញយកតែម្តង ដើម្បីកុំឱ្យបម្លែងត្រួតគ្នា។
                if hasattr(db_time, 'strftime'):
                    apply_date_time = db_time.strftime('%d-%m-%Y ម៉ោង %H:%M')

        cursor.execute("SELECT status_id, remark FROM application_details WHERE application_no = %s LIMIT 1", (app_no,))
        app_detail = cursor.fetchone()
        if app_detail:
            status_id = app_detail.get('status_id')
            remark = app_detail.get('remark')
            
        cursor.execute("SELECT id FROM correction_requests WHERE application_no = %s LIMIT 1", (app_no,))
        if cursor.fetchone():
            has_requested = True
            
    except Exception as e:
        print(f"Error loading success page: {e}")
        flash('មានបញ្ហាក្នុងការទាញយកទិន្នន័យ។', 'danger')
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
    return render_template('application_success.html', 
                           app_no=app_no, 
                           name=name, 
                           queue_number=queue_number,
                           has_requested_edit=has_requested,
                           apply_date_time=apply_date_time, 
                           status_id=status_id,             
                           remark=remark)                   


# ==============================================================================
# 🔴 Route 2: សម្រាប់ប៊ូតុង "ស្នើសុំលេខរង់ចាំថ្មី" (Re-Queue)
# ==============================================================================
@app.route('/candidate/request_new_ticket', methods=['POST'])
def request_new_ticket():
    if 'candidate_logged_in' not in session:
        return redirect(url_for('candidate_login_page'))
        
    app_no = session.get('candidate_app_no')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 🌟 កំណត់ម៉ោងកម្ពុជា
        khmer_tz = pytz.timezone('Asia/Phnom_Penh')
        current_kh_time = datetime.now(khmer_tz).strftime('%Y-%m-%d %H:%M:%S')
        today_kh_date = datetime.now(khmer_tz).strftime('%Y-%m-%d')
        
        conn.start_transaction()
        
        # ១. បង្កើតលេខថ្មីដោយមិនជាន់គ្នា
        cursor.execute("INSERT IGNORE INTO queue_sequence (queue_date, last_number) VALUES (%s, 0)", (today_kh_date,))
        cursor.execute("SELECT last_number FROM queue_sequence WHERE queue_date = %s FOR UPDATE", (today_kh_date,))
        seq_record = cursor.fetchone()
        
        new_number = seq_record[0] + 1
        cursor.execute("UPDATE queue_sequence SET last_number = %s WHERE queue_date = %s", (new_number, today_kh_date))
        queue_str = f"A-{new_number:03d}"
        
        # ២. បញ្ចូលសំបុត្ររង់ចាំថ្មីទៅក្នុងប្រព័ន្ធ
        # 🌟 ជំនួស NOW() ដោយ current_kh_time
        cursor.execute("""
            INSERT INTO queue_tickets (application_no, queue_number, status, created_at, updated_at)
            VALUES (%s, %s, 'Waiting', %s, %s)
        """, (app_no, queue_str, current_kh_time, current_kh_time))
        
        # ៣. Update Status ឱ្យត្រឡប់ទៅជា 1 (រង់ចាំ) វិញ និងលុប Remark ចោល
        cursor.execute("UPDATE application_details SET status_id = 1, remark = NULL WHERE application_no = %s", (app_no,))
        cursor.execute("UPDATE candidates SET job_app_status = 'PENDING' WHERE application_no = %s", (app_no,))
        
        conn.commit()
        session['my_queue_number'] = queue_str
        flash(f'ទទួលបានលេខរង់ចាំថ្មីជោគជ័យ!', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"Error requesting new ticket: {e}")
        flash('មានបញ្ហាក្នុងការបង្កើតលេខរង់ចាំថ្មី!', 'danger')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
    return redirect(url_for('candidate_application_success'))
# ==============================================================================
# Route សម្រាប់បេក្ខជនចាកចេញពីគណនី (Logout) ដែលបានកែសម្រួល
# ==============================================================================
@app.route('/candidate/logout')
def candidate_logout():
    # លុបទិន្នន័យ Session របស់បេក្ខជនចោលទាំងអស់ (បញ្ចូលទាំងឈ្មោះថ្មី និងចាស់ ដើម្បីការពារ)
    session.pop('candidate_logged_in', None)
    session.pop('candidate_app_no', None)
    session.pop('candidate_name', None)      # 👈 លុបអថេរដែលបានបង្កើតពេល Login ថ្មី
    session.pop('candidate_name_en', None)   # 👈 លុបអថេរចាស់ (បើមាន)
    session.pop('my_queue_number', None)     # 👈 លុបលេខរង់ចាំ (Queue) ចោល
    
    # បញ្ជូនត្រលប់ទៅទំព័រ Login របស់បេក្ខជនវិញ
    return redirect(url_for('candidate_login_page'))


import json # កុំភ្លេច import json នៅខាងលើគេនៃ file app.py

# ==============================================================================
# Route សម្រាប់បង្ហាញទំព័រ ស្នើសុំកែតម្រូវទិន្នន័យ (GET)
# ==============================================================================
@app.route('/candidate/request_edit')
def candidate_request_edit():
    if 'candidate_logged_in' not in session:
        return redirect(url_for('candidate_login_page'))
    
    app_no = session.get('candidate_app_no')
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # ១. ឆែកមើលក្រែងលោគាត់មានសំណើកំពុង Pending រួចហើយ
        cursor.execute("SELECT id FROM correction_requests WHERE application_no = %s AND status = 'Pending' LIMIT 1", (app_no,))
        if cursor.fetchone():
            flash('អ្នកមានសំណើកែតម្រូវកំពុងរង់ចាំការពិនិត្យរួចហើយ!', 'warning')
            return redirect(url_for('candidate_application_success'))
            
        # ២. ទាញយកព័ត៌មានបច្ចុប្បន្នរបស់បេក្ខជន ដោយ JOIN ពីតារាងទាំង២
        # 💡 Table candidates: យក name_en, gender, dob
        # 💡 Table application_details: យក id_card_no, passport_no, phone_number
        cursor.execute("""
            SELECT 
                c.name_en, 
                c.gender, 
                c.dob, 
                ad.id_card_no, 
                ad.passport_no, 
                ad.phone_number
            FROM candidates c
            LEFT JOIN application_details ad ON c.application_no = ad.application_no
            WHERE c.application_no = %s
        """, (app_no,))
        
        # ចាប់យកទិន្នន័យ បើអត់មាន (ករណីមិនទាន់បំពេញ Form) ដាក់ Dictionary ទទេ
        candidate_data = cursor.fetchone() or {}
            
    except Exception as e:
        print(f"Error loading edit form: {e}")
        candidate_data = {}
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    # 💡 បោះ c_data ទៅឱ្យ HTML ដើម្បីបង្ហាញជា "ទិន្នន័យចាស់"
    return render_template('request_edit.html', app_no=app_no, c_data=candidate_data)

# ==============================================================================
# Route សម្រាប់ទទួលទិន្នន័យ (POST)
# ==============================================================================
@app.route('/candidate/submit_correction', methods=['POST'])
def submit_correction():
    if 'candidate_logged_in' not in session:
        return redirect(url_for('candidate_login_page'))
        
    app_no = session.get('candidate_app_no')
    
    # ចាប់យកទិន្នន័យ JSON ដែលបានចងក្រងរួចជាស្រេចពី Hidden Input
    requested_info_json = request.form.get('requested_info_json')
    
    # ពិនិត្យថាមានទិន្នន័យកែប្រែដែរឬទេ
    if not requested_info_json or requested_info_json == '[]':
        flash('សូមបំពេញព័ត៌មានថ្មីដែលអ្នកចង់កែប្រែយ៉ាងហោចណាស់មួយចំណុច!', 'danger')
        return redirect(url_for('candidate_request_edit'))
        
    conn = None
    cursor = None
    try:
        # បំប្លែង JSON String ទៅជា Python List ដើម្បីពិនិត្យសុពលភាព (ក្រែងលោគេ Hack ផ្ញើទិន្នន័យមកទទេ)
        changes_list = json.loads(requested_info_json)
        if not changes_list:
             flash('សូមបំពេញព័ត៌មានថ្មីយ៉ាងហោចណាស់មួយចំណុច!', 'danger')
             return redirect(url_for('candidate_request_edit'))

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert ចូល Table `correction_requests` ក្នុង column `requested_info`
        # 💡 Status នឹងដាក់ថា 'Pending' ដោយស្វ័យប្រវត្តិលុះត្រាតែ Admin Approve
        cursor.execute("""
            INSERT INTO correction_requests (application_no, requested_info, status)
            VALUES (%s, %s, 'Pending')
        """, (app_no, requested_info_json))
        conn.commit()
        
        flash('សំណើកែតម្រូវរបស់អ្នកត្រូវបានបញ្ជូនជោគជ័យ! សូមរង់ចាំការពិនិត្យពីមន្ត្រី។', 'success')
    except json.JSONDecodeError:
        flash('មានបញ្ហាជាមួយទម្រង់ទិន្នន័យដែលបានបញ្ជូន!', 'danger')
        return redirect(url_for('candidate_request_edit'))
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error saving correction request: {e}")
        flash('មានបញ្ហាក្នុងការបញ្ជូនសំណើ!', 'danger')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
    return redirect(url_for('candidate_application_success'))

import json # បើបងបាន import នៅខាងលើហើយ មិនបាច់ដាក់ទៀតទេ

import json # កុំភ្លេចប្រាកដថាបាន Import json នៅខាងលើគេនៃឯកសារ app.py ផង

# ==============================================================================
# Route សម្រាប់ Admin មើលបញ្ជីសំណើសុំកែតម្រូវទិន្នន័យ (GET)
# ==============================================================================
@app.route('/admin_correction_requests', methods=['GET'])
def admin_correction_requests():
    # ១. ឆែកមើលការ Login
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    # ២. 🔒 ឆែកសិទ្ធិ: តើគាត់មានសិទ្ធិមើល (can_view) ទំព័រនេះទេ?
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # កូដសិទ្ធិគឺ manage_correction_requests_settings
        cursor.execute("""
            SELECT 1 FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id = %s AND p.name = 'manage_correction_requests_settings' AND up.can_view = 1
        """, (session['id'],))
        has_perm = cursor.fetchone()
        
        if not has_perm and session.get('role', '').lower() != 'super admin':
            flash('អ្នកមិនមានសិទ្ធិក្នុងការចូលមើលទំព័រនេះទេ!', 'danger')
            return redirect(url_for('dashboard'))
    except Exception as e:
        print("Security Check Error:", e)
        # ការពារសុវត្ថិភាព ពេល Error ក៏មិនឱ្យចូលដែរ
        flash('មានបញ្ហាក្នុងការផ្ទៀងផ្ទាត់សិទ្ធិ!', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn is not None: conn.close()

    # ៣. ទាញយកទិន្នន័យសំណើ
    conn = None
    cursor = None
    requests_list = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # ទាញយកសំណើដែល Pending ដោយ JOIN ជាមួយ candidates
        cursor.execute("""
            SELECT 
                cr.id, 
                cr.application_no, 
                cr.requested_info, 
                cr.status, 
                cr.created_at,
                c.name_en
            FROM correction_requests cr
            LEFT JOIN candidates c ON cr.application_no = c.application_no
            WHERE cr.status = 'Pending'
            ORDER BY cr.created_at DESC
        """)
        requests_list = cursor.fetchall()
        
        # បម្លែង JSON string ទៅជា Dictionary
        for req in requests_list:
            try:
                # ការពារក្រែងលោ requested_info ជា Null ឬទទេ
                req['changes'] = json.loads(req['requested_info']) if req['requested_info'] else []
            except Exception as parse_e:
                print(f"JSON Parse Error for request ID {req['id']}: {parse_e}")
                req['changes'] = []
                
    except Exception as e:
        print(f"Error fetching admin requests: {e}")
        requests_list = []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    # ៤. បញ្ជូនទិន្នន័យទៅឱ្យ HTML បង្ហាញ
    return render_template('admin_correction_requests.html', requests=requests_list)


# ==============================================================================
# Route សម្រាប់ Admin ចុច Approve ឬ Reject (POST)
# ==============================================================================
@app.route('/admin/handle_correction', methods=['POST'])
def handle_correction():
    # ១. ត្រួតពិនិត្យការ Login
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    request_id = request.form.get('request_id')
    action = request.form.get('action') 
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) 
        
        if action == 'approve':
            cursor.execute("SELECT * FROM correction_requests WHERE id = %s", (request_id,))
            req_data = cursor.fetchone()
            
            if req_data:
                app_no = req_data['application_no']
                
                # សូមប្រាកដថាឈ្មោះ 'new_name_en' នេះត្រូវនឹង Column ក្នុង Database របស់បង
                new_name = req_data.get('new_name_en') 
                new_dob = req_data.get('new_dob')      
                new_passport = req_data.get('new_passport') 
                
                # Update ចូលតារាង candidates
                update_candidate_sql = """
                    UPDATE candidates 
                    SET name_en = COALESCE(%s, name_en),
                        dob = COALESCE(%s, dob),
                        passport_no = COALESCE(%s, passport_no)
                    WHERE application_no = %s
                """
                cursor.execute(update_candidate_sql, (new_name, new_dob, new_passport, app_no))
            
            new_status = 'Approved'
            
        elif action == 'reject':
            new_status = 'Rejected'
        else:
            flash('សកម្មភាពមិនត្រឹមត្រូវទេ!', 'danger')
            # 💡 កែចំណុចទី ១៖ ត្រលប់ទៅ admin_correction_requests វិញ
            return redirect(url_for('admin_correction_requests')) 
            
        # Update status នៅក្នុងតារាង correction_requests
        cursor.execute("""
            UPDATE correction_requests 
            SET status = %s 
            WHERE id = %s
        """, (new_status, request_id))
        
        conn.commit()
        
        if action == 'approve':
            flash('សំណើត្រូវបានអនុម័ត និងទិន្នន័យបេក្ខជនត្រូវបានកែតម្រូវជោគជ័យ!', 'success')
        else:
            flash('សំណើត្រូវបានបដិសេធដោយជោគជ័យ!', 'warning')
        
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error handling request: {e}")
        flash(f'មានបញ្ហាក្នុងការអនុវត្តសកម្មភាព: {str(e)}', 'danger')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
    # 💡 កែចំណុចទី ២៖ ត្រលប់ទៅ admin_correction_requests វិញ
    return redirect(url_for('admin_correction_requests'))

import pandas as pd # កុំភ្លេច Import Pandas នៅខាងលើគេ

# ==========================================================
# APIs សម្រាប់ទាញទិន្នន័យអាសយដ្ឋាន (AJAX) តាមតម្រូវការ
# ==========================================================
@app.route('/api/get_districts/<int:prov_id>')
def api_get_districts(prov_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ref_districts WHERE province_id = %s ORDER BY name_kh ASC", (prov_id,))
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

@app.route('/api/get_communes/<int:dist_id>')
def api_get_communes(dist_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ref_communes WHERE district_id = %s ORDER BY name_kh ASC", (dist_id,))
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

@app.route('/api/get_villages/<int:comm_id>')
def api_get_villages(comm_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ref_villages WHERE commune_id = %s ORDER BY name_kh ASC", (comm_id,))
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

# ==========================================================
# API សម្រាប់កែប្រែទិន្នន័យអាសយដ្ឋាន (Update)
# ==========================================================
@app.route('/admin/update_address', methods=['POST'])
def update_address():
    if 'loggedin' not in session: 
        return jsonify({'status': 'error', 'message': 'សូម Login ជាមុនសិន!'})
    
    data = request.get_json()
    level = data.get('level')
    record_id = data.get('id')
    code = data.get('code')
    addr_type = data.get('type')
    name_kh = data.get('name_kh')
    name_en = data.get('name_en')

    # 💡 បន្ថែម province ចូលទៅក្នុង map នេះ
    table_map = {
        'province': 'ref_provinces', 
        'district': 'ref_districts',
        'commune': 'ref_communes',
        'village': 'ref_villages'
    }
    
    if level not in table_map:
        return jsonify({'status': 'error', 'message': 'ប្រភេទកម្រិត (Level) មិនត្រឹមត្រូវ!'})
        
    table = table_map[level]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = f"UPDATE {table} SET code=%s, type=%s, name_kh=%s, name_en=%s WHERE id=%s"
        cursor.execute(query, (code, addr_type, name_kh, name_en, record_id))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'កែប្រែទិន្នន័យបានជោគជ័យ!'})
    except Exception as e:
        print(f"Update Address Error: {e}")
        return jsonify({'status': 'error', 'message': 'មានបញ្ហាក្នុងការកែប្រែ! សូមប្រាកដថាលេខកូដ (Code) មិនស្ទួនគ្នា។'})
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn is not None: conn.close()


# ==============================================================
# 💡 Route សម្រាប់បង្ហាញទំព័រគ្រប់គ្រងអាសយដ្ឋាន (GET)
# ==============================================================
@app.route('/manage_addresses', methods=['GET'])
def manage_addresses():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    # 🔒 ឆែកសិទ្ធិ: តើគាត់មានសិទ្ធិមើល (can_view) ទំព័រនេះទេ?
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 1 FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id = %s AND p.name = 'manage_addresses' AND up.can_view = 1
        """, (session['id'],))
        has_perm = cursor.fetchone()
        
        if not has_perm and session.get('role', '').lower() != 'super admin':
            flash('អ្នកមិនមានសិទ្ធិក្នុងការចូលមើលទំព័រនេះទេ!', 'danger')
            return redirect(url_for('dashboard'))
            
        # ១. ទាញយកបញ្ជីខេត្តមកបង្ហាញក្នុង តារាង/Dropdown
        cursor.execute("SELECT * FROM ref_provinces ORDER BY code ASC")
        provinces = cursor.fetchall()

        # ២. 💡 គណនាតួលេខសរុប (stats) ដើម្បីបញ្ជូនទៅ HTML
        cursor.execute("SELECT COUNT(*) as count FROM ref_provinces")
        prov_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM ref_districts")
        dist_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM ref_communes")
        comm_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM ref_villages")
        vill_count = cursor.fetchone()['count']
        
        # បង្កើតជា Dictionary សម្រាប់អថេរ stats
        stats = {
            'provinces': prov_count,
            'districts': dist_count,
            'communes': comm_count,
            'villages': vill_count
        }
        
    except Exception as e:
        print("Address Page Error:", e)
        provinces = []
        stats = {'provinces': 0, 'districts': 0, 'communes': 0, 'villages': 0}
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn is not None: conn.close()

    # 💡 បន្ថែម stats=stats ទៅក្នុង render_template
    return render_template('manage_addresses.html', provinces=provinces, stats=stats)


# ==============================================================
# Route សម្រាប់ Import អាសយដ្ឋានពី Excel (POST)
# ==============================================================
@app.route('/admin/import_addresses_excel', methods=['POST'])
def import_addresses_excel():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    # 🔒 [ជាន់ទី ១] ឆែកសិទ្ធិ៖ តើគាត់មានសិទ្ធិកែប្រែ/បញ្ចូលអាសយដ្ឋានទេ?
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 1 FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id = %s AND p.name = 'manage_addresses' AND (up.can_create = 1 OR up.can_edit = 1)
        """, (session['id'],))
        has_perm = cursor.fetchone()
        
        if not has_perm and session.get('role', '').lower() != 'super admin':
            flash('អ្នកមិនមានសិទ្ធិក្នុងការ Import អាសយដ្ឋាននេះទេ!', 'danger')
            return redirect(url_for('manage_addresses'))
    except Exception as e:
        print("Security Check Error (Import Address):", e)
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn is not None: conn.close()

    file = request.files.get('excel_file')
    clear_data = request.form.get('clear_data')

    if not file or file.filename == '':
        flash('សូមជ្រើសរើស File Excel ជាមុនសិន!', 'danger')
        return redirect(url_for('manage_addresses'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 💡 [ជាន់ទី ២] លុបទិន្នន័យចាស់ចេញដោយសុវត្ថិភាព ជៀសវាង Error Foreign Key
        if clear_data == 'yes':
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            # លុបពីក្រោមឡើងលើ (កូន ទៅ មេ)
            cursor.execute("DELETE FROM ref_villages;")
            cursor.execute("ALTER TABLE ref_villages AUTO_INCREMENT = 1;")
            
            cursor.execute("DELETE FROM ref_communes;")
            cursor.execute("ALTER TABLE ref_communes AUTO_INCREMENT = 1;")
            
            cursor.execute("DELETE FROM ref_districts;")
            cursor.execute("ALTER TABLE ref_districts AUTO_INCREMENT = 1;")
            
            cursor.execute("DELETE FROM ref_provinces;")
            cursor.execute("ALTER TABLE ref_provinces AUTO_INCREMENT = 1;")
            
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()

        # អាន File Excel គ្រប់ Sheets ទាំងអស់
        xls = pd.ExcelFile(file)
        
        PROVINCE_KH_MAP = {
            "Banteay Meanchey": "បន្ទាយមានជ័យ", "Battambang": "បាត់ដំបង", "Kampong Cham": "កំពង់ចាម",
            "Kampong Chhnang": "កំពង់ឆ្នាំង", "Kampong Speu": "កំពង់ស្ពឺ", "Kampong Thom": "កំពង់ធំ",
            "Kampot": "កំពត", "Kandal": "កណ្តាល", "Koh Kong": "កោះកុង", "Kratie": "ក្រចេះ",
            "Mondul Kiri": "មណ្ឌលគិរី", "Phnom Penh": "ភ្នំពេញ", "Preah Vihear": "ព្រះវិហារ",
            "Prey Veng": "ព្រៃវែង", "Pursat": "ពោធិ៍សាត់", "Ratanak Kiri": "រតនគិរី",
            "Siemreap": "សៀមរាប", "Preah Sihanouk": "ព្រះសីហនុ", "Stung Treng": "ស្ទឹងត្រែង",
            "Svay Rieng": "ស្វាយរៀង", "Takeo": "តាកែវ", "Oddar Meanchey": "ឧត្តរមានជ័យ",
            "Kep": "កែប", "Pailin": "ប៉ៃលិន", "Tboung Khmum": "ត្បូងឃ្មុំ"
        }

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=2)
            
            # ចាប់យកលេខកូដ និងឈ្មោះពីចំណងជើង Sheet
            sheet_parts = sheet_name.split('.', 1)
            prov_code = sheet_parts[0].strip() if len(sheet_parts) > 1 else ''
            prov_name_en = sheet_parts[1].strip() if len(sheet_parts) > 1 else sheet_name.strip()
            
            prov_name_kh = PROVINCE_KH_MAP.get(prov_name_en, prov_name_en)
            prov_type = "រាជធានី" if prov_name_en == "Phnom Penh" else "ខេត្ត"
            
            cursor.execute("INSERT INTO ref_provinces (code, type, name_kh, name_en) VALUES (%s, %s, %s, %s)", 
                           (prov_code, prov_type, prov_name_kh, prov_name_en))
            current_prov_id = cursor.lastrowid
            
            current_dist_id = None
            current_comm_id = None

            # រត់ Loop តាមជួរនីមួយៗ
            for index, row in df.iterrows():
                if pd.isna(row.get('Type')): continue
                
                # 💡 [ជាន់ទី ៣] សម្អាតទិន្នន័យ: បើវាចេញ nan (NaN របស់ pandas) ឱ្យក្លាយជា text ទទេវិញ
                row_type = str(row['Type']).strip()
                code = '' if pd.isna(row.get('Code')) else str(row.get('Code')).strip().replace('.0', '')
                name_kh = '' if pd.isna(row.get('Name (Khmer)')) else str(row.get('Name (Khmer)')).strip()
                name_en = '' if pd.isna(row.get('Name (Latin)')) else str(row.get('Name (Latin)')).strip()

                if row_type in ['ស្រុក', 'ក្រុង', 'ខណ្ឌ']:
                    cursor.execute("INSERT INTO ref_districts (province_id, code, type, name_kh, name_en) VALUES (%s, %s, %s, %s, %s)", 
                                   (current_prov_id, code, row_type, name_kh, name_en))
                    current_dist_id = cursor.lastrowid
                    current_comm_id = None # Reset ឃុំពេលឆ្លងស្រុកថ្មី
                    
                elif row_type in ['ឃុំ', 'សង្កាត់']:
                    if current_dist_id:
                        cursor.execute("INSERT INTO ref_communes (district_id, code, type, name_kh, name_en) VALUES (%s, %s, %s, %s, %s)", 
                                       (current_dist_id, code, row_type, name_kh, name_en))
                        current_comm_id = cursor.lastrowid
                        
                elif row_type == 'ភូមិ':
                    if current_comm_id:
                        cursor.execute("INSERT INTO ref_villages (commune_id, code, type, name_kh, name_en) VALUES (%s, %s, %s, %s, %s)", 
                                       (current_comm_id, code, row_type, name_kh, name_en))

        conn.commit()
        flash('នាំចូលទិន្នន័យអាសយដ្ឋានពី Excel បានជោគជ័យ!', 'success')
        return redirect(url_for('manage_addresses'))

    except Exception as e:
        print(f"Excel Import Error: {e}")
        if 'conn' in locals() and conn is not None: conn.rollback()
        flash(f'មានបញ្ហាក្នុងការ Import! សូមពិនិត្យមើលទម្រង់ File Excel ឡើងវិញ។ Error: {e}', 'danger')
        return redirect(url_for('manage_addresses'))
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn is not None: conn.close()

# ==========================================================
# ទំព័ររុករកអាសយដ្ឋានដោយការចុច (Drill-down Address Explorer)
# ==========================================================
@app.route('/search_address')
def search_address_page():
    # ប្រសិនបើចង់ការពារទំព័រ អាចបើកកូដខាងក្រោមនេះបាន
    # if 'loggedin' not in session:
    #     return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # ទាញយកខេត្តទាំងអស់បញ្ជូនទៅទំព័រ
        cursor.execute("SELECT * FROM ref_provinces ORDER BY name_kh ASC")
        provinces = cursor.fetchall()
        
        return render_template('search_address.html', provinces=provinces)
    except Exception as e:
        print(f"Error loading search page: {e}")
        return "មានបញ្ហាប្រព័ន្ធ"
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn is not None: conn.close()

#

# ==============================================================================
# API សម្រាប់ឆែកទិន្នន័យស្ទួន (Email, Facebook, TikTok) មុនពេល Submit
# ==============================================================================
@app.route('/api/check_duplicate', methods=['POST'])
def check_duplicate():
    if 'candidate_logged_in' not in session:
        return jsonify({'exists': False, 'error': 'Unauthorized'})

    data = request.get_json()
    field = data.get('field') # អាចជា 'email', 'facebook_link', ឬ 'tiktok_link'
    value = data.get('value')
    app_no = session.get('candidate_app_no') # លេខរៀងបេក្ខជនបច្ចុប្បន្ន

    # ការពារសុវត្ថិភាព (អនុញ្ញាតតែ ៣ Column នេះប៉ុណ្ណោះ)
    if field not in ['email', 'facebook_link', 'tiktok_link'] or not value:
        return jsonify({'exists': False})

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # ឆែកមើលក្នុង DB ថាតើមានទិន្នន័យនេះឬនៅ? (លើកលែងទិន្នន័យរបស់ខ្លួនឯង ក្រែងលោគាត់គ្រាន់តែ Edit Form ចាស់)
        query = f"SELECT application_no FROM application_details WHERE {field} = %s AND application_no != %s LIMIT 1"
        cursor.execute(query, (value, app_no))
        result = cursor.fetchone()
        
        if result:
            return jsonify({'exists': True})
        else:
            return jsonify({'exists': False})
    except Exception as e:
        print(f"Error checking duplicate: {e}")
        return jsonify({'exists': False})
    finally:
        cursor.close()
        conn.close()    

import io
import math
from datetime import date, timedelta
from flask import render_template, request, session, redirect, url_for

# ==============================================================================
# Admin Route: បង្ហាញទំព័រគ្រប់គ្រងការដាក់ពាក្យ និង ការកំណត់ប្រព័ន្ធ (Settings)
# ==============================================================================
import io
import math
from datetime import date, timedelta
from flask import render_template, request, session, redirect, url_for

# ==============================================================================
# Admin Route: បង្ហាញទំព័រគ្រប់គ្រងការដាក់ពាក្យ និង ការកំណត់ប្រព័ន្ធ (Settings)
# ==============================================================================
# ==============================================================================
# Admin Route: បង្ហាញទំព័រគ្រប់គ្រងការដាក់ពាក្យ និង ការកំណត់ប្រព័ន្ធ (Settings)
# ==============================================================================
@app.route('/admin/manage_applications', methods=['GET'])
def admin_manage_applications():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    # ចាប់យកតម្លៃពី Form ស្វែងរក
    search_query = request.args.get('search_query', '').strip()
    selected_date = request.args.get('apply_date', '').strip()
    
    # បើ request.args គ្មានទិន្នន័យអ្វីទាំងអស់ ទើបដាក់ថ្ងៃបច្ចុប្បន្នជា Default
    if len(request.args) == 0:
        selected_date = date.today().strftime('%Y-%m-%d')
        
    selected_status = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)

    limit = 20
    offset = (page - 1) * limit
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # =======================================================
        # ផ្នែកក៖ ការគ្រប់គ្រងម៉ោងសម្រាប់ផ្ទាំង Settings Modal
        # =======================================================
        cursor.execute("SELECT * FROM system_settings WHERE id = 1")
        settings = cursor.fetchone()

        if settings:
            time_fields = ['am_start_time', 'am_end_time', 'pm_start_time', 'pm_end_time']
            for field in time_fields:
                val = settings.get(field)
                if val is not None:
                    if isinstance(val, timedelta):
                        total_seconds = int(val.total_seconds())
                        hours, remainder = divmod(total_seconds, 3600)
                        minutes, _ = divmod(remainder, 60)
                        settings[field] = f"{hours:02d}:{minutes:02d}"
                    else:
                        settings[field] = str(val).zfill(8)[:5]
                else:
                    settings[field] = ""
        else:
            settings = {}

        # =======================================================
        # ផ្នែកខ៖ សាងសង់លក្ខខណ្ឌស្វែងរក (Dynamic WHERE Clauses)
        # =======================================================
        where_clauses = []
        stats_where_clauses = []  # 🌟 [វះកាត់] បង្កើត Where ដាច់ឡែកសម្រាប់តែរាប់ស្ថិតិ
        params = []
        stats_params = []
        
        # ក. ស្វែងរកតាមពាក្យ (Keyword)
        if search_query:
            kw_sql = """
                (c.application_no LIKE %s OR 
                 c.name_en LIKE %s OR 
                 a.last_name_kh LIKE %s OR 
                 a.first_name_kh LIKE %s OR 
                 a.id_card_no LIKE %s OR 
                 a.phone_number LIKE %s)
            """
            search_term = f"%{search_query}%"
            
            where_clauses.append(kw_sql)
            stats_where_clauses.append(kw_sql)
            
            params.extend([search_term] * 6)
            stats_params.extend([search_term] * 6)
            
        # ខ. ស្វែងរកតាមកាលបរិច្ឆេទ
        if selected_date:
            dt_sql = "DATE(q.created_at) = %s"
            
            where_clauses.append(dt_sql)
            stats_where_clauses.append(dt_sql)
            
            params.append(selected_date)
            stats_params.append(selected_date)
            
        # គ. ស្វែងរកតាមស្ថានភាព (ដាក់តែក្នុង Main Query មិនដាក់ក្នុង Stats Query ទេ)
        if selected_status:
            where_clauses.append("a.status_id = %s") 
            params.append(selected_status)
            
        where_sql = ""
        if where_clauses:
            where_sql = " AND " + " AND ".join(where_clauses)

        stats_where_sql = ""
        if stats_where_clauses:
            stats_where_sql = " AND " + " AND ".join(stats_where_clauses)
            
        # =======================================================
        # ផ្នែកគ៖ ទាញយកស្ថិតិរួម (Stats Card ខាងលើតារាង + ស្ថិតិចម្រាញ់)
        # =======================================================
        # ១. ស្ថិតិសរុបប្រចាំប្រព័ន្ធទាំងមូល (កាតធំទាំង ៤ ខាងលើ)
        stats_sql = """
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN c.gender = 'F' THEN 1 ELSE 0 END) as total_records_female,
                
                SUM(CASE WHEN a.status_id = 1 OR a.status_id IS NULL THEN 1 ELSE 0 END) as total_pending,
                SUM(CASE WHEN (a.status_id = 1 OR a.status_id IS NULL) AND c.gender = 'F' THEN 1 ELSE 0 END) as total_pending_female,
                
                SUM(CASE WHEN a.status_id = 2 THEN 1 ELSE 0 END) as total_approved,
                SUM(CASE WHEN a.status_id = 2 AND c.gender = 'F' THEN 1 ELSE 0 END) as total_approved_female,
                
                SUM(CASE WHEN a.status_id = 3 THEN 1 ELSE 0 END) as total_rejected,
                SUM(CASE WHEN a.status_id = 3 AND c.gender = 'F' THEN 1 ELSE 0 END) as total_rejected_female
            FROM candidates c
            INNER JOIN application_details a ON c.application_no = a.application_no
        """
        cursor.execute(stats_sql)
        stats = cursor.fetchone()

        # ២. 🌟 ស្ថិតិចម្រាញ់ជាក់ស្តែង (Dynamic Stats សម្រាប់ Master Checkbox)
        # រាប់តែអ្នក Pending និង ស្រី ទៅតាមថ្ងៃខែ ឬពាក្យស្វែងរក ដោយមិនខ្វល់ពី Dropdown ស្ថានភាព
        filtered_stats_sql = f"""
            SELECT 
                COUNT(DISTINCT c.application_no) as real_pending_total,
                SUM(CASE WHEN c.gender = 'F' THEN 1 ELSE 0 END) as real_pending_female
            FROM candidates c
            INNER JOIN application_details a ON c.application_no = a.application_no
            LEFT JOIN queue_tickets q ON c.application_no = q.application_no 
                 AND q.id = (SELECT MAX(id) FROM queue_tickets WHERE application_no = c.application_no)
            WHERE (a.status_id = 1 OR a.status_id IS NULL) {stats_where_sql}
        """
        cursor.execute(filtered_stats_sql, stats_params)
        filtered_stats = cursor.fetchone()
        
        # =======================================================
        # ផ្នែកឃ៖ រាប់ចំនួនទិន្នន័យ (Count) សម្រាប់ធ្វើ Pagination
        # =======================================================
        # =======================================================
        # ផ្នែកឃ៖ រាប់ចំនួនទិន្នន័យ (Count) និងចំនួនស្រី តាមតម្រងបច្ចុប្បន្ន
        # =======================================================
        count_sql = f"""
            SELECT 
                COUNT(DISTINCT c.application_no) as total,
                SUM(CASE WHEN c.gender = 'F' THEN 1 ELSE 0 END) as total_female
            FROM candidates c
            INNER JOIN application_details a ON c.application_no = a.application_no
            LEFT JOIN queue_tickets q ON c.application_no = q.application_no 
                 AND q.id = (SELECT MAX(id) FROM queue_tickets WHERE application_no = c.application_no)
            WHERE 1=1 {where_sql}
        """
        cursor.execute(count_sql, params)
        count_row = cursor.fetchone()
        
        total_filtered = count_row['total'] or 0
        total_filtered_female = int(count_row['total_female']) if count_row['total_female'] is not None else 0
        total_pages = math.ceil(total_filtered / limit) if total_filtered > 0 else 1
        
        # =======================================================
        # ផ្នែកង៖ ទាញយកទិន្នន័យជាក់ស្តែង (Main Data)
        # =======================================================
        data_sql = f"""
            SELECT 
                c.application_no, c.name_en, c.gender,
                c.job_app_present, c.latest_scan_photo, c.original_photo_path,
                a.last_name_kh, a.first_name_kh, a.id_card_no, a.phone_number, a.new_photo_file_path,
                a.status_id, a.remark, 
                q.created_at
            FROM candidates c
            INNER JOIN application_details a ON c.application_no = a.application_no
            LEFT JOIN queue_tickets q ON c.application_no = q.application_no 
                 AND q.id = (SELECT MAX(id) FROM queue_tickets WHERE application_no = c.application_no)
            WHERE 1=1 {where_sql}
            ORDER BY q.created_at DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(data_sql, params + [limit, offset])
        applications = cursor.fetchall()

        # =======================================================
        # ផ្នែកច៖ ទាញយកបញ្ជីយោង (Reference Data) សម្រាប់ Dropdowns
        # =======================================================
        cursor.execute("SELECT * FROM ref_app_reject_reasons WHERE is_active = 1 ORDER BY id ASC")
        reject_reasons = cursor.fetchall()

        cursor.execute("SELECT id, status_name_kh, status_name_en FROM ref_app_status ORDER BY id ASC")
        app_statuses = cursor.fetchall()

        return render_template('admin/manage_applications.html',
                               applications=applications,
                               page=page,
                               total_pages=total_pages,
                               total_records=stats['total_records'] or 0,
                               total_pending=stats['total_pending'] or 0,
                               total_approved=stats['total_approved'] or 0,
                               total_rejected=stats['total_rejected'] or 0,
                               #total_records=stats['total_records'] or 0,
                               total_records_female=stats['total_records_female'] or 0,
                               #total_pending=stats['total_pending'] or 0,
                               total_pending_female=stats['total_pending_female'] or 0,
                               #total_approved=stats['total_approved'] or 0,
                               total_approved_female=stats['total_approved_female'] or 0,
                               #total_rejected=stats['total_rejected'] or 0,
                               total_rejected_female=stats['total_rejected_female'] or 0,
                               
                               # 🌟 បញ្ជូនទិន្នន័យពិតប្រាកដប្រចាំតម្រង ទៅឱ្យ Frontend ប្រើប្រាស់
                               real_pending_total=filtered_stats['real_pending_total'] or 0,
                               real_pending_female=filtered_stats['real_pending_female'] or 0,
                               current_total=total_filtered,
                               current_female=total_filtered_female,
                               selected_date=selected_date,
                               selected_status=selected_status,
                               search_query=search_query,
                               settings=settings,
                               reject_reasons=reject_reasons,
                               app_statuses=app_statuses)
    except Exception as e:
        import traceback
        print(f"Error fetching applications: {e}")
        print(traceback.format_exc())
        return "មានបញ្ហាប្រព័ន្ធ សូមឆែកមើល Terminal។"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ==============================================================================
# Admin Route: មើលព័ត៌មានលម្អិតរបស់បេក្ខជន (View Application)
# ==============================================================================
# ==============================================================================
# Route: មើលព័ត៌មានលម្អិតបេក្ខជន (Admin View)
# ==============================================================================
# ==============================================================================
# Route: មើលព័ត៌មានលម្អិតបេក្ខជន (Admin View)
# ==============================================================================
@app.route('/admin/view_application/<app_no>')
def view_application(app_no):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ១. ទាញយកព័ត៌មានបេក្ខជន + Application Details
        # 🔴 [កែតម្រូវ] បានបន្ថែម c.original_photo_path ចូលដើម្បីទាញយករូបភាពដើមមកបង្ហាញ
        cursor.execute("""
            SELECT 
                c.application_no, c.name_en, c.gender, c.dob, c.industry, 
                c.job_app_present, c.job_app_time, c.job_app_status, 
                c.latest_scan_photo, c.original_photo_path,
                a.id AS detail_id, 
                COALESCE(a.last_name_kh, c.name_kh_last) AS last_name_kh, 
                COALESCE(a.first_name_kh, c.name_kh_first) AS first_name_kh, 
                COALESCE(a.id_card_no, c.id_card_no) AS id_card_no, 
                COALESCE(a.phone_number, c.phone_number) AS phone_number,
                COALESCE(a.passport_no, c.passport_no) AS passport_no,
                a.height, a.weight, a.marital_status, a.email, 
                a.province_id, a.district_id, a.commune_id, a.village_id,
                a.passport_issue_date, a.bank_id, a.bank_account_no,
                a.new_photo_file_path, a.status_id, a.remark
            FROM candidates c
            LEFT JOIN application_details a ON c.application_no = a.application_no
            WHERE c.application_no = %s
        """, (app_no,))
        candidate = cursor.fetchone()
        
        if not candidate:
            flash("មិនមានទិន្នន័យបេក្ខជននេះទេ", "warning")
            return redirect(url_for('admin_manage_applications'))

        # ២. ទាញយកព័ត៌មានគ្រួសារ (family_members) ដោយផ្អែកលើ relationship_id
        family = {'father': None, 'mother': None, 'spouse': None, 'guarantor': None}
        try:
            cursor.execute("""
                SELECT f.last_name_kh, f.first_name_kh, f.last_name_en, f.first_name_en, 
                       f.phone_number, f.status, f.guarantor_role, r.relation_name_en 
                FROM family_members f
                LEFT JOIN ref_relationships r ON f.relationship_id = r.id
                WHERE f.application_no = %s
            """, (app_no,))
            family_records = cursor.fetchall()
            
            for member in family_records:
                rel = member.get('relation_name_en')
                role = member.get('guarantor_role')
                
                # បែងចែកសមាជិកគ្រួសារ
                if rel == 'Father': 
                    family['father'] = member
                elif rel == 'Mother': 
                    family['mother'] = member
                elif rel in ['Husband', 'Wife']: 
                    family['spouse'] = member
                    
                # បែងចែកអ្នកធានា (Guarantor) ដាច់ដោយឡែក
                if role == 'Guarantor': 
                    family['guarantor'] = member
        except Exception as eFam:
            print(f"Error loading family data: {eFam}")

        # ៣. ទាញយកទីតាំង (Address)
        address = {}
        if candidate.get('province_id') and candidate.get('district_id') and candidate.get('commune_id') and candidate.get('village_id'):
            try:
                cursor.execute("""
                    SELECT v.name_kh as vill_kh, c.name_kh as comm_kh, d.name_kh as dist_kh, p.name_kh as prov_kh
                    FROM ref_provinces p, ref_districts d, ref_communes c, ref_villages v
                    WHERE p.id=%s AND d.id=%s AND c.id=%s AND v.id=%s
                """, (candidate.get('province_id'), candidate.get('district_id'), candidate.get('commune_id'), candidate.get('village_id')))
                address = cursor.fetchone() or {}
            except Exception as eAddr:
                print(f"Error loading address data: {eAddr}")

        return render_template('view_application.html', 
                               candidate=candidate, 
                               family=family,
                               address=address)
        
    except Exception as e:
        import traceback
        print("\n" + "="*50)
        print(f"CRITICAL ERROR in view_application:")
        print(traceback.format_exc())
        print("="*50 + "\n")
        # 💡 បង្ហាញ Error ពិតប្រាកដទៅកាន់ Admin ដើម្បីងាយស្រួលដឹងបញ្ហា
        flash(f"មានបញ្ហាបច្ចេកទេស៖ {str(e)}", "danger") 
        return redirect(url_for('admin_manage_applications'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

import io
import openpyxl
from datetime import date
from flask import request, jsonify, send_file, session, redirect, url_for, render_template
import math

# ==============================================================================
# 🔴 Update ស្ថានភាពម្តងម្នាក់ (មានភ្ជាប់មូលហេតុ)
# ==============================================================================
@app.route('/admin/update_application_status', methods=['POST'])
def update_application_status():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'សូមចូលគណនី (Login) ជាមុនសិន!'})
        
    data = request.get_json()
    app_no = data.get('application_no')
    new_status = data.get('status') 
    remark = data.get('remark', None) # 🔴 ចាប់យកមូលហេតុពី Frontend
    
    if not app_no or new_status not in ['Approved', 'Rejected', 'Pending']:
        return jsonify({'status': 'error', 'message': 'ទិន្នន័យមិនត្រឹមត្រូវ'})
        
    status_id_map = {'Pending': 1, 'Approved': 2, 'Rejected': 3}
    new_status_id = status_id_map[new_status]
    db_status = new_status.upper() 
    
    # 💡 បើ Status មិនមែនបដិសេធទេ គឺត្រូវ Clear មូលហេតុចោល
    final_remark = remark if new_status == 'Rejected' else None
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        conn.start_transaction()
        cursor.execute("UPDATE candidates SET job_app_status = %s WHERE application_no = %s", (db_status, app_no))
        # 🔴 បន្ថែមការ Update ជួរឈរ remark
        cursor.execute("UPDATE application_details SET status_id = %s, remark = %s WHERE application_no = %s", (new_status_id, final_remark, app_no))
        
        conn.commit()
        return jsonify({'status': 'success', 'message': f'បានផ្លាស់ប្តូរស្ថានភាពទៅជា {new_status}'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

# ====================================================================
# API សម្រាប់ផ្លាស់ប្តូរស្ថានភាព (ទាញថ្ងៃខែពី queue_tickets + Auto Sync)
# ====================================================================
@app.route('/admin/bulk_update_status', methods=['POST'])
def bulk_update_status():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.json
    application_nos = data.get('application_nos', [])
    target_date = data.get('target_date')  # ទាញយកថ្ងៃខែដែលអ្នកគ្រប់គ្រងបានជ្រើសរើស
    status = data.get('status')
    remark = data.get('remark', '')

    if not status:
        return jsonify({'status': 'error', 'message': 'ទិន្នន័យមិនត្រឹមត្រូវ'})

    # កំណត់ status_id
    if status == 'Approved':
        status_id = 2
    elif status == 'Rejected':
        status_id = 3
    elif status == 'Pending':
        status_id = 1
    else:
        return jsonify({'status': 'error', 'message': 'ទិន្នន័យមិនត្រឹមត្រូវ'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # ----------------------------------------------------------------
        # ជម្រើសទី ១៖ អនុម័តម្តងមួយថ្ងៃពេញ (JOIN ជាមួយ queue_tickets)
        # ----------------------------------------------------------------
        if target_date:
            # ១. ស្វែងរក application_no ទាំងអស់ដែលបានបង្កើត Queue ក្នុងថ្ងៃនោះ ហើយនៅ Pending (1)
            cursor.execute("""
                SELECT a.application_no 
                FROM application_details a
                INNER JOIN queue_tickets q ON a.application_no = q.application_no
                WHERE DATE(q.created_at) = %s AND a.status_id = 1
            """, (target_date,))
            
            rows = cursor.fetchall()
            apps_to_update = [row[0] for row in rows]

            if not apps_to_update:
                return jsonify({'status': 'error', 'message': f'មិនមានពាក្យស្នើសុំរង់ចាំ (Pending) ក្នុងថ្ងៃ {target_date} ទេ'})

            # ២. អាប់ដេត status_id ក្នុង application_details សម្រាប់បញ្ជីឈ្មោះទាំងនោះ
            format_strings = ','.join(['%s'] * len(apps_to_update))
            cursor.execute(f"""
                UPDATE application_details 
                SET status_id = %s, remark = %s 
                WHERE application_no IN ({format_strings})
            """, [status_id, remark] + apps_to_update)

            # ៣. [វះកាត់ទី ១] AUTO-SYNC បាញ់វត្តមានចូលតារាង candidates ស្វ័យប្រវត្តិ
            if status == 'Approved':
                cursor.execute(f"""
                    UPDATE candidates 
                    SET job_app_present = 1, 
                        job_app_status = 'APPROVED', 
                        job_app_time = NOW() 
                    WHERE application_no IN ({format_strings})
                """, tuple(apps_to_update))

        # ----------------------------------------------------------------
        # ជម្រើសទី ២៖ អនុម័តតាម Checkbox ធម្មតា
        # ----------------------------------------------------------------
        elif application_nos:
            for app_no in application_nos:
                if status == 'Pending':
                    cursor.execute("""
                        UPDATE application_details 
                        SET status_id = %s, remark = NULL 
                        WHERE application_no = %s
                    """, (status_id, app_no))
                else:
                    cursor.execute("""
                        UPDATE application_details 
                        SET status_id = %s, remark = %s 
                        WHERE application_no = %s
                    """, (status_id, remark, app_no))

                # AUTO-SYNC សម្រាប់បេក្ខជននីមួយៗ
                if status == 'Approved':
                    cursor.execute("""
                        UPDATE candidates 
                        SET job_app_present = 1, 
                            job_app_status = 'APPROVED', 
                            job_app_time = NOW() 
                        WHERE application_no = %s
                    """, (app_no,))
        else:
            return jsonify({'status': 'error', 'message': 'សូមជ្រើសរើសបេក្ខជន ឬ កាលបរិច្ឆេទ'})

        conn.commit()
        return jsonify({'status': 'success', 'message': f'បានអនុម័ត និងធ្វើសមកាលកម្មវត្តមានជោគជ័យ ១០០%'})
    
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

# ==============================================================================
# 2. Route កែសម្រួលថ្មី៖ សម្រាប់ Export Excel ពាក្យសុំស្វែងរកការងារ (Job Applications)
# ==============================================================================
import io
import re
from datetime import datetime, date
from flask import request, redirect, url_for, session, flash, send_file
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side



# 💡 ១. ប្តូរឈ្មោះ Route ឱ្យចំគោលដៅ ឈប់ឱ្យច្រឡំនឹង Skill Test
@app.route('/download_application_report', methods=['POST'])
def download_application_report(): 
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    import io
    from datetime import datetime, date, timedelta

    # ==============================================================
    # 🔒 [ជាន់ទី ២] កូដការពារសុវត្ថិភាព: ឆែកមើលថាតើគាត់មានសិទ្ធិទាញយកទេ?
    # ==============================================================
    try:
        from app import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 1 FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id = %s AND p.name = 'download_application_report' AND up.can_view = 1
        """, (session['id'],))
        has_perm = cursor.fetchone()
        
        if not has_perm and session.get('role_name', '').lower() != 'super admin':
            flash('អ្នកមិនមានសិទ្ធិក្នុងការទាញយករបាយការណ៍នេះទេ!', 'danger')
            return redirect(url_for('admin_manage_applications'))
            
    except Exception as e:
        print("Security Check Error:", e)
    # ==============================================================

    exporter_name = session.get('full_name', 'Admin')
    current_datetime = datetime.now().strftime('%d-%m-%Y %H:%M:%S')

    export_type = request.form.get('export_type')
    report_format = request.form.get('report_format')
    custom_title = request.form.get('custom_title', 'របាយការណ៍បេក្ខជនបានដាក់ពាក្យស្វែងរកការងារ')
    
    # 🌟 ចាប់យកតម្រងពី UI (Filter Context)
    ui_status = request.form.get('ui_status', '').strip()
    ui_search = request.form.get('ui_search', '').strip()
    
    conditions = []
    params = []

    # ១. លក្ខខណ្ឌកាលបរិច្ឆេទ
    if export_type == 'today':
        # ប្រើប្រាស់ថ្ងៃខែពី UI ផ្ទាល់ ជំនួសឱ្យ date.today() ដែលចាក់សោរ
        target_date = request.form.get('start_date') or date.today().strftime('%Y-%m-%d')
        conditions.append("DATE(q.created_at) = %s")
        params.append(target_date)
    elif export_type == 'custom':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        if start_date and end_date:
            conditions.append("DATE(q.created_at) BETWEEN %s AND %s")
            params.extend([start_date, end_date])

    # ២. 🌟 លក្ខខណ្ឌស្ថានភាព (Status Filter)
    if ui_status:
        conditions.append("a.status_id = %s")
        params.append(ui_status)
    else:
        # បើមិនបានរើសស្ថានភាពទេ ទើបយើងទាញយកតែអ្នក Approved និង Pending ធម្មតា
        conditions.append("c.job_app_status IN ('Approved', 'APPROVED', 'Pending', 'PENDING')")

    # ៣. 🌟 លក្ខខណ្ឌស្វែងរក (Search Query Filter)
    if ui_search:
        conditions.append("""
            (c.application_no LIKE %s OR 
             c.name_en LIKE %s OR 
             a.last_name_kh LIKE %s OR 
             a.first_name_kh LIKE %s OR 
             a.id_card_no LIKE %s OR 
             a.phone_number LIKE %s)
        """)
        search_term = f"%{ui_search}%"
        params.extend([search_term] * 6)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    from app import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        sql = f"""
            SELECT 
                c.application_no, c.name_en, c.gender, c.dob, c.job_app_status,
                MAX(a.last_name_kh) as last_name_kh, MAX(a.first_name_kh) as first_name_kh, 
                MAX(a.id_card_no) as id_card_no, MAX(a.phone_number) as phone_number, MAX(a.email) as email,
                MAX(a.facebook_link) as facebook_link, MAX(a.tiktok_link) as tiktok_link, 
                MAX(a.height) as height, MAX(a.weight) as weight, MAX(a.marital_status) as marital_status,
                
                (SELECT MAX(children_count) FROM family_members WHERE application_no = c.application_no) AS children_count,
                
                MAX(a.passport_no) as passport_no, MAX(a.passport_issue_date) as passport_issue_date,
                MAX(a.address_detail) as address_detail,
                MAX(a.bank_account_no) as bank_account_no, 
                MAX(a.worked_in_korea_last_5yrs) as worked_in_korea_last_5yrs,
                MAX(a.alien_registration_no) as alien_registration_no,
                MAX(a.khmer_school_name) as khmer_school_name,
                MAX(a.korean_school_name) as korean_school_name,
                MAX(rel.level_name_en) as education_level_en, 
                MAX(ksp.name_en) as khmer_school_prov, 
                MAX(kosp.name_en) as korean_school_prov, 
                MAX(rb.swift_code) as swift_code,
                MAX(rb.bank_full_name) as bank_full_name,
                
                MAX(rp.name_kh) AS prov_name_kh, MAX(rd.name_kh) AS dist_name_kh, 
                MAX(rc.name_kh) AS comm_name_kh, MAX(rv.name_kh) AS vill_name_kh,
                MAX(rp.name_en) AS prov_name_en,
                
                MAX(fd.last_name_kh) AS f_last_kh, MAX(fd.first_name_kh) AS f_first_kh, 
                MAX(fd.phone_number) AS f_phone, MAX(fd.status) AS f_status,
                MAX(f_occ.job_name_kh) AS f_job_kh, MAX(f_occ.job_name_en) AS f_job_en,

                MAX(f_rp.name_kh) AS p_prov_kh, MAX(f_rd.name_kh) AS p_dist_kh, 
                MAX(f_rc.name_kh) AS p_comm_kh, MAX(f_rv.name_kh) AS p_vill_kh,
                MAX(f_rp.name_en) AS p_prov_en, MAX(f_rd.name_en) AS p_dist_en, 
                MAX(f_rc.name_en) AS p_comm_en, MAX(f_rv.name_en) AS p_vill_en,
                
                MAX(fm.last_name_kh) AS m_last_kh, MAX(fm.first_name_kh) AS m_first_kh, 
                MAX(fm.phone_number) AS m_phone, MAX(fm.status) AS m_status,
                MAX(m_occ.job_name_kh) AS m_job_kh, MAX(m_occ.job_name_en) AS m_job_en,
                
                MAX(fs.last_name_en) AS s_last_en, MAX(fs.first_name_en) AS s_first_en, 
                MAX(fs.dob) AS s_dob, MAX(fs.phone_number) AS s_phone,
                MAX(s_occ.job_name_kh) AS s_job_kh, MAX(s_occ.job_name_en) AS s_job_en,
                
                MAX(fg.last_name_en) AS g_last_en, MAX(fg.first_name_en) AS g_first_en, MAX(fg.phone_number) AS g_phone,
                MAX(gr.relation_name_en) AS g_relation_en, 
                MAX(gp.name_en) AS g_prov_name, 
                MAX(q.created_at) as created_at
            FROM candidates c
            INNER JOIN application_details a ON c.application_no = a.application_no
            LEFT JOIN queue_tickets q ON c.application_no = q.application_no
            LEFT JOIN ref_banks rb ON a.bank_id = rb.id
            LEFT JOIN ref_provinces rp ON a.province_id = rp.id
            LEFT JOIN ref_districts rd ON a.district_id = rd.id
            LEFT JOIN ref_communes rc ON a.commune_id = rc.id
            LEFT JOIN ref_villages rv ON a.village_id = rv.id
            LEFT JOIN ref_education_levels rel ON a.education_level_id = rel.id 
            LEFT JOIN ref_provinces ksp ON a.khmer_school_province_id = ksp.id 
            LEFT JOIN ref_provinces kosp ON a.korean_school_province_id = kosp.id 
            
            LEFT JOIN family_members fd ON c.application_no = fd.application_no 
                 AND fd.relationship_id = (SELECT id FROM ref_relationships WHERE relation_name_en = 'Father' LIMIT 1)
                 AND fd.guarantor_role IS NULL
            LEFT JOIN ref_occupations f_occ ON fd.occupation_id = f_occ.id
            LEFT JOIN ref_provinces f_rp ON fd.province_id = f_rp.id
            LEFT JOIN ref_districts f_rd ON fd.district_id = f_rd.id
            LEFT JOIN ref_communes f_rc ON fd.commune_id = f_rc.id
            LEFT JOIN ref_villages f_rv ON fd.village_id = f_rv.id
            
            LEFT JOIN family_members fm ON c.application_no = fm.application_no 
                 AND fm.relationship_id = (SELECT id FROM ref_relationships WHERE relation_name_en = 'Mother' LIMIT 1)
                 AND fm.guarantor_role IS NULL
            LEFT JOIN ref_occupations m_occ ON fm.occupation_id = m_occ.id
            
            LEFT JOIN family_members fs ON c.application_no = fs.application_no 
                 AND fs.relationship_id IN (SELECT id FROM ref_relationships WHERE relation_name_en IN ('Husband', 'Wife'))
                 AND fs.guarantor_role IS NULL
            LEFT JOIN ref_occupations s_occ ON fs.occupation_id = s_occ.id
            
            LEFT JOIN family_members fg ON c.application_no = fg.application_no AND fg.guarantor_role = 'Guarantor'
            LEFT JOIN ref_relationships gr ON fg.relationship_id = gr.id 
            LEFT JOIN ref_provinces gp ON fg.province_id = gp.id 
            
            {where_clause}
            GROUP BY c.application_no, c.name_en, c.gender, c.dob, c.job_app_status
            ORDER BY MAX(q.created_at) ASC
        """
        cursor.execute(sql, params)
        data = cursor.fetchall()

        total_candidates = len(data)
        total_female = sum(1 for row in data if str(row.get('gender') or '').strip().upper() in ['F', 'FEMALE', 'ស្រី'])

        wb = openpyxl.Workbook()
        ws = wb.active

        def format_date(d):
            if not d or str(d).strip() in ['None', '', 'NULL']: return ""
            if isinstance(d, datetime) or hasattr(d, 'strftime'): 
                return d.strftime('%Y/%m/%d')
            return str(d).split(' ')[0].replace('-', '/')

        if report_format == 'report1':
            ws.title = "Report 1"
            ws.append([custom_title]) 
            ws.append([f"📅 កាលបរិច្ឆេទ និងម៉ោង៖ {current_datetime}   |   👤 ទាញយកដោយ៖ {exporter_name}"])
            ws.append([f"📊 ចំនួនបេក្ខជនសរុប៖ {total_candidates} នាក់ (ស្រី៖ {total_female} នាក់)"])
            
            headers = [
                "ល.រ", "លេខកូដប្រឡង", "ឈ្មោះភាសាខ្មែរ", "ឈ្មោះជាអក្សរឡាតាំង", 
                "ថ្ងែខែឆ្នាំកំណើត", "លេខទូរសព្ទបេក្ខជន", "អាសយដ្ឋានលម្អិត", "ខេត្ត/ក្រុង(បេក្ខជន)", "លេខអត្តសញ្ញាណប័ណ្ណ", "ភេទ",
                "ឪពុកឈ្មោះ", "លេខទូរសព្ទ(ឪពុក)", "មុខរបរ", "ស្ថានភាព(ឳពុក)",
                "ម្តាយឈ្មោះ", "លេខទូរសព្ទ(ម្តាយ)", "មុខរបរ", "ស្ថានភាព(ម្តាយ)", "អាសយដ្ឋានឪពុកម្តាយ",
                "Link Facebook", "Link Tiktok", "លេខលិខិតឆ្លងដែន",
                "កម្ពស់", "ទម្ងន់", "ឈ្មោះប្រពន្ធ ឬប្តី(ឡាតាំង)", "ថ្ងៃខែឆ្នាំកំណើតប្រពន្ធ/ប្តី",
                "មុខរបរ(ប្រពន្ធ/ប្តី)", "លេខទូរសព្ទ(ប្រពន្ធ/ប្តី)", "ចំនួនកូន" 
            ]
            ws.append(headers)

            for index, row in enumerate(data, start=1):
                full_kh_name = f"{row['last_name_kh'] or ''} {row['first_name_kh'] or ''}".strip()
                father_name = f"{row['f_last_kh'] or ''} {row['f_first_kh'] or ''}".strip()
                mother_name = f"{row['m_last_kh'] or ''} {row['m_first_kh'] or ''}".strip()
                spouse_name = f"{row['s_last_en'] or ''} {row['s_first_en'] or ''}".strip()
                
                f_status_raw = str(row['f_status'] or '')
                f_status_kh = "រស់" if f_status_raw.lower() == 'alive' else "ស្លាប់" if f_status_raw.lower() == 'deceased' else f_status_raw
                
                m_status_raw = str(row['m_status'] or '')
                m_status_kh = "រស់" if m_status_raw.lower() == 'alive' else "ស្លាប់" if m_status_raw.lower() == 'deceased' else m_status_raw

                gender_raw = str(row['gender'] or '').strip().upper()
                gender_kh = "ប្រុស" if gender_raw in ['M', 'MALE'] else "ស្រី" if gender_raw in ['F', 'FEMALE'] else (row['gender'] or '')

                cand_province_kh = f"{row['prov_name_kh']}" if row.get('prov_name_kh') else ""

                # 🌟 វះកាត់ជួសជុល៖ បូកបញ្ចូលលេខផ្ទះ/ផ្លូវ (address_detail) មុនឈ្មោះភូមិ ឃុំ ស្រុក
                cand_addr_kh_parts = []
                #if row.get('address_detail'): cand_addr_kh_parts.append(f"{row['address_detail']},")
                if row.get('vill_name_kh'): cand_addr_kh_parts.append(f"ភូមិ{row['vill_name_kh']}")
                if row.get('comm_name_kh'): cand_addr_kh_parts.append(f"ឃុំ/សង្កាត់{row['comm_name_kh']}")
                if row.get('dist_name_kh'): cand_addr_kh_parts.append(f"ស្រុក/ខណ្ឌ{row['dist_name_kh']}")
                
                cand_detailed_address_kh = " ".join(cand_addr_kh_parts) if cand_addr_kh_parts else ""

                parent_addr_parts = []
                if row.get('p_vill_kh'): parent_addr_parts.append(f"ភូមិ{row['p_vill_kh']}")
                if row.get('p_comm_kh'): parent_addr_parts.append(f"ឃុំ/សង្កាត់{row['p_comm_kh']}")
                if row.get('p_dist_kh'): parent_addr_parts.append(f"ស្រុក/ខណ្ឌ{row['p_dist_kh']}")
                if row.get('p_prov_kh'): parent_addr_parts.append(f"ខេត្ត/ក្រុង{row['p_prov_kh']}")
                parent_address_kh = " ".join(parent_addr_parts) if parent_addr_parts else ""

                ws.append([
                    index, row['application_no'] or "", 
                    full_kh_name, row['name_en'] or '', format_date(row['dob']), 
                    row['phone_number'] or '', cand_detailed_address_kh, cand_province_kh, row['id_card_no'] or '', gender_kh, 
                    father_name, row['f_phone'] or '', row['f_job_kh'] or '', f_status_kh, 
                    mother_name, row['m_phone'] or '', row['m_job_kh'] or '', m_status_kh, parent_address_kh, 
                    row['facebook_link'] or '', row['tiktok_link'] or '', row['passport_no'] or '',
                    row['height'] or '', row['weight'] or '', 
                    spouse_name, format_date(row['s_dob']),
                    row['s_job_kh'] or '',  
                    row['s_phone'] or '',
                    row['children_count'] or 0 
                ])

        else:
            ws.title = "Report 2"
            ws.append([custom_title])
            ws.append([f"📅 Exported Date & Time: {current_datetime}   |   👤 Exported By: {exporter_name}"])
            ws.append([f"📊 Total Candidates: {total_candidates} Person(s) (Female: {total_female})"])
            
            headers = [
                "No", "EPS-TOPIK ID", "Code_PP", "Code_BA",
                "Name in English", "Name in Khmer", "Gender", "Date of Birth",
                "ID Card Number", "Phone Number", "Email", "Facebook Link", "TikTok Link", 
                "Height (cm)", "Weight (kg)", "Marital Status", "Number of Children", 
                "Address Detail", "Candidate Province", 
                "Passport Number", "Passport Issue Date", "Date of Expiry", 
                "Bank Name", "Account Number", "Swift Code", 
                "Worked in Korea (5 Yrs)", "Alien Registration No", 
                "Education Level", "Khmer School Name", "Khmer School Province", "Korean School Name", "Korean School Province", 
                "Father Last Name", "Father First Name", "Father Phone", "Father Job", "Father Status", 
                "Mother Last Name", "Mother First Name", "Mother Phone", "Mother Job", "Mother Status", 
                "Parents Address", 
                "Spouse Last Name", "Spouse First Name", "Spouse DOB", "Spouse Job", "Spouse Phone",
                "Guarantor Name", "Guarantor Relationship", "Guarantor Phone", "Guarantor Province"
            ]
            ws.append(headers)

            for index, row in enumerate(data, start=1):
                full_kh_name = f"{row['last_name_kh'] or ''} {row['first_name_kh'] or ''}".strip()

                eps_id = (row['application_no'] or '').upper()
                code_pp = f"{eps_id}_PP" if eps_id else ""
                code_ba = f"{eps_id}_BA" if eps_id else ""

                passport_issue = format_date(row['passport_issue_date'])
                expiry_date = ""
                if passport_issue:
                    try:
                        p_date = datetime.strptime(passport_issue, '%Y/%m/%d')
                        # 🌟 វះកាត់ជួសជុល៖ ការពារកំហុសថ្ងៃទី ២៩ កុម្ភៈ (Leap Year Crash Fix)
                        try:
                            exp_date_obj = p_date.replace(year=p_date.year + 10)
                        except ValueError:
                            # បើថ្ងៃ ២៩ កុម្ភៈ ហើយ ១០ ឆ្នាំក្រោយមិនមែនឆ្នាំបន្តុប វារុញមកថ្ងៃ ២៨ កុម្ភៈ វិញ
                            exp_date_obj = p_date + timedelta(days=365 * 10 + 2)
                            
                        expiry_date = exp_date_obj.strftime('%Y/%m/%d')
                    except: pass

                f_status_en = str(row['f_status'] or '')
                if f_status_en == 'នៅរស់' or f_status_en.lower() == 'alive': f_status_en = 'ALIVE'
                elif f_status_en == 'ស្លាប់' or f_status_en.lower() == 'deceased': f_status_en = 'DECEASED'
                else: f_status_en = f_status_en.upper()

                m_status_en = str(row['m_status'] or '')
                if m_status_en == 'នៅរស់' or m_status_en.lower() == 'alive': m_status_en = 'ALIVE'
                elif m_status_en == 'ស្លាប់' or m_status_en.lower() == 'deceased': m_status_en = 'DECEASED'
                else: m_status_en = m_status_en.upper()

                worked_kr = row.get('worked_in_korea_last_5yrs')
                korea_exp_text = "YES" if worked_kr == 1 else "NO" if worked_kr == 0 else ""

                gender_raw = str(row['gender'] or '').strip().upper()
                gender_en = "MALE" if gender_raw in ['M', 'MALE', 'ប្រុស'] else "FEMALE" if gender_raw in ['F', 'FEMALE', 'ស្រី'] else gender_raw

                edu_level = str(row.get('level_name_en') or row.get('education_level_en') or '').strip().upper()
                kh_school = str(row.get('khmer_school_name') or '').strip().upper()

                g_full_name = f"{row['g_last_en'] or ''} {row['g_first_en'] or ''}".strip().upper()

                cand_address_en = f"{row['prov_name_en']}".upper() if row.get('prov_name_en') else ""

                p_addr_en_parts = []
                if row.get('p_vill_en'): p_addr_en_parts.append(f"{row['p_vill_en']} VILLAGE")
                if row.get('p_comm_en'): p_addr_en_parts.append(f"{row['p_comm_en']} COMMUNE")
                if row.get('p_dist_en'): p_addr_en_parts.append(f"{row['p_dist_en']} DISTRICT")
                if row.get('p_prov_en'): p_addr_en_parts.append(f"{row['p_prov_en']} PROVINCE")
                parent_address_en = ", ".join(p_addr_en_parts).upper() if p_addr_en_parts else ""

                ws.append([
                    index, eps_id, code_pp, code_ba,
                    (row['name_en'] or '').upper(), full_kh_name, gender_en, format_date(row['dob']),
                    row['id_card_no'] or '', row['phone_number'] or '', (row['email'] or '').lower(), row['facebook_link'] or '', row['tiktok_link'] or '', 
                    row['height'] or '', row['weight'] or '', (row['marital_status'] or '').upper(), 
                    row['children_count'] or 0, 
                    (row['address_detail'] or '').upper(), cand_address_en, 
                    (row['passport_no'] or '').upper(), passport_issue, expiry_date, 
                    (row['bank_full_name'] or '').upper(), row['bank_account_no'] or '', (row['swift_code'] or '').upper(), 
                    korea_exp_text, (row['alien_registration_no'] or '').upper(), 
                    edu_level, kh_school, (row['khmer_school_prov'] or '').upper(), (row['korean_school_name'] or '').upper(), (row['korean_school_prov'] or '').upper(),  
                    row['f_last_kh'] or '', row['f_first_kh'] or '', row['f_phone'] or '', (row['f_job_en'] or '').upper(), f_status_en, 
                    row['m_last_kh'] or '', row['m_first_kh'] or '', row['m_phone'] or '', (row['m_job_en'] or '').upper(), m_status_en, 
                    parent_address_en, 
                    (row['s_last_en'] or '').upper(), (row['s_first_en'] or '').upper(), format_date(row['s_dob']), (row['s_job_en'] or '').upper(), row['s_phone'] or '', 
                    g_full_name, (row['g_relation_en'] or '').upper(), row['g_phone'] or '', (row['g_prov_name'] or '').upper() 
                ])

        # =====================================================================
        # 🎨 ការកំណត់ Styles និង Layout
        # =====================================================================
        font_title = Font(name='Khmer OS Siemreap', size=15, bold=True, color="0f172a")
        font_subtitle = Font(name='Khmer OS Siemreap', size=12, color="475569")
        font_header = Font(name='Khmer OS Siemreap', size=13, bold=True, color="ffffff")
        font_data = Font(name='Khmer OS Siemreap', size=11)
        
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        align_center = Alignment(horizontal='center', vertical='center', wrap_text=False)
        align_left = Alignment(horizontal='left', vertical='center', wrap_text=False)
        header_fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")

        ws.row_dimensions[1].height = 35 
        ws.row_dimensions[2].height = 25 
        ws.row_dimensions[3].height = 25
        ws.row_dimensions[4].height = 35 

        for row_idx, row in enumerate(ws.iter_rows(), start=1):
            if row_idx > 4:
                ws.row_dimensions[row_idx].height = 28
                
            for cell in row:
                if row_idx == 1: 
                    cell.font = font_title
                    cell.alignment = align_center
                elif row_idx in [2, 3]: 
                    cell.font = font_subtitle
                    cell.alignment = align_center
                elif row_idx == 4: 
                    cell.font = font_header
                    cell.alignment = align_center
                    cell.border = thin_border
                    cell.fill = header_fill
                else: 
                    cell.font = font_data
                    cell.border = thin_border
                    if cell.column == 1 or cell.column == 2 or cell.column == 8: 
                        cell.alignment = align_center
                    else:
                        cell.alignment = align_left

        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            
            for cell in col:
                if cell.row < 4: continue
                try:
                    if cell.value:
                        cell_length = len(str(cell.value))
                        if cell_length > max_length: max_length = cell_length
                except: pass
            
            if column == 'A' and report_format == 'report1':
                ws.column_dimensions[column].width = 6 
            else:
                adjusted_width = (max_length * 1.3) + 5
                ws.column_dimensions[column].width = min(max(adjusted_width, 15), 60)

        max_col_letter = get_column_letter(ws.max_column)
        ws.merge_cells(f'A1:{max_col_letter}1')
        ws.merge_cells(f'A2:{max_col_letter}2')
        ws.merge_cells(f'A3:{max_col_letter}3')

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        filename = f"{'របាយការណ៍បេក្ខជនបានដាក់ពាក្យស្វែងរកការងារ_Kh' if report_format == 'report1' else 'របាយការណ៍បេក្ខជនបានដាក់ពាក្យស្វែងរកការងារ_En'}_{date.today().strftime('%Y%m%d')}.xlsx"
        return send_file(out, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        import traceback
        print("Excel Export Error:", str(e))
        traceback.print_exc()
        return f"មានបញ្ហាក្នុងការទាញយក Excel៖ {str(e)}"
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

# ==============================================================================
# Admin API: សម្រាប់ Update ការកំណត់ប្រព័ន្ធ (AJAX Modal)
# ==============================================================================
@app.route('/admin/update_settings_ajax', methods=['POST'])
def update_settings_ajax():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'សូមចូលគណនី (Login) ជាមុនសិន!'})
        
    data = request.get_json()
    
    # បញ្ជី Columns ទាំងអស់ដែលត្រូវអាប់ដេត
    columns = [
        'is_system_open', 'app_start_date', 'app_end_date',
        'am_start_time', 'am_end_time', 'pm_start_time', 'pm_end_time',
        'show_personal_info', 'show_parents_info', 'show_spouse_info', 'show_bank_info',
        'show_khmer_school', 'show_korean_school', 'show_korea_experience', 'show_guarantor', 'show_social_media',
        'show_passport_info', 'show_pass_no', 'show_pass_issue_year', 'show_pass_issue_month', 'show_pass_issue_day', 'show_pass_doc',
        'show_f_lname', 'show_f_fname', 'show_f_job', 'show_f_status', 'show_f_phone',
        'show_m_lname', 'show_m_fname', 'show_m_job', 'show_m_status', 'show_m_phone',
        'show_p_province', 'show_p_district', 'show_p_commune', 'show_p_village',
        'show_s_lname', 'show_s_fname', 'show_s_job', 'show_s_phone',
        'show_k_school_name', 'show_k_school_prov', 'show_ko_school_name', 'show_ko_school_prov',
        'show_bank_name', 'show_bank_account', 'show_bank_book',
        'show_exp_korea', 'show_exp_alien_card',
        'show_g_lname', 'show_g_fname', 'show_g_relation', 'show_g_phone', 'show_g_prov',
        'show_fb_link', 'show_tk_link'
    ]

    values = []
    set_clauses = []
    
    for col in columns:
        val = data.get(col)
        
        # 💡 កែពី val == '' មកជា if not val វិញ ដើម្បីចាប់បានទាំង None ទាំង String ទទេ
        if not val and col in ['app_start_date', 'app_end_date']:
            val = None
        if not val and col in ['am_start_time', 'am_end_time', 'pm_start_time', 'pm_end_time']:
            val = None # ដាក់ None ល្អជាង '00:00' ដើម្បីឱ្យ DB ដឹងថាអត់មានកំណត់ម៉ោង
            
        values.append(val)
        set_clauses.append(f"{col} = %s")
            
        
        
    set_clause_str = ", ".join(set_clauses)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = f"UPDATE system_settings SET {set_clause_str} WHERE id = 1"
        cursor.execute(sql, tuple(values))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'បានរក្សាទុកការកំណត់ដោយជោគជ័យ!'})
    except Exception as e:
        conn.rollback()
        print("Settings Save Error:", str(e))
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close() 


@app.route('/station')
def station():
    # ពិនិត្យមើលថាអ្នកប្រើប្រាស់បាន Login ហើយឬនៅ
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    # ពិនិត្យមើលថាបានជ្រើសរើសវគ្គប្រឡងហើយឬនៅ
    if not session.get('active_session'):
        flash('សូមជ្រើសរើសវគ្គប្រឡងជាមុនសិន!', 'warning')
        return redirect(url_for('dashboard'))
        
    # បើកទំព័របញ្ជរស្កែនរួម
    return render_template('station.html')  

import pandas as pd
from werkzeug.utils import secure_filename
import os

# ==========================================
# គ្រប់គ្រងទិន្នន័យធនាគារ (Bank Management)
# ==========================================

@app.route('/admin/banks', methods=['GET'])
def manage_banks():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM ref_banks ORDER BY id DESC")
        banks = cursor.fetchall()
        return render_template('banks.html', banks=banks)
    except Exception as e:
        flash(f'មានបញ្ហាទាញយកទិន្នន័យ៖ {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/banks/add', methods=['POST'])
def add_bank():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    full_name = request.form.get('bank_full_name').strip()
    short_name = request.form.get('bank_short_name').strip()
    swift_code = request.form.get('swift_code').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ref_banks (bank_full_name, bank_short_name, swift_code) 
            VALUES (%s, %s, %s)
        """, (full_name, short_name, swift_code))
        conn.commit()
        flash('បន្ថែមធនាគារថ្មីបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'បរាជ័យក្នុងការបន្ថែម៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('manage_banks'))

@app.route('/admin/banks/delete/<int:id>', methods=['POST'])
def delete_bank(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ref_banks WHERE id = %s", (id,))
        conn.commit()
        flash('លុបទិន្នន័យធនាគារបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'មិនអាចលុបបានទេ (អាចមានទិន្នន័យកំពុងប្រើប្រាស់ធនាគារនេះ)៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_banks'))

@app.route('/admin/banks/import', methods=['POST'])
def import_banks():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('សូមជ្រើសរើសឯកសារ Excel ឬ CSV!', 'warning')
        return redirect(url_for('manage_banks'))
        
    try:
        # អានឯកសារ CSV ឬ Excel
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        else:
            flash('អនុញ្ញាតតែឯកសារ .csv, .xls, .xlsx ប៉ុណ្ណោះ!', 'danger')
            return redirect(url_for('manage_banks'))
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        success_count = 0
        for index, row in df.iterrows():
            # ចាប់យក Column ពី Excel (ផ្អែកលើឈ្មោះ Column "Name" និង "SWIFT Code")
            full_name = str(row.get('Name', '')).strip()
            swift_code = str(row.get('SWIFT Code', '')).strip()
            
            # ប្រសិនបើគ្មាន bank_short_name នៅក្នុង Excel ទេ យើងកាត់យកឈ្មោះពេញ ៥០តួអក្សរដំបូង
            short_name = str(row.get('Short Name', full_name[:50])).strip()
            
            if full_name and full_name.lower() != 'nan':
                cursor.execute("""
                    INSERT INTO ref_banks (bank_full_name, bank_short_name, swift_code) 
                    VALUES (%s, %s, %s)
                """, (full_name, short_name, swift_code if swift_code.lower() != 'nan' else None))
                success_count += 1
                
        conn.commit()
        flash(f'នាំចូលទិន្នន័យបានជោគជ័យចំនួន {success_count} ធនាគារ!', 'success')
        
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback()
        flash(f'បរាជ័យក្នុងការនាំចូលឯកសារ៖ {str(e)}', 'danger')
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()
        
    return redirect(url_for('manage_banks'))

@app.route('/admin/banks/edit/<int:id>', methods=['POST'])
def edit_bank(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    full_name = request.form.get('bank_full_name').strip()
    short_name = request.form.get('bank_short_name').strip()
    swift_code = request.form.get('swift_code').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE ref_banks 
            SET bank_full_name = %s, bank_short_name = %s, swift_code = %s 
            WHERE id = %s
        """, (full_name, short_name, swift_code, id))
        conn.commit()
        flash('កែប្រែព័ត៌មានធនាគារបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'បរាជ័យក្នុងការកែប្រែ៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_banks'))

# ==========================================
# គ្រប់គ្រងកម្រិតសិក្សា (Education Levels)
# ==========================================

@app.route('/admin/education_levels', methods=['GET'])
def manage_education_levels():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM ref_education_levels ORDER BY id DESC")
        edu_levels = cursor.fetchall()
        return render_template('education_levels.html', edu_levels=edu_levels)
    except Exception as e:
        flash(f'មានបញ្ហាទាញយកទិន្នន័យ៖ {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/education_levels/add', methods=['POST'])
def add_education_level():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    level_name_kh = request.form.get('level_name_kh').strip()
    level_name_en = request.form.get('level_name_en').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ref_education_levels (level_name_kh, level_name_en) 
            VALUES (%s, %s)
        """, (level_name_kh, level_name_en))
        conn.commit()
        flash('បន្ថែមតម្រិតសិក្សាថ្មីបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'បរាជ័យក្នុងការបន្ថែម៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('manage_education_levels'))

@app.route('/admin/education_levels/edit/<int:id>', methods=['POST'])
def edit_education_level(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    level_name_kh = request.form.get('level_name_kh').strip()
    level_name_en = request.form.get('level_name_en').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE ref_education_levels 
            SET level_name_kh = %s, level_name_en = %s 
            WHERE id = %s
        """, (level_name_kh, level_name_en, id))
        conn.commit()
        flash('កែប្រែកម្រិតសិក្សាបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'បរាជ័យក្នុងការកែប្រែ៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_education_levels'))

@app.route('/admin/education_levels/delete/<int:id>', methods=['POST'])
def delete_education_level(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ref_education_levels WHERE id = %s", (id,))
        conn.commit()
        flash('លុបទិន្នន័យកម្រិតសិក្សាបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'មិនអាចលុបបានទេ (ទិន្នន័យនេះកំពុងត្រូវបានប្រើប្រាស់ដោយបេក្ខជន)៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_education_levels'))

# ==========================================
# គ្រប់គ្រងទំនាក់ទំនង (Relationships)
# ==========================================

@app.route('/admin/relationships', methods=['GET'])
def manage_relationships():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM ref_relationships ORDER BY id DESC")
        relationships = cursor.fetchall()
        return render_template('relationships.html', relationships=relationships)
    except Exception as e:
        flash(f'មានបញ្ហាទាញយកទិន្នន័យ៖ {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/relationships/add', methods=['POST'])
def add_relationship():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    relation_name_kh = request.form.get('relation_name_kh').strip()
    relation_name_en = request.form.get('relation_name_en').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ref_relationships (relation_name_kh, relation_name_en) 
            VALUES (%s, %s)
        """, (relation_name_kh, relation_name_en))
        conn.commit()
        flash('បន្ថែមទំនាក់ទំនងថ្មីបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'បរាជ័យក្នុងការបន្ថែម៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('manage_relationships'))

@app.route('/admin/relationships/edit/<int:id>', methods=['POST'])
def edit_relationship(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    relation_name_kh = request.form.get('relation_name_kh').strip()
    relation_name_en = request.form.get('relation_name_en').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE ref_relationships 
            SET relation_name_kh = %s, relation_name_en = %s 
            WHERE id = %s
        """, (relation_name_kh, relation_name_en, id))
        conn.commit()
        flash('កែប្រែទំនាក់ទំនងបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'បរាជ័យក្នុងការកែប្រែ៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_relationships'))

@app.route('/admin/relationships/delete/<int:id>', methods=['POST'])
def delete_relationship(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ref_relationships WHERE id = %s", (id,))
        conn.commit()
        flash('លុបទិន្នន័យទំនាក់ទំនងបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'មិនអាចលុបបានទេ (ទិន្នន័យនេះកំពុងត្រូវបានប្រើប្រាស់)៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_relationships'))

# ==========================================
# គ្រប់គ្រងមុខរបរ (Occupations)
# ==========================================

@app.route('/admin/occupations', methods=['GET'])
def manage_occupations():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM ref_occupations ORDER BY id DESC")
        occupations = cursor.fetchall()
        return render_template('occupations.html', occupations=occupations)
    except Exception as e:
        flash(f'មានបញ្ហាទាញយកទិន្នន័យ៖ {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/occupations/add', methods=['POST'])
def add_occupation():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    job_name_kh = request.form.get('job_name_kh').strip()
    job_name_en = request.form.get('job_name_en').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ref_occupations (job_name_kh, job_name_en) 
            VALUES (%s, %s)
        """, (job_name_kh, job_name_en))
        conn.commit()
        flash('បន្ថែមមុខរបរថ្មីបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'បរាជ័យក្នុងការបន្ថែម៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('manage_occupations'))

@app.route('/admin/occupations/edit/<int:id>', methods=['POST'])
def edit_occupation(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    job_name_kh = request.form.get('job_name_kh').strip()
    job_name_en = request.form.get('job_name_en').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE ref_occupations 
            SET job_name_kh = %s, job_name_en = %s 
            WHERE id = %s
        """, (job_name_kh, job_name_en, id))
        conn.commit()
        flash('កែប្រែមុខរបរបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'បរាជ័យក្នុងការកែប្រែ៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_occupations'))

@app.route('/admin/occupations/delete/<int:id>', methods=['POST'])
def delete_occupation(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ref_occupations WHERE id = %s", (id,))
        conn.commit()
        flash('លុបទិន្នន័យមុខរបរបានជោគជ័យ!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'មិនអាចលុបបានទេ ព្រោះមានបេក្ខជនកំពុងប្រើប្រាស់មុខរបរនេះ៖ {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_occupations'))

from datetime import datetime
# កុំភ្លេច import jsonify, request, render_template បើមិនទាន់មាន

# ==========================================
# ១. ផ្ទាំងម៉ាស៊ីនបោះពុម្ពលេខ (Ticket Kiosk UI)
# ==========================================
@app.route('/kiosk') # ឬ @queue_bp.route('/kiosk') បើប្រើ Blueprint
def ticket_kiosk():
    return render_template('kiosk.html')

# ==========================================
# ២. API សម្រាប់បង្កើតលេខរង់ចាំថ្មី (Generate Ticket)
# ==========================================
from datetime import datetime
from flask import jsonify # កុំភ្លេច import បើមិនទាន់មាន

# ==========================================
# API សម្រាប់ Kiosk បង្កើតលេខរង់ចាំថ្មី (Generate Ticket)
# ==========================================
@app.route('/api/generate_ticket', methods=['POST']) # បើបងប្រើ Blueprint សូមដូរទៅ @queue_bp.route
def generate_ticket():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # ១. ចាប់យកកាលបរិច្ឆេទថ្ងៃនេះ
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        # 💡 ការពារទិន្នន័យ (Transaction Start): បើមាន Error ត្រង់ណាមួយ វានឹងមិន Save ចូល DB ទេ
        conn.start_transaction()

        # ២. ឆែកមើលតើថ្ងៃនេះមានលេខហើយឬនៅ ក្នុង Table queue_sequence
        cursor.execute("SELECT last_number FROM queue_sequence WHERE queue_date = %s", (today_date,))
        seq_record = cursor.fetchone()

        if seq_record:
            # បើថ្ងៃនេះមានអ្នកធ្លាប់យកលេខហើយ -> បូកថែម ១
            new_number = seq_record['last_number'] + 1
            cursor.execute("UPDATE queue_sequence SET last_number = %s WHERE queue_date = %s", (new_number, today_date))
        else:
            # បើថ្ងៃនេះអត់ទាន់មានអ្នកយកលេខសោះ (ព្រឹកព្រលឹម) -> ចាប់ផ្តើមពីលេខ ១
            new_number = 1
            cursor.execute("INSERT INTO queue_sequence (queue_date, last_number) VALUES (%s, %s)", (today_date, new_number))

        # ៣. បង្កើតទម្រង់លេខសំបុត្រ (ឧទាហរណ៍៖ A-001, A-002...)
        # បើបងចង់ដូរអក្សរ A ទៅអក្សរផ្សេង អាចកែត្រង់នេះបាន
        queue_str = f"A-{new_number:03d}" 

        # ៤. បញ្ចូលលេខថ្មីនេះទៅក្នុង Table ធំ queue_tickets
        cursor.execute("""
            INSERT INTO queue_tickets (queue_number, status, created_at) 
            VALUES (%s, 'Waiting', NOW())
        """, (queue_str,))
        
        ticket_id = cursor.lastrowid # ចាប់យក ID ដែលទើបនឹងបញ្ចូលថ្មីៗ

        # ៥. បញ្ជាក់ការរក្សាទុកទិន្នន័យ (Commit)
        conn.commit()

        # ៦. ទាញយកម៉ោងពិតប្រាកដចេញពី Database ដើម្បីផ្ញើទៅបង្ហាញលើវិក្កយបត្រ (Kiosk)
        cursor.execute("""
            SELECT queue_number, DATE_FORMAT(created_at, '%d/%m/%Y %h:%i %p') as time_str 
            FROM queue_tickets 
            WHERE id = %s
        """, (ticket_id,))
        ticket_info = cursor.fetchone()

        # ៧. បញ្ជូនទិន្នន័យទៅឱ្យ HTML (Kiosk) វិញ
        return jsonify({'status': 'success', 'ticket': ticket_info})

    except Exception as e:
        conn.rollback() # បើមាន Error ទម្លាក់ចោលការ Save ទាំងអស់
        print(f"Generate Ticket Error: {e}")
        return jsonify({'status': 'error', 'message': 'មានបញ្ហាក្នុងការបង្កើតលេខ សូមព្យាយាមម្តងទៀត។'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

from datetime import datetime

# =======================================================
# ១. មុខងារឆែកមើលសិទ្ធិ (Dynamic ១០០% តាមរយៈ URL)
# =======================================================
def check_qr_access():
    # ចាប់យក Link បច្ចុប្បន្នដោយស្វ័យប្រវត្តិ (ឧទាហរណ៍: '/exam_schedule' ឫ '/candidate_login')
    current_url = request.path 
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # ស្វែងរកនៅក្នុង DB តាមរយៈ target_url តែម្តង
    cursor.execute("SELECT * FROM qr_settings WHERE target_url = %s", (current_url,))
    setting = cursor.fetchone()
    cursor.close()
    conn.close()

    # បើមិនមានកំណត់ក្នុងប្រព័ន្ធទេ អនុញ្ញាតឱ្យចូលមើលធម្មតា
    if not setting:
        return True, None

    # បើរកឃើញ តែត្រូវគេបិទ (is_active = 0)
    if not setting['is_active']:
        return False, setting

    # 🌟 កែសម្រួលកន្លែងនេះ 🌟
    # now = datetime.now() # <--- លុបកូដចាស់នេះចេញ
    cambodia_tz = pytz.timezone('Asia/Phnom_Penh') # កំណត់ម៉ោងកម្ពុជា
    now = datetime.now(cambodia_tz).replace(tzinfo=None) # ដក timezone info ចេញ ដើម្បីអោយត្រូវជាមួយ DB
    # បើមិនទាន់ដល់ម៉ោង ឬ ហួសម៉ោង
    if (setting['start_datetime'] and now < setting['start_datetime']) or \
       (setting['end_datetime'] and now > setting['end_datetime']):
        return False, setting

    return True, setting
# =======================================================
# ២. មុខងារ បង្កើត QR Code ថ្មី (លាក់ qr_type ចោល)
# =======================================================
@app.route('/add_qr_setting', methods=['POST'])
def add_qr_setting():
    qr_name = request.form.get('qr_name')
    target_url = request.form.get('target_url')
    
    # យើងលាក់មិនបាច់ប្រើ Type ទេ តែដើម្បីកុំឱ្យ Error Database ចាស់ យើងយក URL ទៅធ្វើជា Type តែម្តង
    qr_type = target_url 
    
    start_dt = request.form.get('start_datetime')
    end_dt = request.form.get('end_datetime')
    is_active = 1 if request.form.get('is_active') else 0

    if start_dt: start_dt = start_dt.replace('T', ' ') + ':00'
    else: start_dt = None
    if end_dt: end_dt = end_dt.replace('T', ' ') + ':00'
    else: end_dt = None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "INSERT INTO qr_settings (qr_type, qr_name, target_url, start_datetime, end_datetime, is_active) VALUES (%s, %s, %s, %s, %s, %s)"
        cursor.execute(query, (qr_type, qr_name, target_url, start_dt, end_dt, is_active))
        conn.commit()
        flash('បង្កើតការកំណត់ QR Code ថ្មីបានជោគជ័យ!', 'success')
    except Exception as e:
        flash('មានបញ្ហា! តំណភ្ជាប់នេះអាចមានរួចហើយ។', 'danger')
        print(e)
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('qr_settings'))

# =======================================================
# ៣. មុខងារ Update 
# =======================================================
@app.route('/update_qr_setting/<int:setting_id>', methods=['POST'])
def update_qr_setting(setting_id):
    qr_name = request.form.get('qr_name')
    target_url = request.form.get('target_url')
    qr_type = target_url # លាក់ដូចគ្នា
    
    start_dt = request.form.get('start_datetime')
    end_dt = request.form.get('end_datetime')
    is_active = 1 if request.form.get('is_active') else 0

    if start_dt: start_dt = start_dt.replace('T', ' ') + ':00'
    else: start_dt = None
    if end_dt: end_dt = end_dt.replace('T', ' ') + ':00'
    else: end_dt = None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "UPDATE qr_settings SET qr_name = %s, qr_type = %s, target_url = %s, start_datetime = %s, end_datetime = %s, is_active = %s WHERE id = %s"
        cursor.execute(query, (qr_name, qr_type, target_url, start_dt, end_dt, is_active, setting_id))
        conn.commit()
        flash('ការកែប្រែត្រូវបានរក្សាទុកដោយជោគជ័យ!', 'success')
    except Exception as e:
        flash('មានបញ្ហាពេលរក្សាទុក!', 'danger')
        print(e)
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('qr_settings'))
from flask import render_template, request, redirect, url_for, flash
# កុំភ្លេច import datetime បើមិនទាន់មាន

# =======================================================
# ទំព័រគ្រប់គ្រងការកំណត់ QR Code ទាំងអស់ (Admin Panel)
# =======================================================
@app.route('/qr_settings', methods=['GET'])
def qr_settings():
    # សន្មតថាអ្នកមានមុខងារឆែក Session Admin រួចហើយ
    # if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM qr_settings ORDER BY id ASC")
    settings = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('qr_settings.html', settings=settings)

# =======================================================
# មុខងារសម្រាប់ លុប QR Code
# =======================================================
@app.route('/delete_qr_setting/<int:setting_id>', methods=['POST'])
def delete_qr_setting(setting_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM qr_settings WHERE id = %s", (setting_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('លុបការកំណត់ QR Code បានជោគជ័យ!', 'success')
    return redirect(url_for('qr_settings'))
# ==============================================================
# 💡 មុខងារបង្កើតម៉ឺនុយ Dynamic និងឆែកសិទ្ធិ (Global Context)
# ==============================================================
@app.context_processor
def inject_dynamic_menu():
    dynamic_menu = []
    user_perms_dict = {}
    
    if 'id' in session:
        user_id = session['id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # ១. ទាញយកសិទ្ធិជាក់ស្តែងរបស់ User
            cursor.execute("""
                SELECT p.name, up.can_view, up.can_create, up.can_edit, up.can_delete 
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = %s
            """, (user_id,))
            for row in cursor.fetchall():
                user_perms_dict[row['name']] = row

            # ២. ទាញយកម៉ឺនុយទាំងអស់ពីប្រព័ន្ធ (យកមកទាំងមេទាំងកូន)
            cursor.execute("""
                SELECT m.id, m.parent_id, m.module_name_kh, m.module_code, m.route_url, m.icon_class, m.sort_order,
                       p.name as perm_name
                FROM sys_modules m
                LEFT JOIN permissions p ON m.id = p.module_id
                WHERE m.is_active = 1
                ORDER BY m.sort_order ASC, m.id ASC
            """)
            all_modules = cursor.fetchall()

            # ៣. បម្លែងទៅជាទម្រង់ដើមឈើ (Tree Structure)
            modules_by_id = {m['id']: dict(m, children=[]) for m in all_modules}
            
            for m in all_modules:
                if m['parent_id']:
                    parent = modules_by_id.get(m['parent_id'])
                    if parent:
                        parent['children'].append(modules_by_id[m['id']])

            # ៤. មុខងារច្រោះយកតែម៉ឺនុយដែលមានសិទ្ធិ (Recursive Filter)
            def filter_node(node):
                # ច្រោះកូនៗរបស់វាជាមុនសិន
                node['children'] = [filter_node(c) for c in node['children']]
                node['children'] = [c for c in node['children'] if c is not None]
                
                # បើជាម៉ឺនុយមេ (មានកូន ឬមាន Dropdown) -> បង្ហាញលុះត្រាតែមានកូនយ៉ាងហោច ១ ត្រូវបានបង្ហាញ
                if len(node['children']) > 0:
                    return node
                
                # បើជាម៉ឺនុយធម្មតាអត់មានកូន (Leaf node) -> ឆែកសិទ្ធិ can_view
                if node['route_url'] != '#':
                    perm_name = node['perm_name']
                    # បើវាជាម៉ឺនុយដែលត្រូវមានសិទ្ធិទើបមើលឃើញ
                    if perm_name:
                        if user_perms_dict.get(perm_name, {}).get('can_view') == 1:
                            return node
                    else:
                        # បើម៉ឺនុយនោះអត់មានចងសិទ្ធិទេ អនុញ្ញាតឱ្យឃើញទាំងអស់គ្នា
                        return node
                
                return None

            # ៥. អនុវត្តការច្រោះទៅលើម៉ឺនុយគោល (Headers)
            for m in all_modules:
                if m['parent_id'] is None:
                    filtered = filter_node(modules_by_id[m['id']])
                    if filtered:
                        dynamic_menu.append(filtered)

        except Exception as e:
            print("Dynamic Menu Error:", e)
        finally:
            cursor.close()
            conn.close()
            
    # Helper Function សម្រាប់ឆែកសិទ្ធិប៊ូតុងក្នុង HTML
    def has_perm(perm_name, action='can_view'):
        return user_perms_dict.get(perm_name, {}).get(action) == 1
        
    return dict(dynamic_menu=dynamic_menu, has_perm=has_perm)

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
# ... (ត្រូវប្រាកដថាអ្នកមាន get_db_connection និង module ផ្សេងៗទៀតរួចហើយ)

# ==============================================================================
# 🟢 ១. ទំព័របង្ហាញបញ្ជីមូលហេតុបដិសេធ (View Page)
# ==============================================================================
@app.route('/admin/settings/reject_reasons', methods=['GET'])
def manage_reject_reasons():
    # ឆែកមើលសិទ្ធិអនុញ្ញាត (មានតែ Super Admin ឬ Admin ទេទើបអាចចូល Setup បាន)
    if 'loggedin' not in session or session.get('role_name') not in ['Super Admin', 'Admin']:
        flash('អ្នកមិនមានសិទ្ធិចូលប្រើប្រាស់ទំព័រនេះទេ!', 'danger')
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # ទាញយកទិន្នន័យទាំងអស់ តម្រៀបអ្នកកំពុងបើក (is_active=1) ឱ្យនៅខាងលើគេ
        cursor.execute("SELECT * FROM ref_app_reject_reasons ORDER BY is_active DESC, id ASC")
        reasons = cursor.fetchall()
        
        # 🔴 គ្រាន់តែលុបពាក្យ settings/ ចេញ
        return render_template('admin/manage_reject_reasons.html', reasons=reasons)
    except Exception as e:
        print(f"Error loading reject reasons setup: {e}")
        return "មានបញ្ហាប្រព័ន្ធ សូមឆែកមើល Terminal។"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ==============================================================================
# 🟢 ២. មុខងារបន្ថែមថ្មី និងកែប្រែ (Add & Edit - API)
# ==============================================================================
@app.route('/admin/settings/reject_reasons/save', methods=['POST'])
def save_reject_reason():
    if 'loggedin' not in session or session.get('role_name') not in ['Super Admin', 'Admin']:
        return jsonify({'status': 'error', 'message': 'គ្មានសិទ្ធិអនុញ្ញាតទេ!'})

    data = request.get_json()
    reason_id = data.get('id') # បើមាន ID បានន័យថា Edit, បើគ្មានបានន័យថា Add ថ្មី
    reason_kh = data.get('reason_kh', '').strip()
    reason_en = data.get('reason_en', '').strip()

    if not reason_kh:
        return jsonify({'status': 'error', 'message': 'សូមបញ្ជាក់មូលហេតុជាភាសាខ្មែរ!'})

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if reason_id:
            # ករណីកែប្រែ (Update Existing)
            cursor.execute("""
                UPDATE ref_app_reject_reasons 
                SET reason_kh = %s, reason_en = %s 
                WHERE id = %s
            """, (reason_kh, reason_en, reason_id))
            msg = 'បានកែប្រែដោយជោគជ័យ!'
        else:
            # ករណីបញ្ចូលថ្មី (Insert New)
            cursor.execute("""
                INSERT INTO ref_app_reject_reasons (reason_kh, reason_en, is_active) 
                VALUES (%s, %s, 1)
            """, (reason_kh, reason_en))
            msg = 'បានបន្ថែមមូលហេតុថ្មីដោយជោគជ័យ!'
            
        conn.commit()
        return jsonify({'status': 'success', 'message': msg})
    except Exception as e:
        conn.rollback()
        print(f"Error saving reason: {e}")
        return jsonify({'status': 'error', 'message': 'មានបញ្ហាក្នុងការរក្សាទុកទិន្នន័យ!'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ==============================================================================
# 🟢 ៣. មុខងារ បើក/បិទ ស្ថានភាព (Toggle Active Status - API)
# ==============================================================================
@app.route('/admin/settings/reject_reasons/toggle', methods=['POST'])
def toggle_reject_reason():
    if 'loggedin' not in session or session.get('role_name') not in ['Super Admin', 'Admin']:
        return jsonify({'status': 'error', 'message': 'គ្មានសិទ្ធិអនុញ្ញាតទេ!'})

    data = request.get_json()
    reason_id = data.get('id')
    new_status = data.get('is_active') # ទទួលតម្លៃ 1 ឬ 0 ពី Frontend

    if not reason_id or new_status is None:
        return jsonify({'status': 'error', 'message': 'ទិន្នន័យមិនត្រឹមត្រូវ!'})

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Update ស្ថានភាព is_active ទៅតាមអ្វីដែលចុច
        cursor.execute("UPDATE ref_app_reject_reasons SET is_active = %s WHERE id = %s", (new_status, reason_id))
        conn.commit()
        
        status_text = "បើកឱ្យប្រើប្រាស់" if int(new_status) == 1 else "បិទផ្អាក"
        return jsonify({'status': 'success', 'message': f'បាន{status_text}ដោយជោគជ័យ!'})
    except Exception as e:
        conn.rollback()
        print(f"Error toggling reason status: {e}")
        return jsonify({'status': 'error', 'message': 'មានបញ្ហាក្នុងការផ្លាស់ប្តូរស្ថានភាព!'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
# ប្រាកដថាអ្នកមាន get_db_connection()

# ១. Route សម្រាប់បង្ហាញទំព័រ (មាន JOIN ជាមួយតារាង permissions ដើម្បីទាញឈ្មោះសិទ្ធិមកបង្ហាញពេលកែប្រែ)
@app.route('/admin/system_modules', methods=['GET'])
def manage_system_modules():
    if 'loggedin' not in session or session.get('role_name') != 'Super Admin':
        flash('សម្រាប់តែ Super Admin ប៉ុណ្ណោះ!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT m.*, p.name as permission_name 
            FROM sys_modules m 
            LEFT JOIN permissions p ON m.id = p.module_id 
            ORDER BY m.sort_order ASC, m.id ASC
        """)
        raw_modules = cursor.fetchall()

        # 🔴 Logic ថ្មី៖ រៀបចំជាមែកធាងគាំទ្រ ៣ កម្រិត ឬច្រើនជាងនេះ
        module_dict = {m['id']: m for m in raw_modules}
        module_tree = []
        
        # បង្កើតប្រអប់ children ឱ្យគ្រប់ម៉ឺនុយទាំងអស់
        for m in raw_modules:
            m['children'] = [] 

        # ញាត់កូនទៅក្នុងប្រអប់មេរបស់វា
        for m in raw_modules:
            parent_id = m['parent_id']
            if parent_id and parent_id in module_dict:
                module_dict[parent_id]['children'].append(m)
            elif not parent_id:
                module_tree.append(m)

        # បញ្ជូនទាំង module_tree (សម្រាប់តារាង) និង raw_modules (សម្រាប់ Dropdown)
        return render_template('admin/system_modules.html', module_tree=module_tree, all_modules=raw_modules)
    except Exception as e:
        print(f"Error loading system modules: {e}")
        return "មានបញ្ហាប្រព័ន្ធ។"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ២. Route សម្រាប់ Save (រួមបញ្ចូលទាំង Add ថ្មី និង Update)
@app.route('/admin/system_modules/save', methods=['POST'])
def save_system_module():
    if 'loggedin' not in session or session.get('role_name') != 'Super Admin':
        return jsonify({'status': 'error', 'message': 'គ្មានសិទ្ធិ!'})

    data = request.get_json()
    module_id = data.get('id') # បើមាន id បានន័យថាជាការ កែប្រែ (Edit)
    module_name_kh = data.get('module_name_kh')
    module_code = data.get('module_code')
    parent_id = data.get('parent_id') or None
    route_url = data.get('route_url', '#')
    icon_class = data.get('icon_class', 'fas fa-circle')
    sort_order = data.get('sort_order', 0)
    permission_name = data.get('permission_name')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if module_id:
            # 🔴 ករណីកែប្រែ (Update)
            cursor.execute("""
                UPDATE sys_modules 
                SET parent_id=%s, module_name_kh=%s, module_code=%s, route_url=%s, icon_class=%s, sort_order=%s
                WHERE id=%s
            """, (parent_id, module_name_kh, module_code, route_url, icon_class, sort_order, module_id))
            
            if permission_name:
                # ឆែកមើលក្រែងលោចង់អាប់ដេតឈ្មោះសិទ្ធិដែរ
                cursor.execute("UPDATE permissions SET name=%s WHERE module_id=%s", (permission_name, module_id))
            msg = 'បានកែប្រែទិន្នន័យជោគជ័យ!'
        else:
            # 🟢 ករណីបន្ថែមថ្មី (Insert)
            cursor.execute("""
                INSERT INTO sys_modules (parent_id, module_name_kh, module_code, route_url, icon_class, sort_order, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
            """, (parent_id, module_name_kh, module_code, route_url, icon_class, sort_order))
            new_module_id = cursor.lastrowid

            if permission_name:
                perm_desc = f"អនុញ្ញាតឱ្យចូលប្រើទំព័រ {module_name_kh}"
                cursor.execute("""
                    INSERT INTO permissions (name, description, module_id)
                    VALUES (%s, %s, %s)
                """, (permission_name, perm_desc, new_module_id))
            msg = 'បានបន្ថែមម៉ឺនុយថ្មីជោគជ័យ!'

        conn.commit()
        return jsonify({'status': 'success', 'message': msg})
    except Exception as e:
        conn.rollback()
        print(f"Error saving module: {e}")
        return jsonify({'status': 'error', 'message': 'មានបញ្ហាក្នុងការរក្សាទុក!'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ៣. Route សម្រាប់លុប (Delete)
@app.route('/admin/system_modules/delete/<int:id>', methods=['POST'])
def delete_system_module(id):
    if 'loggedin' not in session or session.get('role_name') != 'Super Admin':
        return jsonify({'status': 'error', 'message': 'គ្មានសិទ្ធិ!'})

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # លុបសិទ្ធិក្នុងតារាង permissions មុនសិន ដើម្បីកុំឱ្យជាប់ Foreign Key Error
        cursor.execute("DELETE FROM permissions WHERE module_id = %s", (id,))
        # រួចទើបលុបម៉ឺនុយចេញពីតារាង sys_modules
        cursor.execute("DELETE FROM sys_modules WHERE id = %s", (id,))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'បានលុបម៉ឺនុយជោគជ័យ!'})
    except Exception as e:
        conn.rollback()
        print(f"Error deleting module: {e}")
        return jsonify({'status': 'error', 'message': 'មិនអាចលុបបានទេ! វាអាចជាប់ទាក់ទងនឹងម៉ឺនុយរងផ្សេងទៀត។'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
# ចំណាំ៖ កូដ API ដែលមានស្រាប់ដូចជា /api/get_districts/<id>, /api/get_communes/<id>, /api/get_villages/<id> គឺយើងប្រើដដែល មិនបាច់កែប្រែអ្វីទេ។       
# ==========================================
# បន្ទាត់នេះត្រូវតែនៅក្រោមគេបង្អស់នៃ File app.py ជានិច្ច
# ==========================================
if __name__ == '__main__':
    # កំណត់ Port 5000 ជាស្តង់ដារតែមួយ ទាំង Local (Mac/Windows) និង Server (VPS)
    print("🚀 ប្រព័ន្ធកំពុងដំណើរការលើ Port: 5000")
    app.run(host='127.0.0.1', port=5001, debug=True)
