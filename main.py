from flask import Flask, request, jsonify, session, render_template_string
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
import os
import uuid
import logging
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gizli-anahtar-2024')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    transport=['websocket', 'polling']
)

active_users = {}

MONGODB_URI = os.environ.get(
    'MONGODB_URI',
    'mongodb+srv://Eymen:Eymen6969@cluster0.vqwhlrj.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
)

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    logger.info('✅ MongoDB bağlantısı başarılı!')
    
    db = client.chat_db
    messages_collection = db.messages
    rooms_collection = db.rooms
    users_collection = db.users
    
    messages_collection.create_index([("room", ASCENDING), ("timestamp", DESCENDING)])
    rooms_collection.create_index([("name", ASCENDING)], unique=True)
    users_collection.create_index([("username", ASCENDING)], unique=True)
    users_collection.create_index([("email", ASCENDING)], unique=True)
    
    logger.info('✅ Index\'ler oluşturuldu')
    
except Exception as e:
    logger.error(f'❌ MongoDB bağlantı hatası: {e}')
    exit(1)

def init_db():
    default_rooms = ['Genel', 'Teknoloji', 'Spor', 'Müzik', 'Oyun']
    for room_name in default_rooms:
        try:
            rooms_collection.insert_one({'name': room_name, 'created_at': datetime.now()})
            logger.info(f'✅ Oda oluşturuldu: {room_name}')
        except:
            pass

init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grup Sohbet</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .main-container {
            width: 100%;
            max-width: 1200px;
            height: 90vh;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            display: none;
            overflow: hidden;
        }
        .main-container.active {
            display: flex;
        }
        .sidebar {
            width: 280px;
            background: #2c3e50;
            display: flex;
            flex-direction: column;
        }
        .sidebar-header {
            padding: 25px 20px;
            background: #1a252f;
            color: white;
            border-bottom: 2px solid #34495e;
        }
        .sidebar-header h2 {
            font-size: 20px;
            margin-bottom: 8px;
        }
        .user-info {
            font-size: 13px;
            opacity: 0.8;
            color: #ecf0f1;
            word-break: break-all;
        }
        .user-id-display {
            font-size: 11px;
            color: #95a5a6;
            margin-top: 5px;
            font-family: monospace;
            background: #34495e;
            padding: 5px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .user-id-display:hover {
            background: #667eea;
            color: white;
        }
        .profile-btn {
            margin-top: 10px;
            padding: 8px 12px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
            width: 100%;
        }
        .profile-btn:hover {
            background: #764ba2;
        }
        .rooms-list {
            flex: 1;
            overflow-y: auto;
            padding: 15px 10px;
        }
        .room-item {
            padding: 15px;
            margin-bottom: 8px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 12px;
            color: #ecf0f1;
        }
        .room-item:hover {
            background: #34495e;
            transform: translateX(5px);
        }
        .room-item.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
        }
        .room-item.private {
            border-left: 3px solid #f39c12;
        }
        .room-icon {
            font-size: 22px;
        }
        .room-name {
            flex: 1;
            font-size: 15px;
        }
        .new-room-section {
            padding: 15px;
            background: #1a252f;
            border-top: 2px solid #34495e;
        }
        .new-room-input, .private-room-input {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
            background: #34495e;
            color: white;
        }
        .new-room-input::placeholder, .private-room-input::placeholder {
            color: #95a5a6;
        }
        .new-room-btn {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.2s;
            font-size: 14px;
            margin-bottom: 8px;
        }
        .new-room-btn:hover {
            transform: scale(1.02);
        }
        .private-btn {
            width: 100%;
            padding: 10px;
            background: #f39c12;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            font-size: 12px;
            transition: transform 0.2s;
        }
        .private-btn:hover {
            transform: scale(1.02);
        }
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .chat-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 25px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .chat-header h2 {
            font-size: 24px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .logout-btn {
            padding: 10px 20px;
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.2s;
        }
        .logout-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        .messages {
            flex: 1;
            padding: 25px;
            overflow-y: auto;
            background: #ecf0f1;
        }
        .message {
            margin-bottom: 20px;
            animation: slideIn 0.3s ease;
            display: flex;
            flex-direction: column;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message-content {
            background: white;
            padding: 14px 18px;
            border-radius: 18px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            max-width: 65%;
            word-wrap: break-word;
        }
        .message.own {
            align-items: flex-end;
        }
        .message.own .message-content {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .username {
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 6px;
            color: #667eea;
        }
        .message.own .username {
            color: white;
        }
        .message-text {
            font-size: 15px;
            line-height: 1.5;
            margin-bottom: 6px;
        }
        .timestamp {
            font-size: 11px;
            color: #7f8c8d;
            font-weight: 500;
        }
        .message.own .timestamp {
            color: rgba(255,255,255,0.8);
        }
        .input-area {
            padding: 20px 25px;
            background: white;
            border-top: 2px solid #e0e0e0;
            display: flex;
            gap: 12px;
        }
        input.message-input {
            flex: 1;
            padding: 14px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 25px;
            font-size: 15px;
            outline: none;
            transition: border 0.3s;
        }
        input.message-input:focus { 
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102,126,234,0.1);
        }
        button.send-btn {
            padding: 14px 35px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.2s;
            font-size: 15px;
        }
        button.send-btn:hover { 
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(102,126,234,0.4);
        }
        button.send-btn:active { transform: scale(0.95); }
        
        .auth-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.85);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .auth-modal.hidden {
            display: none;
        }
        .auth-box {
            background: white;
            padding: 45px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            min-width: 400px;
            max-width: 450px;
        }
        .auth-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .auth-header h2 {
            color: #667eea;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .auth-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            background: #f0f0f0;
            padding: 5px;
            border-radius: 10px;
        }
        .auth-tab {
            flex: 1;
            padding: 12px;
            background: transparent;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
            color: #666;
        }
        .auth-tab.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .auth-form {
            display: none;
        }
        .auth-form.active {
            display: block;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
            font-size: 14px;
        }
        .form-input {
            width: 100%;
            padding: 14px 18px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 15px;
            outline: none;
            transition: border 0.3s;
        }
        .form-input:focus {
            border-color: #667eea;
        }
        .auth-btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-weight: bold;
            font-size: 16px;
            transition: transform 0.2s;
        }
        .auth-btn:hover {
            transform: scale(1.02);
        }
        .error-message {
            background: #fee;
            color: #c33;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 14px;
            display: none;
        }
        .success-message {
            background: #efe;
            color: #3c3;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 14px;
            display: none;
        }
        
        .profile-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.85);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .profile-modal.active {
            display: flex;
        }
        .profile-box {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            min-width: 450px;
            max-width: 500px;
        }
        .profile-header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        .profile-avatar {
            width: 100px;
            height: 100px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            color: white;
            margin: 0 auto 15px;
        }
        .profile-info {
            margin-bottom: 30px;
        }
        .profile-field {
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        .profile-field label {
            display: block;
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
            font-weight: 600;
        }
        .profile-field-value {
            font-size: 16px;
            color: #333;
            font-weight: 500;
        }
        .profile-actions {
            display: flex;
            gap: 10px;
        }
        .profile-close-btn {
            flex: 1;
            padding: 12px;
            background: #e0e0e0;
            color: #333;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.2s;
        }
        .profile-close-btn:hover {
            background: #d0d0d0;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
        }
        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 15px;
        }
        @media (max-width: 768px) {
            .sidebar { width: 220px; }
            .main-container { height: 95vh; }
            .auth-box, .profile-box { min-width: 90%; }
        }
    </style>
</head>
<body>
    <div class="auth-modal" id="authModal">
        <div class="auth-box">
            <div class="auth-header">
                <h2>💬 Grup Sohbet</h2>
                <p style="color: #666; font-size: 14px;">Hesabınızla giriş yapın veya yeni hesap oluşturun</p>
            </div>
            
            <div class="auth-tabs">
                <button class="auth-tab active" onclick="switchTab('login')">Giriş Yap</button>
                <button class="auth-tab" onclick="switchTab('register')">Kayıt Ol</button>
            </div>
            
            <div id="errorMessage" class="error-message"></div>
            <div id="successMessage" class="success-message"></div>
            
            <div id="loginForm" class="auth-form active">
                <div class="form-group">
                    <label>Kullanıcı Adı</label>
                    <input type="text" class="form-input" id="loginUsername" placeholder="Kullanıcı adınız">
                </div>
                <div class="form-group">
                    <label>Şifre</label>
                    <input type="password" class="form-input" id="loginPassword" placeholder="Şifreniz">
                </div>
                <button class="auth-btn" onclick="login()">Giriş Yap</button>
            </div>
            
            <div id="registerForm" class="auth-form">
                <div class="form-group">
                    <label>Kullanıcı Adı</label>
                    <input type="text" class="form-input" id="registerUsername" placeholder="Kullanıcı adınız" maxlength="20">
                </div>
                <div class="form-group">
                    <label>E-posta</label>
                    <input type="email" class="form-input" id="registerEmail" placeholder="E-posta adresiniz">
                </div>
                <div class="form-group">
                    <label>Şifre</label>
                    <input type="password" class="form-input" id="registerPassword" placeholder="Şifreniz (min. 6 karakter)">
                </div>
                <div class="form-group">
                    <label>Şifre Tekrar</label>
                    <input type="password" class="form-input" id="registerPasswordConfirm" placeholder="Şifrenizi tekrar girin">
                </div>
                <button class="auth-btn" onclick="register()">Kayıt Ol</button>
            </div>
        </div>
    </div>
    
    <div class="profile-modal" id="profileModal">
        <div class="profile-box">
            <div class="profile-header">
                <div class="profile-avatar" id="profileAvatar">👤</div>
                <h2 id="profileUsername" style="color: #667eea; margin-bottom: 5px;"></h2>
                <p style="color: #999; font-size: 13px;" id="profileJoinDate"></p>
            </div>
            <div class="profile-info">
                <div class="profile-field">
                    <label>E-POSTA</label>
                    <div class="profile-field-value" id="profileEmail"></div>
                </div>
                <div class="profile-field">
                    <label>KULLANICI ID</label>
                    <div class="profile-field-value" id="profileUserId" style="font-family: monospace;"></div>
                </div>
            </div>
            <div class="profile-actions">
                <button class="profile-close-btn" onclick="closeProfile()">Kapat</button>
            </div>
        </div>
    </div>
    
    <div class="main-container" id="mainContainer">
        <div class="sidebar">
            <div class="sidebar-header">
                <h2>🏠 Sohbet Odaları</h2>
                <div class="user-info" id="userInfo"></div>
                <div class="user-id-display" id="userIdDisplay" title="Kliklayarak kopyala"></div>
                <button class="profile-btn" onclick="showProfile()">👤 Profilim</button>
            </div>
            <div class="rooms-list" id="roomsList"></div>
            <div class="new-room-section">
                <input type="text" class="new-room-input" id="newRoomInput" placeholder="Yeni oda adı" maxlength="30">
                <button class="new-room-btn" onclick="createRoom()">➕ Oda Oluştur</button>
                
                <input type="text" class="private-room-input" id="privateUserIdInput" placeholder="Özel sohbet için ID girin" maxlength="50">
                <button class="private-btn" onclick="startPrivateChat()">🔒 Özel Sohbet</button>
            </div>
        </div>
        <div class="chat-container">
            <div class="chat-header">
                <h2 id="currentRoomName"><span class="room-icon">💬</span> Genel</h2>
                <button class="logout-btn" onclick="logout()">Çıkış Yap</button>
            </div>
            <div class="messages" id="messages">
                <div class="empty-state">
                    <div class="empty-state-icon">💬</div>
                    <p>Henüz mesaj yok. İlk mesajı sen gönder!</p>
                </div>
            </div>
            <div class="input-area">
                <input type="text" class="message-input" id="messageInput" placeholder="Mesajınızı yazın..." maxlength="500">
                <button class="send-btn" onclick="sendMessage()">Gönder</button>
            </div>
        </div>
    </div>
    
    <script>
        let socket;
        let username = '';
        let userId = '';
        let userEmail = '';
        let currentRoom = 'Genel';
        
        function switchTab(tab) {
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            
            if (tab === 'login') {
                document.querySelector('.auth-tab:first-child').classList.add('active');
                document.getElementById('loginForm').classList.add('active');
            } else {
                document.querySelector('.auth-tab:last-child').classList.add('active');
                document.getElementById('registerForm').classList.add('active');
            }
            hideMessages();
        }
        
        function hideMessages() {
            document.getElementById('errorMessage').style.display = 'none';
            document.getElementById('successMessage').style.display = 'none';
        }
        
        function showError(message) {
            const errorDiv = document.getElementById('errorMessage');
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(hideMessages, 5000);
        }
        
        function showSuccess(message) {
            const successDiv = document.getElementById('successMessage');
            successDiv.textContent = message;
            successDiv.style.display = 'block';
            setTimeout(hideMessages, 3000);
        }
        
        function register() {
            const user = document.getElementById('registerUsername').value.trim();
            const email = document.getElementById('registerEmail').value.trim();
            const password = document.getElementById('registerPassword').value;
            const passwordConfirm = document.getElementById('registerPasswordConfirm').value;
            
            if (!user || !email || !password) {
                showError('Tüm alanları doldurun!');
                return;
            }
            
            if (password.length < 6) {
                showError('Şifre en az 6 karakter olmalı!');
                return;
            }
            
            if (password !== passwordConfirm) {
                showError('Şifreler eşleşmiyor!');
                return;
            }
            
            const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
            if (!emailRegex.test(email)) {
                showError('Geçerli bir e-posta adresi girin!');
                return;
            }
            
            fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: user, email, password })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showSuccess('✅ Kayıt başarılı! Giriş yapabilirsiniz.');
                    setTimeout(() => {
                        switchTab('login');
                        document.getElementById('loginUsername').value = user;
                    }, 1500);
                } else {
                    showError(data.message || 'Kayıt başarısız!');
                }
            })
            .catch(() => showError('Bir hata oluştu!'));
        }
        
        function login() {
            const user = document.getElementById('loginUsername').value.trim();
            const pass = document.getElementById('loginPassword').value;
            
            if (!user || !pass) {
                showError('Kullanıcı adı ve şifre girin!');
                return;
            }
            
            fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: user, password: pass })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    username = data.username;
                    userEmail = data.email;
                    document.getElementById('authModal').classList.add('hidden');
                    document.getElementById('mainContainer').classList.add('active');
                    document.getElementById('userInfo').textContent = '👤 ' + username;
                    initSocket();
                    loadRooms();
                } else {
                    showError(data.message || 'Giriş başarısız!');
                }
            })
            .catch(() => showError('Bir hata oluştu!'));
        }
        
        function logout() {
            fetch('/api/logout', { method: 'POST' })
            .then(() => location.reload());
        }
        
        function showProfile() {
            document.getElementById('profileUsername').textContent = username;
            document.getElementById('profileEmail').textContent = userEmail;
            document.getElementById('profileUserId').textContent = userId;
            document.getElementById('profileAvatar').textContent = username.charAt(0).toUpperCase();
            
            fetch('/api/profile')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const joinDate = new Date(data.created_at);
                    document.getElementById('profileJoinDate').textContent = 
                        'Üyelik: ' + joinDate.toLocaleDateString('tr-TR');
                }
            });
            
            document.getElementById('profileModal').classList.add('active');
        }
        
        function closeProfile() {
            document.getElementById('profileModal').classList.remove('active');
        }
        
        function initSocket() {
            socket = io({
                transports: ['websocket', 'polling'],
                upgrade: true,
                rememberUpgrade: true,
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionDelayMax: 5000,
                reconnectionAttempts: 5
            });
            
            socket.on('connect', () => {
                console.log('✅ Socket bağlandı!');
                socket.emit('register_user', { username });
            });
            
            socket.on('user_registered', data => {
                userId = data.user_id;
                document.getElementById('userIdDisplay').textContent = '🔑 ID: ' + userId;
                if (currentRoom) {
                    socket.emit('join_room', { room: currentRoom, username });
                }
            });
            
            socket.on('disconnect', () => console.log('❌ Socket bağlantısı kesildi'));
            
            socket.on('receive_message', data => {
                if (data.room === currentRoom) {
                    displayMessage(data.username, data.message, data.timestamp);
                }
            });
            
            socket.on('room_created', data => {
                addRoomToList(data.name);
            });
            
            socket.on('private_room_created', data => {
                addRoomToList(data.room, true);
                joinRoom(data.room);
            });
            
            socket.on('error_message', data => alert(data.message));
        }
        
        function loadRooms() {
            fetch('/api/rooms')
            .then(res => res.json())
            .then(rooms => {
                const roomsList = document.getElementById('roomsList');
                roomsList.innerHTML = '';
                rooms.forEach(room => addRoomToList(room.name, false));
                setActiveRoom('Genel');
                joinRoom('Genel');
            });
        }
        
        function addRoomToList(roomName, isPrivate = false) {
            const roomsList = document.getElementById('roomsList');
            const existingRoom = document.querySelector(`[data-room="${roomName}"]`);
            if (existingRoom) return;
            
            const roomItem = document.createElement('div');
            roomItem.className = 'room-item' + (isPrivate ? ' private' : '');
            roomItem.setAttribute('data-room', roomName);
            roomItem.onclick = () => joinRoom(roomName);
            
            const icons = {
                'Genel': '💬',
                'Teknoloji': '💻',
                'Spor': '⚽',
                'Müzik': '🎵',
                'Oyun': '🎮'
            };
            const icon = isPrivate ? '🔒' : (icons[roomName] || '📌');
            
            roomItem.innerHTML = `<span class="room-icon">${icon}</span><span class="room-name">${roomName}</span>`;
            roomsList.appendChild(roomItem);
        }
        
        function setActiveRoom(roomName) {
            document.querySelectorAll('.room-item').forEach(item => {
                item.classList.toggle('active', item.getAttribute('data-room') === roomName);
            });
        }
        
        function joinRoom(roomName) {
            if (currentRoom === roomName) return;
            
            if (socket && currentRoom) {
                socket.emit('leave_room', { room: currentRoom, username });
            }
            
            currentRoom = roomName;
            
            if (socket) {
                socket.emit('join_room', { room: roomName, username });
            }
            
            const icons = {
                'Genel': '💬',
                'Teknoloji': '💻',
                'Spor': '⚽',
                'Müzik': '🎵',
                'Oyun': '🎮'
            };
            const isPrivate = roomName.includes('_private_');
            const icon = isPrivate ? '🔒' : (icons[roomName] || '📌');
            
            document.getElementById('currentRoomName').innerHTML = `<span class="room-icon">${icon}</span> ${roomName}`;
            setActiveRoom(roomName);
            loadMessages(roomName);
        }
        
        function loadMessages(roomName) {
            fetch(`/api/messages?room=${encodeURIComponent(roomName)}`)
            .then(res => res.json())
            .then(messages => {
                const messagesDiv = document.getElementById('messages');
                messagesDiv.innerHTML = '';
                
                if (messages.length === 0) {
                    messagesDiv.innerHTML = `<div class="empty-state"><div class="empty-state-icon">💬</div><p>${roomName} odasında henüz mesaj yok. İlk mesajı sen gönder!</p></div>`;
                } else {
                    messages.forEach(msg => displayMessage(msg.username, msg.message, msg.timestamp, true));
                }
                scrollToBottom();
            });
        }
        
        function displayMessage(user, message, timestamp, isHistory = false) {
            const messagesDiv = document.getElementById('messages');
            const emptyState = messagesDiv.querySelector('.empty-state');
            if (emptyState) emptyState.remove();
            
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message' + (user === username ? ' own' : '');
            
            messageDiv.innerHTML = `
                <div class="message-content">
                    <div class="username">${user}</div>
                    <div class="message-text">${message}</div>
                    <div class="timestamp">${timestamp}</div>
                </div>`;
            
            messagesDiv.appendChild(messageDiv);
            if (!isHistory) scrollToBottom();
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (message && socket && socket.connected && currentRoom) {
                socket.emit('send_message', { username, message, room: currentRoom });
                input.value = '';
            }
        }
        
        function createRoom() {
            const input = document.getElementById('newRoomInput');
            const roomName = input.value.trim();
            
            if (roomName) {
                fetch('/api/create_room', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: roomName })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        input.value = '';
                        socket.emit('new_room', { name: roomName });
                        addRoomToList(roomName, false);
                        joinRoom(roomName);
                    } else {
                        alert(data.message || 'Oda oluşturulamadı!');
                    }
                });
            }
        }
        
        function startPrivateChat() {
            const input = document.getElementById('privateUserIdInput');
            const targetUserId = input.value.trim();
            
            if (!targetUserId) {
                alert('Lütfen geçerli bir ID girin!');
                return;
            }
            
            if (targetUserId === userId) {
                alert('Kendinizle özel sohbet yapamazsınız!');
                return;
            }
            
            socket.emit('start_private_chat', {
                from_id: userId,
                to_id: targetUserId,
                username
            });
            
            input.value = '';
        }
        
        function scrollToBottom() {
            const messagesDiv = document.getElementById('messages');
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        document.getElementById('messageInput').addEventListener('keypress', e => {
            if (e.key === 'Enter') sendMessage();
        });
        
        document.getElementById('newRoomInput').addEventListener('keypress', e => {
            if (e.key === 'Enter') createRoom();
        });
        
        document.getElementById('privateUserIdInput').addEventListener('keypress', e => {
            if (e.key === 'Enter') startPrivateChat();
        });
        
        document.getElementById('loginUsername').addEventListener('keypress', e => {
            if (e.key === 'Enter') login();
        });
        
        document.getElementById('loginPassword').addEventListener('keypress', e => {
            if (e.key === 'Enter') login();
        });
        
        document.getElementById('registerPasswordConfirm').addEventListener('keypress', e => {
            if (e.key === 'Enter') register();
        });
        
        document.getElementById('userIdDisplay').addEventListener('click', () => {
            navigator.clipboard.writeText(userId).then(() => {
                alert('ID kopyalandı: ' + userId);
            }).catch(() => {
                const textarea = document.createElement('textarea');
                textarea.value = userId;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                alert('ID kopyalandı: ' + userId);
            });
        });
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not username or not email or not password:
            return jsonify({'success': False, 'message': 'Tüm alanları doldurun!'})
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Şifre en az 6 karakter olmalı!'})
        
        existing_user = users_collection.find_one({'$or': [{'username': username}, {'email': email}]})
        if existing_user:
            if existing_user.get('username') == username:
                return jsonify({'success': False, 'message': 'Bu kullanıcı adı zaten kullanılıyor!'})
            else:
                return jsonify({'success': False, 'message': 'Bu e-posta adresi zaten kullanılıyor!'})
        
        hashed_password = hash_password(password)
        user_doc = {
            'username': username,
            'email': email,
            'password': hashed_password,
            'created_at': datetime.now()
        }
        
        users_collection.insert_one(user_doc)
        logger.info(f'✅ Yeni kullanıcı kaydedildi: {username}')
        
        return jsonify({'success': True, 'message': 'Kayıt başarılı!'})
    
    except Exception as e:
        logger.error(f'❌ Kayıt hatası: {e}')
        return jsonify({'success': False, 'message': 'Bir hata oluştu!'})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Kullanıcı adı ve şifre girin!'})
        
        user = users_collection.find_one({'username': username})
        
        if not user:
            return jsonify({'success': False, 'message': 'Kullanıcı bulunamadı!'})
        
        hashed_password = hash_password(password)
        if user['password'] != hashed_password:
            return jsonify({'success': False, 'message': 'Şifre hatalı!'})
        
        session['username'] = user['username']
        session['email'] = user['email']
        session['user_id'] = str(user['_id'])
        
        logger.info(f'✅ Kullanıcı giriş yaptı: {username}')
        
        return jsonify({
            'success': True,
            'username': user['username'],
            'email': user['email']
        })
    
    except Exception as e:
        logger.error(f'❌ Giriş hatası: {e}')
        return jsonify({'success': False, 'message': 'Bir hata oluştu!'})

@app.route('/api/logout', methods=['POST'])
def logout_route():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/profile')
def get_profile():
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'message': 'Oturum bulunamadı!'})
        
        user = users_collection.find_one({'username': username})
        if not user:
            return jsonify({'success': False, 'message': 'Kullanıcı bulunamadı!'})
        
        return jsonify({
            'success': True,
            'username': user['username'],
            'email': user['email'],
            'created_at': user['created_at'].isoformat()
        })
    
    except Exception as e:
        logger.error(f'❌ Profil hatası: {e}')
        return jsonify({'success': False, 'message': 'Bir hata oluştu!'})

@app.route('/api/rooms')
def get_rooms():
    try:
        rooms = list(rooms_collection.find({}, {'_id': 0, 'name': 1}).sort('name', ASCENDING))
        return jsonify(rooms)
    except Exception as e:
        logger.error(f'❌ Oda listesi hatası: {e}')
        return jsonify([])

@app.route('/api/create_room', methods=['POST'])
def create_room():
    data = request.json
    room_name = data.get('name', '').strip()
    
    if not room_name:
        return jsonify({'success': False, 'message': 'Oda adı boş olamaz!'})
    
    try:
        rooms_collection.insert_one({'name': room_name, 'created_at': datetime.now()})
        return jsonify({'success': True, 'name': room_name})
    except Exception as e:
        return jsonify({'success': False, 'message': 'Bu oda zaten mevcut!'})

@app.route('/api/messages')
def get_messages():
    room = request.args.get('room', 'Genel')
    try:
        messages = list(messages_collection.find(
            {'room': room}, 
            {'_id': 0, 'username': 1, 'message': 1, 'timestamp': 1}
        ).sort('_id', ASCENDING).limit(100))
        
        logger.info(f'✅ Oda: {room}, Mesaj sayısı: {len(messages)}')
        return jsonify(messages)
    except Exception as e:
        logger.error(f'❌ Mesaj yükleme hatası: {e}')
        return jsonify([])

@socketio.on('register_user')
def handle_register_user(data):
    username = data.get('username', 'Anonim')
    user_id = str(uuid.uuid4())[:8].upper()
    
    active_users[request.sid] = {
        'username': username,
        'user_id': user_id,
        'socket_id': request.sid
    }
    
    logger.info(f'✅ Kullanıcı kaydedildi - Adı: {username}, ID: {user_id}, SID: {request.sid}')
    emit('user_registered', {'user_id': user_id})

@socketio.on('send_message')
def handle_message(data):
    username = data.get('username', 'Anonim')
    message = data.get('message', '')
    room = data.get('room', 'Genel')
    timestamp = datetime.now().strftime('%H:%M')
    
    logger.info(f'📨 Mesaj alındı -> Kullanıcı: {username}, Oda: {room}, Mesaj: {message}')
    
    socketio.emit('receive_message', {
        'username': username,
        'message': message,
        'timestamp': timestamp,
        'room': room
    }, to=room)
    
    logger.info(f'📢 Mesaj {room} odasındaki herkese yayınlandı')
    
    try:
        is_private = '_private_' in room
        messages_collection.insert_one({
            'username': username,
            'message': message,
            'timestamp': timestamp,
            'room': room,
            'private': is_private,
            'created_at': datetime.now()
        })
        logger.info(f'💾 Mesaj MongoDB\'ye kaydedildi')
    except Exception as e:
        logger.error(f'❌ MongoDB kayıt hatası: {e}')

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room', 'Genel')
    username = data.get('username', 'Anonim')
    join_room(room)
    logger.info(f'✅ {username} (SID: {request.sid}) -> {room} odasına katıldı')
    
    if '_private_' not in room:
        socketio.emit('receive_message', {
            'username': 'Sistem',
            'message': f'{username} odaya katıldı',
            'timestamp': datetime.now().strftime('%H:%M'),
            'room': room
        }, to=room)

@socketio.on('leave_room')
def handle_leave_room(data):
    room = data.get('room')
    username = data.get('username', 'Anonim')
    leave_room(room)
    logger.info(f'❌ {username} {room} odasından ayrıldı')

@socketio.on('new_room')
def handle_new_room(data):
    emit('room_created', {'name': data['name']}, broadcast=True)

@socketio.on('start_private_chat')
def handle_start_private_chat(data):
    from_id = data.get('from_id')
    to_id = data.get('to_id')
    username = data.get('username')
    
    target_user = None
    target_socket_id = None
    
    for sid, user_data in active_users.items():
        if user_data['user_id'] == to_id:
            target_user = user_data
            target_socket_id = sid
            break
    
    if not target_user:
        emit('error_message', {
            'message': '❌ Kullanıcı çevrimiçi değil veya ID hatalı!'
        })
        logger.info(f'❌ Özel sohbet hatası: Hedef kullanıcı {to_id} bulunamadı')
        return
    
    private_room = f'_private_{sorted([from_id, to_id])[0]}_{sorted([from_id, to_id])[1]}'
    
    logger.info(f'🔒 Özel sohbet başlatılıyor: {username} ({from_id}) <-> {target_user["username"]} ({to_id})')
    logger.info(f'🔒 Oda adı: {private_room}')
    
    socketio.emit('private_room_created', {
        'room': private_room,
        'other_username': target_user['username'],
        'other_id': to_id
    }, to=request.sid)
    
    socketio.emit('private_room_created', {
        'room': private_room,
        'other_username': username,
        'other_id': from_id
    }, to=target_socket_id)
    
    logger.info(f'✅ Özel oda oluşturuldu: {private_room}')

@socketio.on('connect')
def handle_connect():
    user_ip = request.remote_addr
    sid = request.sid
    logger.info(f'✅ Kullanıcı bağlandı - SID: {sid}, IP: {user_ip}')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in active_users:
        user_info = active_users[sid]
        logger.info(f'❌ Kullanıcı ayrıldı - Adı: {user_info["username"]}, ID: {user_info["user_id"]}, SID: {sid}')
        del active_users[sid]
    else:
        logger.info(f'❌ Kullanıcı ayrıldı - SID: {sid}')

if __name__ == '__main__':
    print('\n' + '='*60)
    print('🚀 GRUP SOHBET SUNUCUSU BAŞLATILDI!')
    print('='*60)
    print('📍 Render\'da çalışıyor...')
    print('='*60)
    print('✨ Özellikler:')
    print('   • ✅ Kullanıcı Kayıt ve Giriş Sistemi')
    print('   • ✅ Güvenli Şifre Hash\'leme (SHA-256)')
    print('   • ✅ Oturum Yönetimi (Flask Session)')
    print('   • ✅ Kullanıcı Profil Sayfası')
    print('   • MongoDB Atlas bağlantısı')
    print('   • 5 Varsayılan oda (Genel, Teknoloji, Spor, Müzik, Oyun)')
    print('   • Yeni oda oluşturma')
    print('   • Her odanın bağımsız mesaj sistemi')
    print('   • Gerçek zamanlı mesajlaşma')
    print('   • Her kullanıcıya benzersiz ID verilir')
    print('   • Özel sohbet sistemi (sadece 2 kullanıcı görür)')
    print('   • Modern ve şık tasarım')
    print('='*60 + '\n')

    port = int(os.environ.get("PORT", 5000))
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )
