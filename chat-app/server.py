# server_db.py - 使用SQLite数据库的服务器
import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库初始化
def init_database():
    """初始化数据库"""
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nickname TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP,
            is_online BOOLEAN DEFAULT 0
        )
    ''')
    
    # 创建好友关系表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (friend_id) REFERENCES users(id),
            UNIQUE(user_id, friend_id)
        )
    ''')
    
    # 创建消息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT 0,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (receiver_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("数据库初始化完成")

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.conn = sqlite3.connect('chat.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
    
    def get_user(self, username: str):
        """获取用户"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        return cursor.fetchone()
    
    def create_user(self, username: str, password: str, nickname: str = None):
        """创建用户"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password, nickname) VALUES (?, ?, ?)',
                (username, password, nickname or username)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def add_friend(self, username: str, friend_username: str):
        """添加好友关系"""
        try:
            # 获取用户ID
            user = self.get_user(username)
            friend = self.get_user(friend_username)
            
            if not user or not friend:
                return False
            
            cursor = self.conn.cursor()
            
            # 检查是否已经是好友
            cursor.execute(
                'SELECT * FROM friends WHERE user_id = ? AND friend_id = ?',
                (user['id'], friend['id'])
            )
            if cursor.fetchone():
                return True  # 已经是好友
            
            # 添加双向好友关系
            cursor.execute(
                'INSERT INTO friends (user_id, friend_id) VALUES (?, ?)',
                (user['id'], friend['id'])
            )
            cursor.execute(
                'INSERT INTO friends (user_id, friend_id) VALUES (?, ?)',
                (friend['id'], user['id'])
            )
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加好友失败: {e}")
            return False
    
    def get_friends(self, username: str):
        """获取好友列表"""
        user = self.get_user(username)
        if not user:
            return []
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT u.username, u.nickname, u.is_online, u.last_seen
            FROM friends f
            JOIN users u ON f.friend_id = u.id
            WHERE f.user_id = ?
            ORDER BY u.is_online DESC, u.nickname
        ''', (user['id'],))
        
        friends = []
        for row in cursor.fetchall():
            friends.append({
                'username': row['username'],
                'nickname': row['nickname'],
                'is_online': bool(row['is_online']),
                'last_seen': row['last_seen']
            })
        
        return friends
    
    def search_users(self, query: str):
        """搜索用户"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT username, nickname, is_online 
            FROM users 
            WHERE username LIKE ? OR nickname LIKE ?
            ORDER BY is_online DESC, username
        ''', (f'%{query}%', f'%{query}%'))
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'username': row['username'],
                'nickname': row['nickname'],
                'is_online': bool(row['is_online'])
            })
        
        return users
    
    def update_user_status(self, username: str, is_online: bool):
        """更新用户在线状态"""
        cursor = self.conn.cursor()
        cursor.execute(
            'UPDATE users SET is_online = ?, last_seen = ? WHERE username = ?',
            (1 if is_online else 0, datetime.now().isoformat(), username)
        )
        self.conn.commit()
    
    def save_message(self, sender: str, receiver: str, content: str):
        """保存消息"""
        sender_user = self.get_user(sender)
        receiver_user = self.get_user(receiver)
        
        if not sender_user or not receiver_user:
            return False
        
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)',
            (sender_user['id'], receiver_user['id'], content)
        )
        self.conn.commit()
        return True

class ConnectionManager:
    """连接管理器"""
    
    def __init__(self, db: DatabaseManager):
        self.active_connections: Dict[str, WebSocket] = {}
        self.db = db
    
    async def connect(self, websocket: WebSocket, username: str):
        """用户连接"""
        await websocket.accept()
        self.active_connections[username] = websocket
        
        # 更新在线状态
        self.db.update_user_status(username, True)
        logger.info(f"用户 {username} 已连接")
        
        # 通知好友上线
        await self.notify_friends_status(username, True)
    
    def disconnect(self, username: str):
        """用户断开连接"""
        if username in self.active_connections:
            del self.active_connections[username]
        
        # 更新在线状态
        self.db.update_user_status(username, False)
        logger.info(f"用户 {username} 已断开")
        
        # 通知好友下线
        asyncio.create_task(self.notify_friends_status(username, False))
    
    async def send_personal_message(self, message: dict, username: str):
        """发送消息给指定用户"""
        if username in self.active_connections:
            try:
                await self.active_connections[username].send_json(message)
            except:
                logger.warning(f"发送消息失败给用户 {username}")
    
    async def notify_friends_status(self, username: str, is_online: bool):
        """通知好友在线状态变化"""
        friends = self.db.get_friends(username)
        
        for friend in friends:
            if friend['username'] in self.active_connections:
                try:
                    await self.active_connections[friend['username']].send_json({
                        "type": "user_status",
                        "username": username,
                        "is_online": is_online,
                        "timestamp": datetime.now().isoformat()
                    })
                except:
                    pass

# 初始化数据库
init_database()
db_manager = DatabaseManager()

# 创建测试用户
def create_test_users():
    """创建测试用户"""
    test_users = [
        ("alice", "123456", "Alice"),
        ("bob", "123456", "Bob"),
        ("charlie", "123456", "Charlie")
    ]
    
    for username, password, nickname in test_users:
        if not db_manager.get_user(username):
            db_manager.create_user(username, password, nickname)
    
    # 建立好友关系
    db_manager.add_friend("alice", "bob")
    db_manager.add_friend("alice", "charlie")
    
    logger.info("测试用户创建完成")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    # 启动时
    print("服务器启动中...")
    create_test_users()
    yield
    # 关闭时
    print("服务器关闭")

# 创建FastAPI应用
app = FastAPI(title="聊天服务器 - 数据库版", lifespan=lifespan)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建连接管理器
manager = ConnectionManager(db_manager)

# API端点
@app.post("/register")
async def register(username: str, password: str, nickname: str = None):
    """用户注册"""
    if len(username) < 3 or len(username) > 20:
        raise HTTPException(status_code=400, detail="用户名长度3-20位")
    
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")
    
    if db_manager.get_user(username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    if db_manager.create_user(username, password, nickname):
        return {"message": "注册成功", "username": username}
    else:
        raise HTTPException(status_code=500, detail="注册失败")

@app.post("/login")
async def login(username: str, password: str):
    """用户登录"""
    user = db_manager.get_user(username)
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")
    
    if user['password'] != password:
        raise HTTPException(status_code=400, detail="密码错误")
    
    return {
        "message": "登录成功",
        "username": username,
        "nickname": user['nickname']
    }

@app.get("/search")
async def search_user(query: str):
    """搜索用户"""
    users = db_manager.search_users(query)
    return users

@app.post("/add_friend")
async def add_friend(username: str, friend_username: str):
    """添加好友"""
    if not db_manager.get_user(username):
        raise HTTPException(status_code=400, detail="用户不存在")
    
    if not db_manager.get_user(friend_username):
        raise HTTPException(status_code=400, detail="好友用户不存在")
    
    if username == friend_username:
        raise HTTPException(status_code=400, detail="不能添加自己为好友")
    
    if db_manager.add_friend(username, friend_username):
        return {"message": "好友添加成功"}
    else:
        raise HTTPException(status_code=500, detail="添加好友失败")

@app.get("/friends/{username}")
async def get_friends(username: str):
    """获取好友列表"""
    if not db_manager.get_user(username):
        raise HTTPException(status_code=400, detail="用户不存在")
    
    friends = db_manager.get_friends(username)
    return friends

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    """WebSocket连接处理"""
    # 验证用户
    if not db_manager.get_user(username):
        await websocket.close(code=1008, reason="用户不存在")
        return
    
    await manager.connect(websocket, username)
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "chat":
                    receiver = message.get("to")
                    content = message.get("content")
                    
                    if not receiver or not content:
                        continue
                    
                    if not db_manager.get_user(receiver):
                        await websocket.send_json({
                            "type": "error",
                            "message": "用户不存在"
                        })
                        continue
                    
                    # 保存消息到数据库
                    db_manager.save_message(username, receiver, content)
                    
                    # 构建消息对象
                    chat_message = {
                        "type": "chat",
                        "from": username,
                        "to": receiver,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                        "sender_nickname": db_manager.get_user(username)['nickname']
                    }
                    
                    # 发送给接收者
                    await manager.send_personal_message(chat_message, receiver)
                    
                    # 发送确认给自己
                    await websocket.send_json({
                        **chat_message,
                        "status": "sent"
                    })
                    
                    logger.info(f"消息: {username} -> {receiver}: {content[:50]}...")
                    
            except json.JSONDecodeError:
                logger.error(f"无效的JSON: {data}")
                
    except WebSocketDisconnect:
        manager.disconnect(username)
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        manager.disconnect(username)

@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "聊天服务器运行中 - 数据库版",
        "version": "2.0.0",
        "online_users": len(manager.active_connections),
        "timestamp": datetime.now().isoformat()
    }

def run_server(host="0.0.0.0", port=8000):
    """启动服务器"""
    print("=" * 60)
    print("聊天服务器 v2.0.0 (数据库版)")
    print(f"HTTP地址: http://{host}:{port}")
    print(f"WebSocket地址: ws://{host}:{port}/ws/{{用户名}}")
    print("数据库文件: chat.db")
    print("=" * 60)
    print("测试账号 (自动创建):")
    print("  alice   - 密码: 123456 - 好友: bob, charlie")
    print("  bob     - 密码: 123456 - 好友: alice")
    print("  charlie - 密码: 123456 - 好友: alice")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    run_server()