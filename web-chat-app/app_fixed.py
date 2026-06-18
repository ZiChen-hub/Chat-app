#!/usr/bin/env python3
"""
修复 Windows eventlet 问题的版本
"""

import os
import sys

# 设置环境变量，避免 eventlet 问题
os.environ['EVENTLET_NO_GREENDNS'] = 'yes'

import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash

# Configuration
DATABASE = 'chat.db'
SECRET_KEY = 'dev_key_change_in_production'

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# 使用 threading 模式，避免 eventlet 的 Windows 问题
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='threading',
                   logger=False,
                   engineio_logger=False,
                   ping_timeout=60,
                   ping_interval=30)

# Database helpers
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Users table - 移除 avatar 字段
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                display_name TEXT,
                online BOOLEAN DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read BOOLEAN DEFAULT 0,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (receiver_id) REFERENCES users (id)
            )
        ''')
        # Friends table - 双向好友关系
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                friend_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending', -- pending, accepted, blocked
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, friend_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (friend_id) REFERENCES users (id),
                CHECK (user_id != friend_id)
            )
        ''')
        db.commit()
        
        # Insert demo users if none exist
        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()['count'] == 0:
            demo_users = [
                ('alice', 'password123', 'Alice'),
                ('bob', 'password123', 'Bob'),
                ('charlie', 'password123', 'Charlie'),
                ('diana', 'password123', 'Diana'),
                ('test', 'test', 'Test User'),
            ]
            for uname, pwd, dname in demo_users:
                cursor.execute(
                    "INSERT INTO users (username, password, display_name) VALUES (?, ?, ?)",
                    (uname, generate_password_hash(pwd), dname)
                )
            db.commit()
            
            # 创建一些好友关系
            cursor.execute("SELECT id FROM users WHERE username = 'alice'")
            alice_id = cursor.fetchone()['id']
            cursor.execute("SELECT id FROM users WHERE username = 'bob'")
            bob_id = cursor.fetchone()['id']
            cursor.execute("SELECT id FROM users WHERE username = 'charlie'")
            charlie_id = cursor.fetchone()['id']
            
            # Alice 和 Bob 是好友
            cursor.execute(
                "INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, 'accepted')",
                (alice_id, bob_id)
            )
            cursor.execute(
                "INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, 'accepted')",
                (bob_id, alice_id)
            )
            
            # Alice 和 Charlie 是好友
            cursor.execute(
                "INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, 'accepted')",
                (alice_id, charlie_id)
            )
            cursor.execute(
                "INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, 'accepted')",
                (charlie_id, alice_id)
            )
            
            db.commit()
            print("Demo users and friendships created.")

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['display_name'] = user['display_name']
            # Update online status
            cursor.execute("UPDATE users SET online = 1 WHERE id = ?", (user['id'],))
            db.commit()
            return jsonify({'success': True, 'user': {
                'id': user['id'],
                'username': user['username'],
                'display_name': user['display_name']
            }})
        else:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        display_name = data.get('display_name', '').strip()
        
        # 验证输入
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'}), 400
        
        if len(username) < 3:
            return jsonify({'success': False, 'error': 'Username must be at least 3 characters'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
        
        if not display_name:
            display_name = username
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            # 检查用户名是否已存在
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return jsonify({'success': False, 'error': 'Username already exists'}), 400
            
            # 创建新用户
            cursor.execute(
                "INSERT INTO users (username, password, display_name) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), display_name)
            )
            user_id = cursor.lastrowid
            db.commit()
            
            # 自动登录
            session['user_id'] = user_id
            session['username'] = username
            session['display_name'] = display_name
            
            return jsonify({'success': True, 'user': {
                'id': user_id,
                'username': username,
                'display_name': display_name
            }})
            
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'success': False, 'error': 'Database error: ' + str(e)}), 500
    
    # GET 请求返回注册页面
    return render_template('register.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET online = 0 WHERE id = ?", (session['user_id'],))
        db.commit()
        session.clear()
    return redirect(url_for('login'))

@app.route('/api/user')
def get_current_user():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({
        'id': session['user_id'],
        'username': session['username'],
        'display_name': session['display_name']
    })

@app.route('/api/contacts')
def get_contacts():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    db = get_db()
    cursor = db.cursor()
    
    # 只获取双向好友关系中的联系人
    cursor.execute("""
        SELECT u.id, u.username, u.display_name, u.online, u.last_seen
        FROM users u
        JOIN friends f1 ON u.id = f1.friend_id
        JOIN friends f2 ON u.id = f2.user_id AND f2.friend_id = f1.user_id
        WHERE f1.user_id = ? 
          AND f1.status = 'accepted' 
          AND f2.status = 'accepted'
        ORDER BY u.display_name
    """, (session['user_id'],))
    
    contacts = []
    for row in cursor.fetchall():
        # 获取未读消息数
        cursor.execute("""
            SELECT COUNT(*) as unread
            FROM messages
            WHERE receiver_id = ? AND sender_id = ? AND read = 0
        """, (session['user_id'], row['id']))
        unread = cursor.fetchone()['unread']
        
        # 获取最后一条消息
        cursor.execute("""
            SELECT content, timestamp
            FROM messages
            WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
            ORDER BY timestamp DESC
            LIMIT 1
        """, (session['user_id'], row['id'], row['id'], session['user_id']))
        last_msg = cursor.fetchone()
        
        contacts.append({
            'id': row['id'],
            'username': row['username'],
            'display_name': row['display_name'],
            'online': bool(row['online']),
            'last_seen': row['last_seen'],
            'unread_count': unread,
            'last_message': last_msg['content'] if last_msg else None,
            'last_message_time': last_msg['timestamp'] if last_msg else None
        })
    
    return jsonify(contacts)

@app.route('/api/messages/<int:contact_id>')
def get_messages(contact_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT m.*, u.username as sender_name, u.display_name as sender_display_name
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.timestamp
    """, (session['user_id'], contact_id, contact_id, session['user_id']))
    messages = []
    for row in cursor.fetchall():
        messages.append({
            'id': row['id'],
            'sender_id': row['sender_id'],
            'receiver_id': row['receiver_id'],
            'content': row['content'],
            'timestamp': row['timestamp'],
            'read': bool(row['read']),
            'sender_name': row['sender_name'],
            'sender_display_name': row['sender_display_name']
        })
    # Mark messages as read
    cursor.execute("""
        UPDATE messages SET read = 1
        WHERE sender_id = ? AND receiver_id = ? AND read = 0
    """, (contact_id, session['user_id']))
    db.commit()
    return jsonify(messages)

@app.route('/api/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    
    if not receiver_id or not content:
        return jsonify({'error': 'Missing parameters'}), 400
    
    # 验证是否为双向好友
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) as is_friend 
        FROM friends 
        WHERE user_id = ? AND friend_id = ? AND status = 'accepted'
    """, (session['user_id'], receiver_id))
    
    is_friend = cursor.fetchone()['is_friend'] > 0
    
    if not is_friend:
        return jsonify({'error': 'You can only send messages to friends'}), 403
    
    cursor.execute("""
        INSERT INTO messages (sender_id, receiver_id, content)
        VALUES (?, ?, ?)
    """, (session['user_id'], receiver_id, content))
    db.commit()
    message_id = cursor.lastrowid
    
    # Get the created message
    cursor.execute("""
        SELECT m.*, u.username as sender_name, u.display_name as sender_display_name
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.id = ?
    """, (message_id,))
    row = cursor.fetchone()
    message = {
        'id': row['id'],
        'sender_id': row['sender_id'],
        'receiver_id': row['receiver_id'],
        'content': row['content'],
        'timestamp': row['timestamp'],
        'read': bool(row['read']),
        'sender_name': row['sender_name'],
        'sender_display_name': row['sender_display_name']
    }
    
    # Emit via SocketIO
    socketio.emit('new_message', message, room=f"user_{receiver_id}")
    socketio.emit('new_message', message, room=f"user_{session['user_id']}")
    
    return jsonify({'success': True, 'message': message})

@app.route('/api/friends', methods=['GET'])
def get_friends():
    """获取所有好友请求和好友列表"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    db = get_db()
    cursor = db.cursor()
    
    # 获取好友请求（别人发给我的）
    cursor.execute("""
        SELECT f.id, f.user_id, u.username, u.display_name, f.status, f.created_at
        FROM friends f
        JOIN users u ON f.user_id = u.id
        WHERE f.friend_id = ? AND f.status = 'pending'
        ORDER BY f.created_at DESC
    """, (session['user_id'],))
    pending_requests = []
    for row in cursor.fetchall():
        pending_requests.append({
            'id': row['id'],
            'user_id': row['user_id'],
            'username': row['username'],
            'display_name': row['display_name'],
            'status': row['status'],
            'created_at': row['created_at']
        })
    
    # 获取我发送的好友请求
    cursor.execute("""
        SELECT f.id, f.friend_id, u.username, u.display_name, f.status, f.created_at
        FROM friends f
        JOIN users u ON f.friend_id = u.id
        WHERE f.user_id = ? AND f.status = 'pending'
        ORDER BY f.created_at DESC
    """, (session['user_id'],))
    sent_requests = []
    for row in cursor.fetchall():
        sent_requests.append({
            'id': row['id'],
            'friend_id': row['friend_id'],
            'username': row['username'],
            'display_name': row['display_name'],
            'status': row['status'],
            'created_at': row['created_at']
        })
    
    return jsonify({
        'pending': pending_requests,
        'sent': sent_requests
    })

@app.route('/api/friends/add', methods=['POST'])
def add_friend():
    """添加好友"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    friend_username = data.get('username', '').strip()
    
    if not friend_username:
        return jsonify({'success': False, 'error': 'Username is required'}), 400
    
    if friend_username == session['username']:
        return jsonify({'success': False, 'error': 'Cannot add yourself as friend'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 查找用户
        cursor.execute("SELECT id FROM users WHERE username = ?", (friend_username,))
        friend = cursor.fetchone()
        if not friend:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        friend_id = friend['id']
        
        # 检查是否已经是好友
        cursor.execute("""
            SELECT status FROM friends 
            WHERE user_id = ? AND friend_id = ?
        """, (session['user_id'], friend_id))
        existing = cursor.fetchone()
        
        if existing:
            if existing['status'] == 'pending':
                return jsonify({'success': False, 'error': 'Friend request already sent'}), 400
            elif existing['status'] == 'accepted':
                return jsonify({'success': False, 'error': 'Already friends'}), 400
            elif existing['status'] == 'blocked':
                return jsonify({'success': False, 'error': 'User is blocked'}), 400
        
        # 发送好友请求
        cursor.execute(
            "INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, 'pending')",
            (session['user_id'], friend_id)
        )
        db.commit()
        
        # 通知对方
        socketio.emit('friend_request', {
            'from_user_id': session['user_id'],
            'from_username': session['username'],
            'from_display_name': session['display_name']
        }, room=f"user_{friend_id}")
        
        return jsonify({'success': True, 'message': 'Friend request sent'})
        
    except sqlite3.Error as e:
        db.rollback()
        return jsonify({'success': False, 'error': 'Database error: ' + str(e)}), 500

@app.route('/api/friends/<int:request_id>/accept', methods=['POST'])
def accept_friend(request_id):
    """接受好友请求"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 检查请求是否存在且属于当前用户
        cursor.execute("""
            SELECT f.user_id, f.friend_id 
            FROM friends f 
            WHERE f.id = ? AND f.friend_id = ? AND f.status = 'pending'
        """, (request_id, session['user_id']))
        request_data = cursor.fetchone()
        
        if not request_data:
            return jsonify({'success': False, 'error': 'Friend request not found'}), 404
        
        sender_id = request_data['user_id']
        
        # 更新请求状态为 accepted
        cursor.execute(
            "UPDATE friends SET status = 'accepted', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (request_id,)
        )
        
        # 创建反向好友关系（双向好友）
        cursor.execute("""
            INSERT OR IGNORE INTO friends (user_id, friend_id, status) 
            VALUES (?, ?, 'accepted')
        """, (session['user_id'], sender_id))
        
        db.commit()
        
        # 通知对方
        socketio.emit('friend_accepted', {
            'user_id': session['user_id'],
            'username': session['username'],
            'display_name': session['display_name']
        }, room=f"user_{sender_id}")
        
        return jsonify({'success': True, 'message': 'Friend request accepted'})
        
    except sqlite3.Error as e:
        db.rollback()
        return jsonify({'success': False, 'error': 'Database error: ' + str(e)}), 500

@app.route('/api/friends/<int:request_id>/reject', methods=['POST'])
def reject_friend(request_id):
    """拒绝好友请求"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 检查请求是否存在且属于当前用户
        cursor.execute("""
            SELECT id FROM friends 
            WHERE id = ? AND friend_id = ? AND status = 'pending'
        """, (request_id, session['user_id']))
        
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': 'Friend request not found'}), 404
        
        # 删除请求
        cursor.execute("DELETE FROM friends WHERE id = ?", (request_id,))
        db.commit()
        
        return jsonify({'success': True, 'message': 'Friend request rejected'})
        
    except sqlite3.Error as e:
        db.rollback()
        return jsonify({'success': False, 'error': 'Database error: ' + str(e)}), 500

@app.route('/api/friends/<int:friend_id>/remove', methods=['POST'])
def remove_friend(friend_id):
    """移除好友"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 删除双向好友关系
        cursor.execute("""
            DELETE FROM friends 
            WHERE (user_id = ? AND friend_id = ?) 
               OR (user_id = ? AND friend_id = ?)
        """, (session['user_id'], friend_id, friend_id, session['user_id']))
        
        db.commit()
        return jsonify({'success': True, 'message': 'Friend removed'})
        
    except sqlite3.Error as e:
        db.rollback()
        return jsonify({'success': False, 'error': 'Database error: ' + str(e)}), 500

# SocketIO events
@socketio.on_error()
def error_handler(e):
    print(f"SocketIO 错误: {e}")
    return {'error': str(e)}



@socketio.on('connect')
def handle_connect():
    try:
        if 'user_id' in session:
            join_room(f"user_{session['user_id']}")
            emit('status', {'user_id': session['user_id'], 'online': True}, broadcast=True)
    except Exception as e:
        print(f"连接错误: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    try:
        if 'user_id' in session:
            leave_room(f"user_{session['user_id']}")
            emit('status', {'user_id': session['user_id'], 'online': False}, broadcast=True)
    except Exception as e:
        print(f"断开连接错误: {e}")

@socketio.on('typing')
def handle_typing(data):
    receiver_id = data.get('receiver_id')
    if 'user_id' in session:
        emit('typing', {'sender_id': session['user_id']}, room=f"user_{receiver_id}")

@socketio.on('stop_typing')
def handle_stop_typing(data):
    receiver_id = data.get('receiver_id')
    if 'user_id' in session:
        emit('stop_typing', {'sender_id': session['user_id']}, room=f"user_{receiver_id}")

@socketio.on('mark_read')
def handle_mark_read(data):
    message_id = data.get('message_id')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE messages SET read = 1 WHERE id = ?", (message_id,))
    db.commit()
    emit('message_read', {'message_id': message_id}, broadcast=True)



if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("✅ ChatApp 服务器启动成功！")
    print("📱 移动端访问: http://192.168.1.4:5000")
    print("💻 桌面端访问: http://localhost:5000")
    print("=" * 60)
    
    try:
        socketio.run(app, 
                    host='0.0.0.0', 
                    port=5000, 
                    debug=True, 
                    use_reloader=False,
                    allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n👋 服务器关闭")
    except Exception as e:
        print(f"\n❌ 服务器错误: {e}")
        print("尝试备用启动方式...")
        # 备用方案：纯 HTTP 模式
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)