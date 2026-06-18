# 微信风格即时聊天应用

一个轻量级的即时聊天应用，模仿微信的基本功能，使用 HTML、CSS、JavaScript、Python（Flask）和 SQLite 实现。

## 功能特性

- **用户认证**：注册与登录（密码哈希存储）
- **联系人列表**：显示所有用户及其在线状态
- **实时聊天**：一对一消息发送与接收
- **自动刷新**：发送消息后双方页面自动刷新（轮询机制）
- **未读消息提示**：
  - 消息已读/未读状态
  - 未读消息计数
  - 实时更新已读状态
  - 视觉提示（红点、数字徽标）
- **响应式设计**：
  - 登录页面简洁美观
  - 手机版联系人列表 + 聊天界面
  - 输入框点击时上移，键盘跳出
- **其他功能**：
  - 消息时间戳
  - 发送状态指示
  - 用户在线状态显示

## 快速开始

### 1. 安装依赖

确保已安装 Python 3.7+。然后安装所需包：

```bash
pip install -r requirements.txt
```

### 2. 初始化数据库

首次运行会自动创建数据库和表。你也可以手动初始化：

```bash
python -c "from app import init_db; init_db()"
```

### 3. 启动服务器

```bash
python app.py
```

或者使用辅助脚本：

```bash
python start_server.py
```

服务器将在 `http://localhost:5000` 启动。

### 4. 访问应用

在浏览器中打开 `http://localhost:5000/login`。

### 5. 测试账号

- 用户名：`test`，密码：`test`
- 或者注册新用户

## 使用指南

### 登录/注册

1. 访问登录页面 (`/login`)
2. 输入用户名和密码
3. 点击“登录”或“注册”按钮

### 主界面（联系人列表）

登录后进入主界面，显示：
- 顶部：当前用户信息
- 中部：所有用户列表（在线用户显示绿色圆点）
- 每个联系人旁显示未读消息数（红点数字）

### 开始聊天

1. 点击任意联系人
2. 进入聊天界面，显示历史消息
3. 底部输入框输入消息，点击发送或按 Enter
4. 消息自动发送并出现在对方聊天窗口

### 未读消息处理

- 新消息到达时，联系人列表显示红点数字
- 进入聊天界面后，该联系人的未读消息自动标记为已读
- 已读消息显示为灰色，未读消息显示为蓝色

### 响应式布局

- **桌面**：左侧联系人列表，右侧聊天窗口
- **手机**：全屏联系人列表，点击后全屏聊天界面
- 手机输入框点击时自动上移，避免键盘遮挡

## 文件结构

```
web-chat-app/
├── app.py                 # Flask 主应用
├── start_server.py        # 服务器启动脚本
├── test_server.py         # 测试脚本
├── requirements.txt       # Python 依赖
├── chat.db               # SQLite 数据库
├── README.md             # 本文件
├── templates/
│   ├── login.html        # 登录页面
│   ├── index.html        # 主页面（联系人列表）
│   └── chat.html         # 聊天页面
└── static/
    ├── css/
    │   └── style.css     # 所有样式
    └── js/
        ├── login.js      # 登录页面逻辑
        └── app.js        # 主应用逻辑
```

## 技术细节

### 后端
- **框架**：Flask
- **数据库**：SQLite（`chat.db`）
- **API 端点**：
  - `POST /login` - 用户登录
  - `POST /register` - 用户注册
  - `GET /users` - 获取用户列表
  - `GET /messages/<recipient>` - 获取与特定用户的聊天记录
  - `POST /send` - 发送消息
  - `POST /mark_read` - 标记消息为已读

### 前端
- **HTML5**：语义化标签
- **CSS3**：Flexbox、Grid、媒体查询、CSS 变量
- **JavaScript**：原生 JS，使用 Fetch API 进行 AJAX 调用
- **轮询机制**：每 2 秒获取新消息

### 数据库模式
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    online BOOLEAN DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT 0,
    FOREIGN KEY (sender_id) REFERENCES users (id),
    FOREIGN KEY (recipient_id) REFERENCES users (id)
);
```

## 故障排除

### 端口占用
如果端口 5000 被占用，可以修改 `app.py` 中的端口号：
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)  # 改为 5001
```

### 数据库问题
删除 `chat.db` 文件并重启服务器以重新初始化。

### 样式未加载
确保静态文件路径正确，检查浏览器控制台是否有 404 错误。

## 扩展建议

1. **WebSocket 支持**：替换轮询为 WebSocket 实现真正实时通信
2. **群聊功能**：添加群组和群消息
3. **文件传输**：支持图片、文件上传
4. **消息加密**：端到端加密
5. **推送通知**：浏览器通知

## 许可证

MIT
