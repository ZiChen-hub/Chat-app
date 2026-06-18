# client_fixed_ui.py - 修复UI更新问题
import sys
import json
import asyncio
import aiohttp
import websockets
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QSplitter, QFrame, QMessageBox, QInputDialog, QDialog,
    QDialogButtonBox, QFormLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer, QMutex, QMutexLocker
from PyQt5.QtGui import QFont, QColor, QTextCursor

# 抑制警告
import os
os.environ["QT_LOGGING_RULES"] = "*.debug=false"

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class WebSocketClient(QThread):
    """WebSocket客户端"""
    
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    message_received = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, server_url, username):
        super().__init__()
        self.server_url = server_url
        self.username = username
        self.ws = None
        self.running = True
    
    def run(self):
        """运行线程"""
        asyncio.run(self._run())
    
    async def _run(self):
        """异步运行"""
        try:
            await self.connect()
        except Exception as e:
            self.error.emit(str(e))
    
    async def connect(self):
        """连接WebSocket"""
        try:
            ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = f"{ws_url}/ws/{self.username}"
            print(f"[WebSocket] 连接: {ws_url}")
            
            self.ws = await websockets.connect(ws_url)
            self.connected.emit()
            print("[WebSocket] 连接成功")
            
            # 接收消息
            await self.receive_messages()
            
        except Exception as e:
            print(f"[WebSocket] 连接失败: {e}")
            raise
    
    async def receive_messages(self):
        """接收消息"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    self.message_received.emit(data)
                except json.JSONDecodeError:
                    print(f"[WebSocket] 无效JSON: {message}")
                    
        except websockets.exceptions.ConnectionClosed:
            print("[WebSocket] 连接关闭")
            self.disconnected.emit()
        except Exception as e:
            print(f"[WebSocket] 接收错误: {e}")
            self.error.emit(str(e))
    
    async def send_async(self, data):
        """异步发送"""
        if self.ws:
            try:
                await self.ws.send(json.dumps(data))
            except Exception as e:
                print(f"[WebSocket] 发送失败: {e}")
    
    def send(self, data):
        """发送消息"""
        asyncio.run_coroutine_threadsafe(self.send_async(data), asyncio.get_event_loop())
    
    def stop(self):
        """停止"""
        self.running = False
        if self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.close(), asyncio.get_event_loop())

class ChatWindow(QMainWindow):
    """聊天主窗口 - 修复UI更新"""
    
    def __init__(self, server_url, username):
        super().__init__()
        self.server_url = server_url
        self.username = username
        self.current_chat = None
        
        # 数据存储
        self.friends = {}  # username -> friend_info
        self.friend_items = {}  # username -> QListWidgetItem
        
        # HTTP客户端
        self.http_session = None
        
        # WebSocket客户端
        self.ws_client = None
        
        # 互斥锁
        self.mutex = QMutex()
        
        self.setup_ui()
        self.initialize()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle(f"聊天 - {self.username}")
        self.setGeometry(100, 100, 900, 600)
        
        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)
        
        # 主布局
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 左侧联系人面板
        left_panel = QWidget()
        left_panel.setMinimumWidth(250)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # 用户信息
        user_info = QLabel(f"👤 {self.username}")
        user_info.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 14px;
                padding: 10px;
                background: #e3f2fd;
                border-radius: 8px;
                margin-bottom: 10px;
            }
        """)
        user_info.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(user_info)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ 添加")
        self.add_btn.clicked.connect(self.add_friend)
        btn_layout.addWidget(self.add_btn)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_friends)
        btn_layout.addWidget(self.refresh_btn)
        
        left_layout.addLayout(btn_layout)
        
        # 联系人列表标题
        contacts_title = QLabel("💬 联系人")
        contacts_title.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #555;
                margin-top: 10px;
                margin-bottom: 5px;
                padding-left: 5px;
            }
        """)
        left_layout.addWidget(contacts_title)
        
        # 联系人列表 - 使用简单的样式
        self.contact_list = QListWidget()
        self.contact_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                background: white;
            }
        """)
        self.contact_list.itemClicked.connect(self.on_contact_selected)
        left_layout.addWidget(self.contact_list)
        
        layout.addWidget(left_panel)
        
        # 右侧聊天面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # 聊天标题
        self.chat_title = QLabel("请选择联系人开始聊天")
        self.chat_title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background: #f5f5f5;
                border-radius: 5px;
            }
        """)
        self.chat_title.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.chat_title)
        
        # 消息显示区域
        self.message_display = QTextEdit()
        self.message_display.setReadOnly(True)
        self.message_display.setFont(QFont("Arial", 10))
        right_layout.addWidget(self.message_display, 1)
        
        # 输入区域
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入消息...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field, 1)
        
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn)
        
        right_layout.addLayout(input_layout)
        
        layout.addWidget(right_panel, 1)
        
        # 状态栏
        self.statusBar().showMessage("正在初始化...")
    
    def initialize(self):
        """初始化客户端"""
        print(f"[初始化] 用户: {self.username}")
        print(f"[初始化] 服务器: {self.server_url}")
        
        # 延迟启动异步任务
        QTimer.singleShot(100, self.start_async_tasks)
    
    def start_async_tasks(self):
        """启动异步任务"""
        # 创建新的事件循环
        self.loop = asyncio.new_event_loop()
        
        # 在线程中运行事件循环
        import threading
        self.async_thread = threading.Thread(
            target=self.run_event_loop,
            daemon=True
        )
        self.async_thread.start()
        
        # 启动初始化任务
        self.run_async_task(self.async_initialize())
    
    def run_event_loop(self):
        """运行事件循环"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def run_async_task(self, coro):
        """运行异步任务"""
        asyncio.run_coroutine_threadsafe(coro, self.loop)
    
    async def async_initialize(self):
        """异步初始化"""
        try:
            print("[初始化] 创建HTTP会话")
            self.http_session = aiohttp.ClientSession()
            
            print("[初始化] 加载好友列表")
            await self.load_friends()
            
            print("[初始化] 连接WebSocket")
            await self.connect_websocket()
            
            self.statusBar().showMessage("就绪", 2000)
            print("[初始化] 完成")
            
        except Exception as e:
            print(f"[初始化] 失败: {e}")
            self.show_message("错误", f"初始化失败: {str(e)}")
    
    async def load_friends(self):
        """加载好友列表"""
        try:
            url = f"{self.server_url}/friends/{self.username}"
            print(f"[HTTP] 请求好友列表: {url}")
            
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    friends = await response.json()
                    print(f"[HTTP] 收到好友数据: {friends}")
                    self.update_friends_list(friends)
                else:
                    error = await response.text()
                    print(f"[HTTP] 请求失败: {response.status}, {error}")
                    self.update_friends_list([])
                    
        except Exception as e:
            print(f"[HTTP] 加载好友失败: {e}")
            self.update_friends_list([])
    
    def update_friends_list(self, friends):
        """更新好友列表 - 确保在主线程中执行"""
        def update():
            with QMutexLocker(self.mutex):
                print(f"[UI] 开始更新好友列表，数量: {len(friends) if friends else 0}")
                
                # 清空列表
                self.contact_list.clear()
                self.friends = {}
                self.friend_items = {}
                
                if not friends:
                    # 显示空状态
                    item = QListWidgetItem("暂无好友")
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(QColor("#999"))
                    self.contact_list.addItem(item)
                    print("[UI] 显示'暂无好友'")
                    return
                
                # 添加好友
                for friend in friends:
                    username = friend["username"]
                    nickname = friend["nickname"]
                    is_online = friend["is_online"]
                    
                    # 存储好友信息
                    self.friends[username] = friend
                    
                    # 创建显示文本
                    status = "🟢" if is_online else "⚫"
                    display_text = f"{status} {nickname}"
                    
                    # 创建列表项
                    item = QListWidgetItem(display_text)
                    
                    # 设置颜色
                    if is_online:
                        item.setForeground(QColor("#4CAF50"))
                    else:
                        item.setForeground(QColor("#757575"))
                    
                    # 存储引用
                    self.friend_items[username] = item
                    self.contact_list.addItem(item)
                    
                    print(f"[UI] 添加好友: {display_text} ({username})")
                
                print(f"[UI] 好友列表更新完成，共 {len(friends)} 个好友")
        
        # 在主线程中执行UI更新
        QTimer.singleShot(0, update)
    
    async def connect_websocket(self):
        """连接WebSocket"""
        try:
            self.ws_client = WebSocketClient(self.server_url, self.username)
            
            # 连接信号
            self.ws_client.connected.connect(self.on_ws_connected)
            self.ws_client.disconnected.connect(self.on_ws_disconnected)
            self.ws_client.message_received.connect(self.on_ws_message)
            self.ws_client.error.connect(self.on_ws_error)
            
            # 启动WebSocket线程
            self.ws_client.start()
            
        except Exception as e:
            print(f"[WebSocket] 连接失败: {e}")
            self.show_message("错误", f"WebSocket连接失败: {str(e)}")
    
    def add_friend(self):
        """添加好友"""
        # 获取建议的用户名
        if self.username == "alice":
            suggestions = ["bob", "charlie"]
        elif self.username == "bob":
            suggestions = ["alice", "charlie"]
        elif self.username == "charlie":
            suggestions = ["alice", "bob"]
        else:
            suggestions = []
        
        username, ok = QInputDialog.getText(
            self,
            "添加好友",
            "请输入要添加的用户名:",
            text=suggestions[0] if suggestions else ""
        )
        
        if ok and username:
            self.run_async_task(self.async_add_friend(username))
    
    async def async_add_friend(self, friend_username):
        """异步添加好友"""
        try:
            if friend_username == self.username:
                self.show_message("提示", "不能添加自己为好友")
                return
            
            print(f"[添加好友] 添加: {friend_username}")
            
            url = f"{self.server_url}/add_friend"
            params = {
                "username": self.username,
                "friend_username": friend_username
            }
            
            async with self.http_session.post(url, params=params) as response:
                result = await response.json()
                
                if response.status == 200:
                    self.show_message("成功", f"已添加 {friend_username} 为好友")
                    # 重新加载好友列表
                    await self.load_friends()
                else:
                    error = result.get("detail", "添加失败")
                    self.show_message("错误", f"添加失败: {error}")
                    
        except Exception as e:
            print(f"[添加好友] 失败: {e}")
            self.show_message("错误", f"添加失败: {str(e)}")
    
    def refresh_friends(self):
        """刷新好友列表"""
        print("[刷新] 手动刷新好友列表")
        self.run_async_task(self.load_friends())
    
    def on_contact_selected(self, item):
        """选择联系人"""
        try:
            display_text = item.text()
            print(f"[选择] 点击了: {display_text}")
            
            # 跳过提示文本
            if "暂无好友" in display_text:
                return
            
            # 解析显示文本，获取昵称
            # 格式: 🟢 Bob 或 ⚫ Charlie
            parts = display_text.split(" ", 1)
            if len(parts) < 2:
                return
            
            nickname = parts[1].strip()
            
            # 通过昵称查找用户名
            selected_username = None
            for username, friend in self.friends.items():
                if friend["nickname"] == nickname:
                    selected_username = username
                    break
            
            if not selected_username:
                print(f"[选择] 错误: 找不到昵称为 {nickname} 的好友")
                return
            
            self.current_chat = selected_username
            friend = self.friends[selected_username]
            
            # 更新聊天标题
            self.chat_title.setText(f"与 {friend['nickname']} 聊天")
            
            # 清空消息区域
            self.message_display.clear()
            
            # 显示欢迎消息
            self.add_system_message(f"开始与 {friend['nickname']} 聊天")
            
            print(f"[选择] 已选择: {friend['nickname']} ({selected_username})")
            
        except Exception as e:
            print(f"[选择] 错误: {e}")
    
    def send_message(self):
        """发送消息"""
        if not self.current_chat:
            self.show_message("提示", "请先选择一个联系人")
            return
        
        message = self.input_field.text().strip()
        if not message:
            return
        
        print(f"[发送] 给 {self.current_chat}: {message}")
        
        # 清空输入框
        self.input_field.clear()
        
        # 本地显示
        self.add_message("我", message, is_self=True)
        
        # 发送
        if self.ws_client and self.ws_client.isRunning():
            data = {
                "type": "chat",
                "to": self.current_chat,
                "content": message
            }
            self.ws_client.send(data)
        else:
            print("[发送] 错误: WebSocket未连接")
    
    def add_message(self, sender, content, is_self=False):
        """添加消息"""
        timestamp = datetime.now().strftime("%H:%M")
        
        cursor = self.message_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # 时间戳
        self.message_display.setTextColor(QColor("#666"))
        self.message_display.insertPlainText(f"[{timestamp}] ")
        
        # 发送者
        if is_self:
            self.message_display.setTextColor(QColor("#007acc"))
            self.message_display.insertPlainText("我: ")
        else:
            self.message_display.setTextColor(QColor("#d32f2f"))
            self.message_display.insertPlainText(f"{sender}: ")
        
        # 内容
        self.message_display.setTextColor(QColor("#000"))
        self.message_display.insertPlainText(f"{content}\n")
        
        # 滚动到底部
        self.message_display.moveCursor(QTextCursor.End)
    
    def add_system_message(self, content):
        """添加系统消息"""
        timestamp = datetime.now().strftime("%H:%M")
        
        cursor = self.message_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        self.message_display.setTextColor(QColor("#666"))
        self.message_display.insertPlainText(f"[{timestamp}] 💡 {content}\n")
        self.message_display.moveCursor(QTextCursor.End)
    
    @pyqtSlot()
    def on_ws_connected(self):
        """WebSocket连接成功"""
        print("[WebSocket] 连接成功")
        self.statusBar().showMessage("已连接到服务器", 2000)
    
    @pyqtSlot()
    def on_ws_disconnected(self):
        """WebSocket断开连接"""
        print("[WebSocket] 断开连接")
        self.statusBar().showMessage("连接已断开", 2000)
    
    @pyqtSlot(dict)
    def on_ws_message(self, data):
        """处理WebSocket消息"""
        msg_type = data.get("type")
        
        if msg_type == "chat":
            sender = data.get("from")
            content = data.get("content")
            nickname = data.get("sender_nickname", sender)
            
            print(f"[消息] 来自 {sender}: {content}")
            
            # 如果是当前聊天对象
            if sender == self.current_chat:
                self.add_message(nickname, content, is_self=False)
            else:
                # 显示通知
                if sender in self.friends:
                    friend = self.friends[sender]
                    self.statusBar().showMessage(f"💬 {friend['nickname']}: {content[:30]}...", 3000)
        
        elif msg_type == "user_status":
            # 用户状态变化，刷新好友列表
            username = data.get("username")
            is_online = data.get("is_online")
            print(f"[状态] {username} -> {'在线' if is_online else '离线'}")
            self.refresh_friends()
    
    @pyqtSlot(str)
    def on_ws_error(self, error):
        """WebSocket错误"""
        print(f"[WebSocket] 错误: {error}")
        self.statusBar().showMessage(f"错误: {error[:30]}", 3000)
    
    def show_message(self, title, text):
        """显示消息框"""
        QTimer.singleShot(0, lambda: QMessageBox.information(self, title, text))
    
    def closeEvent(self, event):
        """关闭事件"""
        print("[关闭] 正在关闭客户端...")
        
        # 停止WebSocket
        if self.ws_client and self.ws_client.isRunning():
            self.ws_client.stop()
            self.ws_client.wait()
        
        # 停止事件循环
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        # 关闭HTTP会话
        if self.http_session:
            self.run_async_task(self.http_session.close())
        
        print("[关闭] 客户端已关闭")
        event.accept()

class SimpleLoginDialog(QDialog):
    """简单登录对话框"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("登录聊天")
        self.setFixedSize(300, 200)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("极简聊天")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title)
        
        # 表单
        form = QFormLayout()
        
        # 服务器
        self.server_input = QLineEdit("localhost:8000")
        form.addRow("服务器:", self.server_input)
        
        # 用户名
        self.username_input = QLineEdit()
        form.addRow("用户名:", self.username_input)
        
        # 密码
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        form.addRow("密码:", self.password_input)
        
        layout.addLayout(form)
        
        # 测试账号提示
        test_label = QLabel("测试账号: alice/123456, bob/123456")
        test_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(test_label)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
        # 设置默认值
        self.username_input.setText("alice")
        self.password_input.setText("123456")
    
    def login(self):
        """登录"""
        server = self.server_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not server or not username or not password:
            QMessageBox.warning(self, "错误", "请填写所有字段")
            return
        
        # 处理服务器地址
        if "://" not in server:
            server = "http://" + server
        
        self.server_url = server
        self.username = username
        
        print(f"[登录] 用户: {username}, 服务器: {server}")
        self.accept()

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 登录对话框
    dialog = SimpleLoginDialog()
    
    if dialog.exec_() == QDialog.Accepted:
        try:
            # 创建聊天窗口
            window = ChatWindow(dialog.server_url, dialog.username)
            window.show()
            
            sys.exit(app.exec_())
            
        except Exception as e:
            print(f"[错误] 创建窗口失败: {e}")
            QMessageBox.critical(None, "错误", f"启动失败: {str(e)}")
            sys.exit(1)
    else:
        print("[登录] 取消")
        sys.exit(0)

if __name__ == "__main__":
    main()