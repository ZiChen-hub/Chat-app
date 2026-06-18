// Main chat application JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // State
    let currentChat = null;
    let currentUserData = null;
    let contacts = [];
    let isMobile = window.innerWidth <= 768;
    
    // Initialize
    init();
    
    async function init() {
        // Check if user is logged in
        try {
            const response = await fetch('/api/user');
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }
            currentUserData = await response.json();
            
            // 检测设备类型
            isMobile = window.innerWidth <= 768;
            
            if (isMobile) {
                // 移动端初始化
                initMobile();
            } else {
                // 桌面端初始化
                initDesktop();
            }
            
        } catch (error) {
            console.error('Initialization error:', error);
            window.location.href = '/login';
        }
    }
    
    // ================= 移动端功能 =================
    function initMobile() {
        // 隐藏桌面版，显示移动版
        document.getElementById('desktopContainer').style.display = 'none';
        document.getElementById('appContainer').style.display = 'block';
        
        // 设置当前用户信息
        updateCurrentUserInfo();
        
        // 加载联系人
        loadContacts();
        
        // 设置事件监听
        setupMobileEvents();
        
        // 设置好友管理
        setupFriendManagement();
        
        // 加载好友请求
        loadFriendRequests();
        
        // 设置 SocketIO
        setupSocketIO();
    }
    
    function updateCurrentUserInfo() {
        if (currentUserData) {
            // 更新用户名
            const currentUserElement = document.getElementById('currentUser');
            if (currentUserElement) {
                currentUserElement.textContent = currentUserData.display_name || currentUserData.username;
            }
            
            // 更新用户头像（姓名圆圈）
            const currentUserAvatar = document.getElementById('currentUserAvatar');
            if (currentUserAvatar) {
                const firstLetter = currentUserData.display_name ? 
                    currentUserData.display_name.charAt(0).toUpperCase() : 
                    currentUserData.username.charAt(0).toUpperCase();
                currentUserAvatar.textContent = firstLetter;
                currentUserAvatar.className = `avatar name-circle color-${currentUserData.id % 6 + 1}`;
            }
        }
    }
    
    function setupMobileEvents() {
        // 返回联系人列表按钮
        const backToContactsBtn = document.getElementById('backToContacts');
        if (backToContactsBtn) {
            backToContactsBtn.addEventListener('click', () => {
                showContactsView();
            });
        }
        
        // 移动端添加好友按钮
        const addFriendMobileBtn = document.getElementById('addFriendMobileBtn');
        if (addFriendMobileBtn) {
            addFriendMobileBtn.addEventListener('click', () => {
                const addFriendModal = document.getElementById('addFriendModal');
                if (addFriendModal) {
                    addFriendModal.style.display = 'block';
                    const friendUsernameInput = document.getElementById('friendUsername');
                    if (friendUsernameInput) friendUsernameInput.focus();
                }
            });
        }
        
        // 发送消息按钮
        const sendBtn = document.getElementById('sendBtn');
        const messageInput = document.getElementById('messageInput');
        
        if (sendBtn) {
            sendBtn.addEventListener('click', sendMessage);
        }
        
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
            
            // 移动端输入框优化
            messageInput.addEventListener('focus', () => {
                // 确保输入框可见
                setTimeout(() => {
                    const chatMessages = document.getElementById('chatMessages');
                    if (chatMessages) {
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                }, 300);
            });
        }
        
        // 搜索框
        const searchInput = document.getElementById('searchContacts');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const searchTerm = e.target.value.toLowerCase();
                filterContacts(searchTerm);
            });
        }
        
        // 移动端导航
        setupMobileNavigation();
    }
    
    function setupMobileNavigation() {
        const navChats = document.getElementById('navChats');
        const navRequests = document.getElementById('navRequests');
        const navSearch = document.getElementById('navSearch');
        const navLogout = document.getElementById('navLogout');
        
        if (navChats) {
            navChats.addEventListener('click', (e) => {
                e.preventDefault();
                showContactsView();
                setActiveNav('navChats');
            });
        }
        
        if (navRequests) {
            navRequests.addEventListener('click', (e) => {
                e.preventDefault();
                const friendRequestsModal = document.getElementById('friendRequestsModal');
                if (friendRequestsModal) {
                    friendRequestsModal.style.display = 'block';
                    loadFriendRequests();
                }
                setActiveNav('navRequests');
            });
        }
        
        if (navSearch) {
            navSearch.addEventListener('click', (e) => {
                e.preventDefault();
                const searchInput = document.getElementById('searchContacts');
                if (searchInput) {
                    searchInput.focus();
                }
                setActiveNav('navSearch');
            });
        }
        
        if (navLogout) {
            navLogout.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.href = '/logout';
            });
        }
    }
    
    function showContactsView() {
        const contactsView = document.getElementById('contactsView');
        const chatView = document.getElementById('chatView');
        
        if (contactsView && chatView) {
            contactsView.style.display = 'flex';
            chatView.style.display = 'none';
            
            // 重置当前聊天
            currentChat = null;
            
            // 重新加载联系人（更新未读计数）
            loadContacts();
        }
    }
    
    function showChatView(contactId, contactName, isOnline) {
        const contactsView = document.getElementById('contactsView');
        const chatView = document.getElementById('chatView');
        
        if (contactsView && chatView) {
            contactsView.style.display = 'none';
            chatView.style.display = 'flex';
            
            currentChat = contactId;
            
            // 更新聊天头部信息
            updateChatHeader(contactId, contactName, isOnline);
            
            // 加载消息
            loadMessages(contactId);
            
            // 启用输入框
            const messageInput = document.getElementById('messageInput');
            const sendBtn = document.getElementById('sendBtn');
            if (messageInput) messageInput.disabled = false;
            if (sendBtn) sendBtn.disabled = false;
            
            // 聚焦输入框
            setTimeout(() => {
                if (messageInput) messageInput.focus();
            }, 300);
        }
    }
    
    function updateChatHeader(contactId, contactName, isOnline) {
        // 更新聊天伙伴名字
        const chatPartnerName = document.getElementById('chatPartnerName');
        if (chatPartnerName) {
            chatPartnerName.textContent = contactName;
        }
        
        // 更新状态
        const chatPartnerStatus = document.getElementById('chatPartnerStatus');
        if (chatPartnerStatus) {
            chatPartnerStatus.textContent = isOnline ? 'Online' : 'Offline';
            chatPartnerStatus.className = `status ${isOnline ? 'online' : 'offline'}`;
        }
        
        // 更新头像（姓名圆圈）
        const chatPartnerAvatar = document.getElementById('chatPartnerAvatar');
        if (chatPartnerAvatar) {
            const firstLetter = contactName ? contactName.charAt(0).toUpperCase() : '?';
            chatPartnerAvatar.textContent = firstLetter;
            chatPartnerAvatar.className = `chat-avatar name-circle color-${contactId % 6 + 1}`;
        }
    }
    
    function setActiveNav(activeId) {
        document.querySelectorAll('.nav-item').forEach(nav => {
            nav.classList.remove('active');
        });
        const activeNav = document.getElementById(activeId);
        if (activeNav) activeNav.classList.add('active');
    }
    
    // ================= 桌面端功能 =================
    function initDesktop() {
        // 隐藏移动版，显示桌面版
        document.getElementById('appContainer').style.display = 'none';
        document.getElementById('desktopContainer').style.display = 'flex';
        
        // 设置当前用户信息（桌面端）
        updateCurrentUserInfoDesktop();
        
        // 加载联系人
        loadContactsDesktop();
        
        // 设置事件监听
        setupDesktopEvents();
        
        // 设置好友管理
        setupFriendManagement();
        
        // 加载好友请求
        loadFriendRequests();
        
        // 设置 SocketIO
        setupSocketIO();
    }
    
    function updateCurrentUserInfoDesktop() {
        if (currentUserData) {
            // 更新用户名
            const currentUserElement = document.getElementById('currentUserDesktop');
            if (currentUserElement) {
                currentUserElement.textContent = currentUserData.display_name || currentUserData.username;
            }
            
            // 更新用户头像（姓名圆圈）
            const currentUserAvatar = document.getElementById('currentUserAvatarDesktop');
            if (currentUserAvatar) {
                const firstLetter = currentUserData.display_name ? 
                    currentUserData.display_name.charAt(0).toUpperCase() : 
                    currentUserData.username.charAt(0).toUpperCase();
                currentUserAvatar.textContent = firstLetter;
                currentUserAvatar.className = `avatar name-circle color-${currentUserData.id % 6 + 1}`;
            }
        }
    }
    
    function setupDesktopEvents() {
        // 发送消息按钮
        const sendBtn = document.getElementById('sendBtnDesktop');
        const messageInput = document.getElementById('messageInputDesktop');
        
        if (sendBtn) {
            sendBtn.addEventListener('click', sendMessageDesktop);
        }
        
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessageDesktop();
                }
            });
        }
        
        // 搜索框
        const searchInput = document.getElementById('searchContactsDesktop');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const searchTerm = e.target.value.toLowerCase();
                filterContactsDesktop(searchTerm);
            });
        }
        
        // 登出按钮
        const logoutBtn = document.getElementById('logoutBtnDesktop');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.href = '/logout';
            });
        }
    }
    
    function openChatDesktop(contactId, contactName, isOnline) {
        currentChat = contactId;
        
        // 更新聊天头部
        const chatPartnerName = document.getElementById('chatPartnerNameDesktop');
        const chatPartnerStatus = document.getElementById('chatPartnerStatusDesktop');
        const chatPartnerAvatar = document.getElementById('chatPartnerAvatarDesktop');
        
        if (chatPartnerName) chatPartnerName.textContent = contactName;
        if (chatPartnerStatus) {
            chatPartnerStatus.textContent = isOnline ? 'Online' : 'Offline';
            chatPartnerStatus.className = `status ${isOnline ? 'online' : 'offline'}`;
        }
        
        if (chatPartnerAvatar) {
            const firstLetter = contactName ? contactName.charAt(0).toUpperCase() : '?';
            chatPartnerAvatar.textContent = firstLetter;
            chatPartnerAvatar.className = `chat-avatar name-circle color-${contactId % 6 + 1}`;
        }
        
        // 显示聊天界面
        const welcomeScreen = document.getElementById('welcomeScreenDesktop');
        const chatMessages = document.getElementById('chatMessagesDesktop');
        const messageInputContainer = document.getElementById('messageInputContainerDesktop');
        const messageInput = document.getElementById('messageInputDesktop');
        const sendBtn = document.getElementById('sendBtnDesktop');
        
        if (welcomeScreen) welcomeScreen.style.display = 'none';
        if (chatMessages) chatMessages.style.display = 'flex';
        if (messageInputContainer) messageInputContainer.style.display = 'flex';
        if (messageInput) messageInput.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        
        // 加载消息
        loadMessagesDesktop(contactId);
        
        // 聚焦输入框
        setTimeout(() => {
            if (messageInput) messageInput.focus();
        }, 100);
    }
    
    async function sendMessageDesktop() {
        const messageInput = document.getElementById('messageInputDesktop');
        const text = messageInput ? messageInput.value.trim() : '';
        
        if (!text || !currentChat || !currentUserData) return;
        
        try {
            const response = await fetch('/api/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    receiver_id: currentChat,
                    content: text
                })
            });
            
            if (response.ok) {
                // 清空输入框
                if (messageInput) messageInput.value = '';
                
                // 重新加载消息
                await loadMessagesDesktop(currentChat);
                
                // 重新加载联系人（更新最后一条消息）
                await loadContactsDesktop();
            } else {
                const errorData = await response.json();
                showAlert('Failed to send: ' + (errorData.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            showAlert('Network error', 'error');
        }
    }
    
    async function loadMessagesDesktop(contactId) {
        try {
            const response = await fetch(`/api/messages/${contactId}`);
            if (response.ok) {
                const messages = await response.json();
                renderMessagesDesktop(messages);
            }
        } catch (error) {
            console.error('Error loading messages:', error);
            showAlert('Failed to load messages', 'error');
        }
    }
    
    function renderMessagesDesktop(messages) {
        const chatMessages = document.getElementById('chatMessagesDesktop');
        if (!chatMessages) return;
        
        chatMessages.innerHTML = '';
        
        if (messages.length === 0) {
            chatMessages.innerHTML = `
                <div class="text-center" style="margin: auto; color: #777;">
                    <i class="fas fa-comments" style="font-size: 50px; margin-bottom: 15px;"></i>
                    <p>No messages yet. Start the conversation!</p>
                </div>
            `;
            return;
        }
        
        messages.forEach(msg => {
            const messageDiv = document.createElement('div');
            const isSent = msg.sender_id === currentUserData.id;
            messageDiv.className = `message ${isSent ? 'sent' : 'received'}`;
            
            messageDiv.innerHTML = `
                <div class="message-bubble">${msg.content}</div>
                <div class="message-time">
                    ${formatTime(msg.timestamp)}
                    ${isSent ? 
                        `<span class="message-status ${msg.read ? 'read' : ''}">
                            <i class="fas fa-check${msg.read ? '-double' : ''}"></i>
                        </span>` : 
                        ''
                    }
                </div>
            `;
            
            chatMessages.appendChild(messageDiv);
        });
        
        // 滚动到底部
        setTimeout(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 100);
    }
    
    function filterContactsDesktop(searchTerm) {
        const filteredContacts = contacts.filter(contact => {
            const name = (contact.display_name || contact.username).toLowerCase();
            return name.includes(searchTerm);
        });
        renderContactsDesktop(filteredContacts);
    }
    
    // ================= 通用功能 =================
    
    async function loadContacts() {
        try {
            const response = await fetch('/api/contacts');
            if (response.ok) {
                contacts = await response.json();
                if (isMobile) {
                    renderContacts(contacts);
                } else {
                    renderContactsDesktop(contacts);
                }
            }
        } catch (error) {
            console.error('Error loading contacts:', error);
        }
    }
    
    function renderContacts(contactsToRender = contacts) {
        const contactsList = document.getElementById('contactsList');
        if (!contactsList) return;
        
        contactsList.innerHTML = '';
        
        if (contactsToRender.length === 0) {
            contactsList.innerHTML = `
                <div class="text-center" style="padding: 30px; color: #777;">
                    <i class="fas fa-user-friends" style="font-size: 40px; margin-bottom: 15px;"></i>
                    <p>No contacts yet</p>
                    <small>Add friends to start chatting</small>
                </div>
            `;
            return;
        }
        
        contactsToRender.forEach(contact => {
            const contactItem = document.createElement('div');
            contactItem.className = 'contact-item-mobile';
            
            // 获取姓名首字母
            const firstLetter = contact.display_name ? contact.display_name.charAt(0).toUpperCase() : '?';
            
            contactItem.innerHTML = `
                <div class="name-circle color-${contact.id % 6 + 1}">${firstLetter}</div>
                <div style="flex: 1;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <strong>${contact.display_name || contact.username}</strong>
                        <small style="color: #999;">${contact.last_message_time ? formatTime(contact.last_message_time) : ''}</small>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <small style="color: #777; max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            ${contact.last_message || 'No messages yet'}
                        </small>
                        ${contact.unread_count > 0 ? 
                            `<span class="unread-count">${contact.unread_count}</span>` : 
                            contact.online ? '<span style="width: 8px; height: 8px; background: #2ecc71; border-radius: 50%;"></span>' : ''
                        }
                    </div>
                </div>
            `;
            
            contactItem.addEventListener('click', () => {
                showChatView(contact.id, contact.display_name || contact.username, contact.online);
            });
            
            contactsList.appendChild(contactItem);
        });
    }
    
    function renderContactsDesktop(contactsToRender = contacts) {
        const contactsList = document.getElementById('contactsListDesktop');
        if (!contactsList) return;
        
        contactsList.innerHTML = '';
        
        if (contactsToRender.length === 0) {
            contactsList.innerHTML = `
                <div class="text-center" style="padding: 30px; color: #777;">
                    <i class="fas fa-user-friends" style="font-size: 40px; margin-bottom: 15px;"></i>
                    <p>No contacts yet</p>
                    <small>Add friends to start chatting</small>
                </div>
            `;
            return;
        }
        
        contactsToRender.forEach(contact => {
            const contactItem = document.createElement('div');
            contactItem.className = 'contact-item-desktop';
            if (currentChat === contact.id) {
                contactItem.classList.add('active');
            }
            
            // 获取姓名首字母
            const firstLetter = contact.display_name ? contact.display_name.charAt(0).toUpperCase() : '?';
            
            contactItem.innerHTML = `
                <div class="name-circle color-${contact.id % 6 + 1}">${firstLetter}</div>
                <div class="contact-info">
                    <div class="contact-name">
                        <span>${contact.display_name || contact.username}</span>
                        <span class="contact-meta">${contact.last_message_time ? formatTime(contact.last_message_time) : ''}</span>
                    </div>
                    <div class="contact-last-msg">
                        ${contact.last_message || 'No messages yet'}
                        ${contact.unread_count > 0 ? `<span class="unread-count">${contact.unread_count}</span>` : ''}
                        ${contact.online ? '<span class="unread-indicator" style="background-color: #2ecc71;"></span>' : ''}
                    </div>
                </div>
            `;
            
            contactItem.addEventListener('click', () => {
                openChatDesktop(contact.id, contact.display_name || contact.username, contact.online);
            });
            
            contactsList.appendChild(contactItem);
        });
    }
    
    function filterContacts(searchTerm) {
        const filteredContacts = contacts.filter(contact => {
            const name = (contact.display_name || contact.username).toLowerCase();
            return name.includes(searchTerm);
        });
        renderContacts(filteredContacts);
    }
    
    async function loadMessages(contactId) {
        try {
            const response = await fetch(`/api/messages/${contactId}`);
            if (response.ok) {
                const messages = await response.json();
                if (isMobile) {
                    renderMessagesMobile(messages);
                } else {
                    renderMessagesDesktop(messages);
                }
            }
        } catch (error) {
            console.error('Error loading messages:', error);
            showAlert('Failed to load messages', 'error');
        }
    }
    
    function renderMessagesMobile(messages) {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) return;
        
        chatMessages.innerHTML = '';
        
        if (messages.length === 0) {
            chatMessages.innerHTML = `
                <div class="text-center" style="margin: auto; color: #777; padding: 40px;">
                    <i class="fas fa-comments" style="font-size: 50px; margin-bottom: 15px;"></i>
                    <p>No messages yet</p>
                    <p>Start the conversation!</p>
                </div>
            `;
            return;
        }
        
        messages.forEach(msg => {
            const messageDiv = document.createElement('div');
            const isSent = msg.sender_id === currentUserData.id;
            messageDiv.className = `message-mobile ${isSent ? 'sent' : 'received'}`;
            
            messageDiv.innerHTML = `
                <div class="message-bubble-mobile">${msg.content}</div>
                <div class="message-time-mobile">
                    ${formatTime(msg.timestamp)}
                    ${isSent ? 
                        `<span class="message-status ${msg.read ? 'read' : ''}">
                            <i class="fas fa-check${msg.read ? '-double' : ''}" style="font-size: 10px;"></i>
                        </span>` : 
                        ''
                    }
                </div>
            `;
            
            chatMessages.appendChild(messageDiv);
        });
        
        // 滚动到底部
        setTimeout(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 100);
    }
    
    async function sendMessage() {
        const messageInput = isMobile ? 
            document.getElementById('messageInput') : 
            document.getElementById('messageInputDesktop');
        const text = messageInput ? messageInput.value.trim() : '';
        
        if (!text || !currentChat || !currentUserData) return;
        
        try {
            const response = await fetch('/api/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    receiver_id: currentChat,
                    content: text
                })
            });
            
            if (response.ok) {
                // 清空输入框
                if (messageInput) messageInput.value = '';
                
                // 重新加载消息
                await loadMessages(currentChat);
                
                // 重新加载联系人（更新最后一条消息）
                await loadContacts();
            } else {
                const errorData = await response.json();
                showAlert('Failed to send: ' + (errorData.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            showAlert('Network error', 'error');
        }
    }
    
    function setupFriendManagement() {
        // 添加好友按钮
        const addFriendBtn = isMobile ? 
            null : document.getElementById('addFriendBtnDesktop');
        const friendRequestsBtn = isMobile ? 
            null : document.getElementById('friendRequestsBtnDesktop');
        const addFriendModal = document.getElementById('addFriendModal');
        const friendRequestsModal = document.getElementById('friendRequestsModal');
        const sendFriendRequestBtn = document.getElementById('sendFriendRequest');
        const friendUsernameInput = document.getElementById('friendUsername');
        
        if (addFriendBtn) {
            addFriendBtn.addEventListener('click', () => {
                if (addFriendModal) {
                    addFriendModal.style.display = 'block';
                    if (friendUsernameInput) friendUsernameInput.focus();
                }
            });
        }
        
        if (friendRequestsBtn) {
            friendRequestsBtn.addEventListener('click', () => {
                if (friendRequestsModal) {
                    friendRequestsModal.style.display = 'block';
                    loadFriendRequests();
                }
            });
        }
        
        // 关闭模态框按钮
        document.querySelectorAll('.modal-close').forEach(closeBtn => {
            closeBtn.addEventListener('click', function() {
                this.closest('.modal').style.display = 'none';
            });
        });
        
        // 点击模态框外部关闭
        window.addEventListener('click', function(event) {
            if (event.target.classList.contains('modal')) {
                event.target.style.display = 'none';
            }
        });
        
        // 发送好友请求
        if (sendFriendRequestBtn) {
            sendFriendRequestBtn.addEventListener('click', sendFriendRequest);
        }
        
        if (friendUsernameInput) {
            friendUsernameInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    sendFriendRequest();
                }
            });
        }
    }
    
    async function sendFriendRequest() {
        const usernameInput = document.getElementById('friendUsername');
        const resultDiv = document.getElementById('friendRequestResult');
        
        if (!usernameInput || !resultDiv) return;
        
        const username = usernameInput.value.trim();
        
        if (!username) {
            resultDiv.innerHTML = '<div class="alert error">Please enter a username</div>';
            return;
        }
        
        try {
            const response = await fetch('/api/friends/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username: username })
            });
            
            const data = await response.json();
            
            if (data.success) {
                resultDiv.innerHTML = '<div class="alert success">Friend request sent!</div>';
                usernameInput.value = '';
                // 重新加载好友请求
                loadFriendRequests();
                // 2秒后关闭模态框
                setTimeout(() => {
                    const modal = document.getElementById('addFriendModal');
                    if (modal) modal.style.display = 'none';
                }, 2000);
            } else {
                resultDiv.innerHTML = `<div class="alert error">${data.error}</div>`;
            }
        } catch (error) {
            console.error('Error sending friend request:', error);
            resultDiv.innerHTML = '<div class="alert error">Network error</div>';
        }
    }
    
    async function loadFriendRequests() {
        try {
            const response = await fetch('/api/friends');
            const data = await response.json();
            
            // 更新请求数量
            const requestCount = data.pending.length;
            
            // 移动端
            const badgeMobile = document.getElementById('friendRequestCountMobile');
            if (badgeMobile) {
                if (requestCount > 0) {
                    badgeMobile.textContent = requestCount;
                    badgeMobile.style.display = 'inline-block';
                } else {
                    badgeMobile.style.display = 'none';
                }
            }
            
            // 桌面端
            const badgeDesktop = document.getElementById('friendRequestCountDesktop');
            if (badgeDesktop) {
                if (requestCount > 0) {
                    badgeDesktop.textContent = requestCount;
                    badgeDesktop.style.display = 'inline-block';
                } else {
                    badgeDesktop.style.display = 'none';
                }
            }
            
            // 渲染待处理请求
            const requestsList = document.getElementById('requestsList');
            const sentRequestsList = document.getElementById('sentRequestsList');
            
            if (requestsList) {
                if (data.pending.length === 0) {
                    requestsList.innerHTML = '<p class="text-muted">No pending requests</p>';
                } else {
                    requestsList.innerHTML = data.pending.map(request => `
                        <div class="friend-request">
                            <div class="friend-request-info">
                                <div class="name-circle color-${request.user_id % 6 + 1}">
                                    ${request.display_name ? request.display_name.charAt(0) : '?'}
                                </div>
                                <div>
                                    <strong>${request.display_name || request.username}</strong><br>
                                    <small>@${request.username}</small>
                                </div>
                            </div>
                            <div class="friend-request-actions">
                                <button class="accept-btn" onclick="window.acceptFriendRequest(${request.id})">
                                    Accept
                                </button>
                                <button class="reject-btn" onclick="window.rejectFriendRequest(${request.id})">
                                    Reject
                                </button>
                            </div>
                        </div>
                    `).join('');
                }
            }
            
            if (sentRequestsList) {
                if (data.sent.length === 0) {
                    sentRequestsList.innerHTML = '<p class="text-muted">No sent requests</p>';
                } else {
                    sentRequestsList.innerHTML = data.sent.map(request => `
                        <div class="friend-request">
                            <div class="friend-request-info">
                                <div class="name-circle color-${request.friend_id % 6 + 1}">
                                    ${request.display_name ? request.display_name.charAt(0) : '?'}
                                </div>
                                <div>
                                    <strong>${request.display_name || request.username}</strong><br>
                                    <small>@${request.username} - Pending</small>
                                </div>
                            </div>
                        </div>
                    `).join('');
                }
            }
            
        } catch (error) {
            console.error('Error loading friend requests:', error);
        }
    }
    
    // 全局函数供好友请求按钮使用
    window.acceptFriendRequest = async function(requestId) {
        try {
            const response = await fetch(`/api/friends/${requestId}/accept`, {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.success) {
                // 重新加载好友请求和联系人
                loadFriendRequests();
                loadContacts();
                showAlert('Friend request accepted!', 'success');
                
                // 关闭模态框
                const modal = document.getElementById('friendRequestsModal');
                if (modal) modal.style.display = 'none';
            } else {
                showAlert('Error: ' + data.error, 'error');
            }
        } catch (error) {
            console.error('Error accepting friend request:', error);
            showAlert('Network error', 'error');
        }
    };
    
    window.rejectFriendRequest = async function(requestId) {
        try {
            const response = await fetch(`/api/friends/${requestId}/reject`, {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.success) {
                // 重新加载好友请求
                loadFriendRequests();
                showAlert('Friend request rejected', 'success');
            } else {
                showAlert('Error: ' + data.error, 'error');
            }
        } catch (error) {
            console.error('Error rejecting friend request:', error);
            showAlert('Network error', 'error');
        }
    };
    
    function setupSocketIO() {
        // 监听新消息
        socketio.on('new_message', (message) => {
            if (currentChat && (message.sender_id === currentChat || message.receiver_id === currentChat)) {
                // 如果这条消息是当前聊天的，重新加载消息
                if (isMobile) {
                    loadMessages(currentChat);
                } else {
                    loadMessagesDesktop(currentChat);
                }
            }
            
            // 重新加载联系人以更新未读计数
            loadContacts();
        });
        
        // 监听用户状态变化
        socketio.on('status', (data) => {
            // 更新联系人状态
            loadContacts();
        });
        
        // 监听好友请求
        socketio.on('friend_request', (data) => {
            // 重新加载好友请求
            loadFriendRequests();
        });
        
        // 监听好友请求接受
        socketio.on('friend_accepted', (data) => {
            // 重新加载好友请求和联系人
            loadFriendRequests();
            loadContacts();
        });
        
        // 监听打字指示
        socketio.on('typing', (data) => {
            if (data.sender_id === currentChat) {
                // 显示打字指示
                const statusElement = isMobile ? 
                    document.getElementById('chatPartnerStatus') : 
                    document.getElementById('chatPartnerStatusDesktop');
                if (statusElement) {
                    statusElement.textContent = 'Typing...';
                }
            }
        });
        
        socketio.on('stop_typing', (data) => {
            if (data.sender_id === currentChat) {
                // 恢复状态
                const contact = contacts.find(c => c.id === currentChat);
                const statusElement = isMobile ? 
                    document.getElementById('chatPartnerStatus') : 
                    document.getElementById('chatPartnerStatusDesktop');
                if (statusElement && contact) {
                    statusElement.textContent = contact.online ? 'Online' : 'Offline';
                }
            }
        });
    }
    
    function formatTime(timestamp) {
        if (!timestamp) return '';
        
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        // 如果是今天
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        
        // 如果是昨天
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.toDateString() === yesterday.toDateString()) {
            return 'Yesterday';
        }
        
        // 如果在一周内
        if (diff < 7 * 24 * 60 * 60 * 1000) {
            return date.toLocaleDateString([], { weekday: 'short' });
        }
        
        // 更早的日期
        return date.toLocaleDateString();
    }
    
    function showAlert(message, type) {
        // 移除现有的警告
        const existingAlert = document.querySelector('.app-alert');
        if (existingAlert) {
            existingAlert.remove();
        }
        
        const alert = document.createElement('div');
        alert.className = `app-alert alert-${type}`;
        alert.textContent = message;
        
        // 添加样式
        alert.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 2000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideDown 0.3s ease;
        `;
        
        if (type === 'error') {
            alert.style.background = 'linear-gradient(to right, #ff4757, #ff3838)';
        } else if (type === 'success') {
            alert.style.background = 'linear-gradient(to right, #2ecc71, #27ae60)';
        } else {
            alert.style.background = 'linear-gradient(to right, #3498db, #2980b9)';
        }
        
        document.body.appendChild(alert);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (alert.parentNode) {
                alert.style.animation = 'slideUp 0.3s ease';
                setTimeout(() => alert.remove(), 300);
            }
        }, 3000);
        
        // 添加动画CSS
        if (!document.querySelector('#alert-animations')) {
            const style = document.createElement('style');
            style.id = 'alert-animations';
            style.textContent = `
                @keyframes slideDown {
                    from { transform: translate(-50%, -100%); opacity: 0; }
                    to { transform: translate(-50%, 0); opacity: 1; }
                }
                @keyframes slideUp {
                    from { transform: translate(-50%, 0); opacity: 1; }
                    to { transform: translate(-50%, -100%); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    // 窗口大小改变时重新检测设备
    window.addEventListener('resize', () => {
        const wasMobile = isMobile;
        isMobile = window.innerWidth <= 768;
        
        // 如果设备类型改变，重新加载页面
        if (wasMobile !== isMobile) {
            location.reload();
        }
    });
    
    // 自动刷新消息和联系人
    setInterval(() => {
        if (currentChat) {
            if (isMobile) {
                loadMessages(currentChat);
            } else {
                loadMessagesDesktop(currentChat);
            }
        }
        loadContacts();
        loadFriendRequests();
    }, 5000);
    
    // SocketIO 连接时加载好友请求
    socketio.on('connect', () => {
        loadFriendRequests();
    });
});