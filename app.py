#!/usr/bin/env python3
"""
================================================================================
   📢 نظام المراقبة المتكامل - مع تنبيهات تليجرام ولوحة تحكم ويب 📢
   ✅ مراقبة التغييرات في المشاريع
   ✅ إضافة/حذف/تعديل المشاريع من لوحة التحكم
   ✅ تنبيهات فورية عبر تليجرام (لعدة مستخدمين)
   ✅ تنبيهات بتنسيق احترافي
================================================================================
"""

import json
import os
import time
import random
import sqlite3
import threading
from datetime import datetime
from typing import Dict, Optional, List

from flask import Flask, render_template, request, jsonify
from curl_cffi import requests as cf_requests

# =========================================================
# 🔧 إعدادات التليجرام - غيّر هذه القيم 🔧
# =========================================================
TELEGRAM_BOT_TOKEN = "8238448083:AAHJoP2IxojjCzMVLZbuPxaAKdHyaesWMss"  # ضع توكن البوت هنا
# ✅ تم التعديل هنا: أصبحت قائمة (List) لاستقبال عدة معرفات
TELEGRAM_CHAT_IDS = ["8257513771","48599827"]
    
TELEGRAM_ENABLED = True                      # تفعيل/تعطيل التنبيهات

# للحصول على التوكن: ابحث عن @BotFather في التليجرام
# للحصول على المعرف: ابحث عن @userinfobot (يجب على كل مستخدم بدء محادثة مع البوت أولاً)

# =========================================================
# إعدادات Flask
# =========================================================
app = Flask(__name__)
PROJECTS_FILE = "projects.json"
CHECK_INTERVAL = 10  # ثانية بين الفحوصات

# =========================================================
# إعدادات البروكسي
# =========================================================
PROXY_BASE = "http://smart-jmuhv4nqxa5h_area-SA_life-15_session-{session}:qGsWedUUeOMq4ySa@proxy.smartproxy.net:3120"

def get_proxy():
    session = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=12))
    return PROXY_BASE.format(session=session)

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "ar,en;q=0.9",
    "app-locale": "ar",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "referer": "https://sakani.sa/app/land-projects",
    "origin": "https://sakani.sa"
}

# =========================================================
# ✅ دوال التليجرام المُعدلة (لإرسال لمجموعة مستخدمين)
# =========================================================
def send_telegram_message(message: str):
    """إرسال رسالة إلى جميع المعرفات المخزنة في قائمة TELEGRAM_CHAT_IDS"""
    if not TELEGRAM_ENABLED:
        return
    
    # التحقق من صحة الإعدادات
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not TELEGRAM_CHAT_IDS:
        print("⚠️ لم يتم إعداد التليجرام: يرجى إدخال التوكن وإضافة معرفات في القائمة")
        return
    
    # التأكد من عدم وجود معرفات فارغة أو مكررة (اختياري)
    unique_chat_ids = list(set([cid for cid in TELEGRAM_CHAT_IDS if cid and str(cid).strip()]))
    
    if not unique_chat_ids:
        print("⚠️ لا توجد معرفات صالحة للإرسال")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        for chat_id in unique_chat_ids:
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            # إضافة محاولة إعادة المحاولة (Retry) لتجنب أخطاء الشبكة العابرة
            for attempt in range(2):
                try:
                    response = cf_requests.post(url, json=data, timeout=10)
                    if response.status_code == 200:
                        print(f"📨 تم إرسال التنبيه إلى {chat_id}")
                        break  # نجحت العملية، نخرج من حلقة إعادة المحاولة
                    else:
                        print(f"⚠️ فشل إرسال التنبيه لـ {chat_id} (حاول {attempt+1}/2): {response.status_code}")
                except Exception as e:
                    print(f"⚠️ خطأ في الإرسال لـ {chat_id} (حاول {attempt+1}/2): {e}")
                    if attempt == 1:
                        print(f"❌ فشل إرسال التنبيه لـ {chat_id} بعد محاولتين")
                time.sleep(0.5)  # انتظار نصف ثانية بين محاولات إعادة الإرسال لنفس المستخدم
            
            # تأخير بسيط بين المستخدمين لتجنب Rate Limiting من تليجرام
            time.sleep(0.3)
            
    except Exception as e:
        print(f"❌ خطأ عام في إرسال التليجرام: {e}")

def send_test_message():
    """إرسال رسالة اختبار للتحقق من إعدادات التليجرام لجميع المستخدمين"""
    message = """
🔰 <b>نظام المراقبة يعمل!</b> 🔰

✅ تم تشغيل نظام المراقبة بنجاح
📊 سيتم إشعارك عند أي تغيير في المشاريع
👥 تم إعداد التنبيهات للإرسال لعدة مستخدمين
⏰ الوقت: {time}

<i>جميع التنبيهات اللاحقة ستصل بهذا التنسيق</i>
""".format(time=datetime.now().strftime('%Y-%m-%d %I:%M:%S %p'))
    
    send_telegram_message(message)

# =========================================================
# دوال المشاريع (حفظ وتحميل) - لم تتغير
# =========================================================
def load_projects():
    """تحميل المشاريع من ملف JSON"""
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_projects(projects):
    """حفظ المشاريع في ملف JSON"""
    with open(PROJECTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(projects, f, indent=2, ensure_ascii=False)

# =========================================================
# قاعدة البيانات - لم تتغير
# =========================================================
def init_db():
    """تهيئة قاعدة البيانات"""
    conn = sqlite3.connect('monitoring.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS project_history (
            project_id INTEGER,
            timestamp TEXT,
            available_units INTEGER,
            booked_units INTEGER,
            inactive_units INTEGER,
            PRIMARY KEY (project_id, timestamp)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            project_id INTEGER,
            project_name TEXT,
            change_type TEXT,
            old_value INTEGER,
            new_value INTEGER,
            alert_text TEXT,
            sent_to_telegram INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def save_history(project_id, data):
    """حفظ تاريخ المشروع"""
    conn = sqlite3.connect('monitoring.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO project_history 
        (project_id, timestamp, available_units, booked_units, inactive_units)
        VALUES (?, ?, ?, ?, ?)
    ''', (project_id, data['timestamp'], data['available_units'], 
          data['booked_units'], data['inactive_units']))
    conn.commit()
    conn.close()

def save_alert(project_id, project_name, change_type, old_value, new_value, alert_text, sent_to_telegram=0):
    """حفظ التنبيه في قاعدة البيانات"""
    conn = sqlite3.connect('monitoring.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO alerts (timestamp, project_id, project_name, change_type, old_value, new_value, alert_text, sent_to_telegram)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), project_id, 
          project_name, change_type, old_value, new_value, alert_text, sent_to_telegram))
    conn.commit()
    conn.close()

def get_last_history(project_id):
    """جلب آخر تاريخ للمشروع"""
    conn = sqlite3.connect('monitoring.db')
    c = conn.cursor()
    c.execute('''
        SELECT available_units, booked_units, inactive_units, timestamp
        FROM project_history 
        WHERE project_id = ? 
        ORDER BY timestamp DESC LIMIT 1
    ''', (project_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'available_units': row[0],
            'booked_units': row[1],
            'inactive_units': row[2],
            'timestamp': row[3]
        }
    return None

# =========================================================
# جلب بيانات المشروع من API - لم تتغير
# =========================================================
def get_project_data(project_id: int, project_info: dict) -> Optional[Dict]:
    """جلب بيانات المشروع من API"""
    reference_unit = project_info.get('reference_unit')
    if not reference_unit:
        return None
    
    url = f"https://sakani.sa/mainIntermediaryApi/v4/units/{reference_unit}?include=project,project.project_unit_types"
    proxy = get_proxy()
    
    try:
        response = cf_requests.get(
            url,
            headers=HEADERS,
            proxies={"http": proxy, "https": proxy},
            impersonate="chrome120",
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            
            total_inactive = 0
            total_units = 0
            available_units = 0
            booked_units = 0
            
            for item in data.get('included', []):
                if item.get('type') == 'projects':
                    attrs = item.get('attributes', {})
                    stats = attrs.get('units_statistic_data', {})
                    total_units = stats.get('all_units_count', 0)
                    available_units = stats.get('available_units_count', 0)
                    booked_units = stats.get('published_booked_count', 0)
                
                if item.get('type') == 'project_unit_types':
                    total_inactive += item.get('attributes', {}).get('inactive_unit_count', 0)
            
            return {
                'project_id': project_id,
                'project_name': project_info['name'],
                'total_units': total_units,
                'available_units': available_units,
                'booked_units': booked_units,
                'inactive_units': total_inactive,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        return None
    except Exception as e:
        print(f"❌ خطأ في المشروع {project_id}: {e}")
        return None

# =========================================================
# تنسيق التنبيه - لم تتغير
# =========================================================
def format_alert(project_name: str, change_type: str, old_value: int, new_value: int) -> str:
    """تنسيق التنبيه للعرض في الكونسول"""
    now = datetime.now()
    time_str = now.strftime('%I:%M:%S.%f')[:-3]
    
    if change_type == 'cancellation' or (change_type == 'inactive' and new_value > old_value):
        title = "📢 إلغاء حجز"
    elif change_type == 'available' and new_value > old_value:
        title = "🟢 وحدات جديدة متاحة"
    elif change_type == 'booked' and new_value > old_value:
        title = "📝 حجز جديد"
    else:
        title = "📊 تحديث في المشروع"
    
    alert_lines = []
    alert_lines.append("=" * 50)
    alert_lines.append(title)
    alert_lines.append("=" * 50)
    alert_lines.append(f"📌 المشروع: {project_name}")
    alert_lines.append(f"📊 السابق: {old_value}")
    alert_lines.append(f"📊 الحالي: {new_value}")
    alert_lines.append("-" * 50)
    alert_lines.append(f"⏰ الوقت: {time_str}")
    alert_lines.append("=" * 50)
    
    return "\n".join(alert_lines)

def format_telegram_alert(project_name: str, change_type: str, old_value: int, new_value: int) -> str:
    """تنسيق التنبيه للتليجرام (HTML)"""
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%I:%M:%S %p')
    
    if change_type == 'cancellation' or (change_type == 'inactive' and new_value > old_value):
        title = "❌ إلغاء حجز"
        icon = "❌"
    elif change_type == 'available' and new_value > old_value:
        title = "🟢 وحدات جديدة متاحة"
        icon = "🟢"
    elif change_type == 'booked' and new_value > old_value:
        title = "📝 حجز جديد"
        icon = "📝"
    else:
        title = "📊 تحديث في المشروع"
        icon = "📊"
    
    diff = new_value - old_value
    diff_symbol = "+" if diff > 0 else ""
    
    alert = f"""
<b>{icon} {title}</b>

<b>🏠 المشروع:</b> {project_name}
<b>📊 السابق:</b> {old_value}
<b>📊 الحالي:</b> {new_value}
<b>📈 التغير:</b> {diff_symbol}{diff}

<b>⏰ التاريخ:</b> {date_str}
<b>⏰ الوقت:</b> {time_str}

━━━━━━━━━━━━━━━━━━━━
🔔 <i>تم اكتشاف التغيير تلقائياً</i>
"""
    return alert

# =========================================================
# التحقق من التغييرات وإرسال التنبيه - لم تتغير
# =========================================================
last_data = {}

def check_and_alert(project_id: int, project_name: str, current_data: dict):
    """التحقق من التغييرات وإرسال تنبيه"""
    global last_data
    
    previous = last_data.get(project_id)
    
    if not previous:
        last_data[project_id] = current_data
        save_history(project_id, current_data)
        return
    
    changes = []
    
    # فحص الوحدات الغير نشطة (إلغاء حجز)
    if previous.get('inactive_units') != current_data['inactive_units']:
        old_val = previous.get('inactive_units', 0)
        new_val = current_data['inactive_units']
        if new_val != old_val:
            changes.append(('inactive', old_val, new_val))
    
    # فحص الوحدات المتاحة
    if previous.get('available_units') != current_data['available_units']:
        old_val = previous.get('available_units', 0)
        new_val = current_data['available_units']
        if new_val != old_val:
            changes.append(('available', old_val, new_val))
    
    # فحص الوحدات المحجوزة
    if previous.get('booked_units') != current_data['booked_units']:
        old_val = previous.get('booked_units', 0)
        new_val = current_data['booked_units']
        if new_val != old_val:
            changes.append(('booked', old_val, new_val))
    
    # إرسال تنبيه لكل تغيير
    for change_type, old_val, new_val in changes:
        # تنبيه للكونسول
        alert_text = format_alert(project_name, change_type, old_val, new_val)
        print(f"\n{alert_text}\n")
        
        # تنبيه للتليجرام (الدالة الجديدة ستتعامل مع عدة مستخدمين)
        telegram_alert = format_telegram_alert(project_name, change_type, old_val, new_val)
        send_telegram_message(telegram_alert)
        
        # حفظ في قاعدة البيانات
        save_alert(project_id, project_name, change_type, old_val, new_val, alert_text, 1)
    
    # تحديث آخر البيانات
    last_data[project_id] = current_data
    save_history(project_id, current_data)

# =========================================================
# حلقة المراقبة المستمرة - لم تتغير
# =========================================================
def monitoring_loop():
    """حلقة المراقبة المستمرة"""
    print("=" * 60)
    print("   📢 نظام المراقبة - قيد التشغيل")
    print("=" * 60)
    print("✅ يمكنك إدارة المشاريع من http://localhost:5000")
    print(f"⏱️  فترة الفحص: كل {CHECK_INTERVAL} ثانية")
    
    # عرض حالة التليجرام بشكل صحيح مع القائمة الجديدة
    is_telegram_ready = (TELEGRAM_ENABLED and 
                         TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE" and 
                         len(TELEGRAM_CHAT_IDS) > 0 and
                         TELEGRAM_CHAT_IDS[0] != "7538070681") # تحقق بسيط
    print(f"📨 التليجرام: {'مفعل (' + str(len(TELEGRAM_CHAT_IDS)) + ' مستخدم)' if is_telegram_ready else 'غير مفعل'}")
    print("=" * 60)
    print("\n🚀 بدء المراقبة...\n")
    
    # إرسال رسالة اختبار للتليجرام لجميع المستخدمين
    if is_telegram_ready:
        send_test_message()
    
    while True:
        try:
            projects = load_projects()
            
            for project_id, info in projects.items():
                if not info.get('reference_unit'):
                    continue
                
                current_data = get_project_data(int(project_id), info)
                if current_data:
                    check_and_alert(int(project_id), info['name'], current_data)
                    print(f"✅ {info['name']}: متاح={current_data['available_units']} | غير نشط={current_data['inactive_units']}")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n🛑 تم إيقاف المراقبة")
            break
        except Exception as e:
            print(f"❌ خطأ: {e}")
            time.sleep(CHECK_INTERVAL)

# =========================================================
# APIs للوحة التحكم - تحديث طفيف في رسالة التليجرام
# =========================================================
@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('dashboard.html')

@app.route('/api/projects', methods=['GET'])
def api_get_projects():
    """جلب قائمة المشاريع"""
    projects = load_projects()
    return jsonify(projects)

@app.route('/api/projects', methods=['POST'])
def api_add_project():
    """إضافة مشروع جديد"""
    data = request.get_json()
    
    project_id = data.get('project_id')
    project_name = data.get('project_name')
    reference_unit = data.get('reference_unit')
    
    if not project_id or not project_name or not reference_unit:
        return jsonify({'error': 'جميع الحقول مطلوبة'}), 400
    
    try:
        project_id = str(int(project_id))
        reference_unit = int(reference_unit)
    except ValueError:
        return jsonify({'error': 'رقم المشروع والوحدة المرجعية يجب أن تكون أرقاماً'}), 400
    
    projects = load_projects()
    
    if project_id in projects:
        return jsonify({'error': f'المشروع {project_id} موجود مسبقاً'}), 400
    
    projects[project_id] = {
        'name': project_name,
        'reference_unit': reference_unit,
        'alert_enabled': True,
        'added_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    save_projects(projects)
    
    # إرسال إشعار تليجرام بإضافة مشروع جديد (سيصل للجميع)
    msg = f"➕ <b>تم إضافة مشروع جديد</b>\n\n<b>🏠 المشروع:</b> {project_name}\n<b>🆔 ID:</b> {project_id}\n<b>🔢 الوحدة المرجعية:</b> {reference_unit}"
    send_telegram_message(msg)
    
    return jsonify({'success': True, 'message': 'تم إضافة المشروع بنجاح'})

@app.route('/api/projects/<project_id>', methods=['DELETE'])
def api_delete_project(project_id):
    """حذف مشروع"""
    projects = load_projects()
    
    if project_id not in projects:
        return jsonify({'error': 'المشروع غير موجود'}), 404
    
    project_name = projects[project_id].get('name', 'غير معروف')
    del projects[project_id]
    save_projects(projects)
    
    if project_id in last_data:
        del last_data[project_id]
    
    # إرسال إشعار تليجرام بحذف مشروع (سيصل للجميع)
    msg = f"🗑️ <b>تم حذف مشروع</b>\n\n<b>🏠 المشروع:</b> {project_name}\n<b>🆔 ID:</b> {project_id}"
    send_telegram_message(msg)
    
    return jsonify({'success': True, 'message': 'تم حذف المشروع بنجاح'})

@app.route('/api/projects/<project_id>', methods=['PUT'])
def api_update_project(project_id):
    """تحديث وحدة مرجعية لمشروع"""
    data = request.get_json()
    projects = load_projects()
    
    if project_id not in projects:
        return jsonify({'error': 'المشروع غير موجود'}), 404
    
    old_ref = projects[project_id].get('reference_unit')
    
    if 'reference_unit' in data:
        projects[project_id]['reference_unit'] = int(data['reference_unit'])
    
    save_projects(projects)
    
    # إرسال إشعار تليجرام بتحديث المشروع (سيصل للجميع)
    msg = f"✏️ <b>تم تحديث مشروع</b>\n\n<b>🏠 المشروع:</b> {projects[project_id]['name']}\n<b>🆔 ID:</b> {project_id}\n<b>🔢 الوحدة المرجعية القديمة:</b> {old_ref}\n<b>🔢 الوحدة المرجعية الجديدة:</b> {projects[project_id]['reference_unit']}"
    send_telegram_message(msg)
    
    return jsonify({'success': True, 'message': 'تم تحديث المشروع بنجاح'})

@app.route('/api/status')
def api_status():
    """جلب الحالة الحالية"""
    projects = load_projects()
    status = {}
    
    for pid, info in projects.items():
        if info.get('reference_unit'):
            data = get_project_data(int(pid), info)
            if data:
                status[pid] = {
                    'name': info['name'],
                    'available': data['available_units'],
                    'booked': data['booked_units'],
                    'inactive': data['inactive_units'],
                    'total': data['total_units']
                }
    
    return jsonify(status)

@app.route('/api/alerts')
def api_alerts():
    """جلب آخر التنبيهات"""
    conn = sqlite3.connect('monitoring.db')
    c = conn.cursor()
    c.execute('SELECT timestamp, project_name, change_type, old_value, new_value FROM alerts ORDER BY id DESC LIMIT 50')
    rows = c.fetchall()
    conn.close()
    
    alerts = []
    for row in rows:
        alerts.append({
            'timestamp': row[0],
            'project_name': row[1],
            'change_type': row[2],
            'old_value': row[3],
            'new_value': row[4]
        })
    
    return jsonify(alerts)

@app.route('/api/telegram/status')
def api_telegram_status():
    """جلب حالة التليجرام"""
    is_configured = TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE" and len(TELEGRAM_CHAT_IDS) > 0
    return jsonify({
        'enabled': TELEGRAM_ENABLED,
        'configured': is_configured,
        'recipients_count': len(TELEGRAM_CHAT_IDS) if is_configured else 0
    })

@app.route('/api/telegram/test', methods=['POST'])
def api_telegram_test():
    """إرسال رسالة اختبار للتليجرام لجميع المستخدمين"""
    send_test_message()
    return jsonify({'success': True, 'message': f'تم إرسال رسالة اختبار إلى {len(TELEGRAM_CHAT_IDS)} مستخدم(ين)'})

# =========================================================
# التشغيل الرئيسي
# =========================================================
def main():
    """تشغيل النظام"""
    init_db()
    
    # إنشاء مشاريع افتراضية إذا لم يكن هناك
    if not os.path.exists(PROJECTS_FILE):
        default_projects = {
            "165": {
                "name": "مشروع التلال ",
                "reference_unit": 615079 ,
                "alert_enabled": True,
                "added_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            "208": {
                "name": "مشروع ربوع الأسياح",
                "reference_unit": 663602,
                "alert_enabled": True,
                "added_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }
        save_projects(default_projects)
    
    # تشغيل المراقبة في خيط منفصل
    monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitor_thread.start()
    
    # تشغيل خادم Flask
import os

print("\n🌐 تشغيل السيرفر...\n")

port = int(os.environ.get("PORT", 5000))
app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()