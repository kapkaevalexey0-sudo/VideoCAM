from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List
import socket
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_local_ip():
    """Получить локальный IP адрес"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()
print(f"🌐 Server IP: {LOCAL_IP}")

app = FastAPI(title="Video Chat Server")

# CORS для кросс-доменных запросов
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.rooms: Dict[str, List[str]] = {}
        self.user_info: Dict[str, dict] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"✅ Подключился: {client_id}")
        return True
    
    def disconnect(self, client_id: str):
        # Удаляем из комнаты
        user_data = self.user_info.get(client_id, {})
        room_id = user_data.get("room_id")
        
        if room_id and room_id in self.rooms:
            if client_id in self.rooms[room_id]:
                self.rooms[room_id].remove(client_id)
                logger.info(f"📤 {client_id} вышел из комнаты {room_id}")
                # Если комната пустая, удаляем ее
                if not self.rooms[room_id]:
                    del self.rooms[room_id]
                    logger.info(f"🗑️ Комната {room_id} удалена")
        
        # Удаляем соединение
        self.active_connections.pop(client_id, None)
        self.user_info.pop(client_id, None)
        logger.info(f"📤 Отключился: {client_id}")
    
    async def join_room(self, client_id: str, room_id: str, username: str) -> List[dict]:
        """Присоединить пользователя к комнате"""
        # Создаем комнату если нужно
        if room_id not in self.rooms:
            self.rooms[room_id] = []
            logger.info(f"🏠 Создана комната: {room_id}")
        
        # Добавляем в комнату
        self.rooms[room_id].append(client_id)
        
        # Сохраняем информацию о пользователе
        self.user_info[client_id] = {
            "username": username,
            "room_id": room_id,
            "joined_at": datetime.now().isoformat()
        }
        
        logger.info(f"👥 {username} ({client_id}) вошел в комнату {room_id}")
        
        # Получаем список других участников
        other_users = []
        for uid in self.rooms[room_id]:
            if uid != client_id:
                user_data = self.user_info.get(uid, {})
                other_users.append({
                    "client_id": uid,
                    "username": user_data.get("username", "Unknown"),
                    "room_id": room_id
                })
        
        return other_users
    
    async def send_to_client(self, message: dict, client_id: str) -> bool:
        """Отправить сообщение конкретному клиенту"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
                return True
            except Exception as e:
                logger.error(f"Ошибка отправки клиенту {client_id}: {e}")
                return False
        return False
    
    async def broadcast_to_room(self, message: dict, room_id: str, exclude_client: str = None):
        """Отправить сообщение всем в комнате, кроме указанного клиента"""
        if room_id in self.rooms:
            for client_id in self.rooms[room_id]:
                if client_id != exclude_client:
                    await self.send_to_client(message, client_id)

manager = ConnectionManager()

@app.get("/")
async def home():
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎥 Видеозвонок</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 0; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            .container {{ 
                background: white; 
                padding: 40px; 
                border-radius: 20px; 
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 500px;
                width: 90%;
            }}
            h1 {{ 
                color: #333; 
                margin-bottom: 10px;
                font-size: 32px;
            }}
            .ip-address {{ 
                background: #f0f0f0; 
                padding: 10px; 
                border-radius: 10px; 
                margin: 20px 0;
                font-family: monospace;
                font-size: 18px;
            }}
            .btn {{ 
                display: inline-block;
                padding: 15px 30px; 
                font-size: 18px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; 
                border: none; 
                border-radius: 10px; 
                cursor: pointer; 
                text-decoration: none;
                transition: transform 0.3s, box-shadow 0.3s;
                margin-top: 20px;
            }}
            .btn:hover {{
                transform: translateY(-3px);
                box-shadow: 0 10px 20px rgba(0,0,0,0.2);
            }}
            .instructions {{
                margin-top: 30px;
                text-align: left;
                background: #f9f9f9;
                padding: 20px;
                border-radius: 10px;
                font-size: 14px;
            }}
            .instructions li {{
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Видеозвонок</h1>
            <p>Простой и быстрый видеочат для общения</p>
            
            <div class="ip-address">
                IP сервера: <strong>{LOCAL_IP}</strong>
            </div>
            
            <a href="/chat" class="btn">Открыть видеозвонок</a>
            
            <div class="instructions">
                <h3>📋 Как использовать:</h3>
                <ol>
                    <li>Нажмите "Открыть видеозвонок"</li>
                    <li>Введите имя и ID комнаты</li>
                    <li>Нажмите "Подключиться к комнате"</li>
                    <li>Разрешите доступ к камере и микрофону</li>
                    <li>Пригласите других участников по тому же ID комнаты</li>
                </ol>
                <p><strong>Для доступа с других устройств:</strong><br>
                Откройте в браузере: <code>http://{LOCAL_IP}:8000</code></p>
            </div>
        </div>
    </body>
    </html>
    """)

@app.get("/chat")
async def chat_page():
    html_content = """
    <!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎥 Видеозвонок</title>
    <style>
        :root {
            --primary-color: #4a6ee0;
            --secondary-color: #6a11cb;
            --success-color: #2ecc71;
            --danger-color: #e74c3c;
            --warning-color: #f39c12;
            --dark-color: #2c3e50;
            --light-color: #ecf0f1;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        
        /* Шапка */
        header {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 30px 40px;
            text-align: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        header h1 {
            font-size: 36px;
            margin-bottom: 10px;
            font-weight: 700;
        }
        
        header p {
            font-size: 18px;
            opacity: 0.9;
            max-width: 600px;
            margin: 0 auto;
        }
        
        /* Панель управления */
        .controls-panel {
            padding: 30px 40px;
            background: var(--light-color);
            border-bottom: 1px solid #ddd;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            align-items: end;
        }
        
        .control-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .control-group label {
            font-weight: 600;
            color: var(--dark-color);
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .input-field {
            padding: 14px 18px;
            border: 2px solid #ddd;
            border-radius: 12px;
            font-size: 16px;
            transition: all 0.3s;
            background: white;
        }
        
        .input-field:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(74, 110, 224, 0.1);
        }
        
        .btn {
            padding: 16px 28px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(74, 110, 224, 0.3);
        }
        
        .btn-success {
            background: linear-gradient(135deg, var(--success-color), #27ae60);
            color: white;
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(46, 204, 113, 0.3);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, var(--danger-color), #c0392b);
            color: white;
        }
        
        .btn-danger:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(231, 76, 60, 0.3);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }
        
        /* Видео контейнер */
        .video-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 30px;
            padding: 40px;
        }
        
        .video-box {
            background: var(--dark-color);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            position: relative;
            transition: all 0.3s;
            border: 4px solid transparent;
        }
        
        .video-box.local {
            border-color: var(--success-color);
        }
        
        .video-box.remote {
            border-color: var(--primary-color);
        }
        
        .video-box:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }
        
        video {
            width: 100%;
            height: auto;
            display: block;
            background: #000;
            min-height: 400px;
            object-fit: cover;
        }
        
        .video-overlay {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(transparent, rgba(0, 0, 0, 0.9));
            padding: 25px;
            color: white;
        }
        
        .video-title {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .video-status {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 14px;
            opacity: 0.9;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }
        
        .status-online {
            background: var(--success-color);
            animation: pulse 2s infinite;
        }
        
        .status-offline {
            background: var(--danger-color);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 400px;
            color: #999;
            text-align: center;
            padding: 40px;
        }
        
        .empty-state-icon {
            font-size: 80px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        
        /* Уведомления */
        .notification {
            position: fixed;
            top: 30px;
            right: 30px;
            padding: 20px 25px;
            border-radius: 12px;
            color: white;
            font-weight: 600;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            z-index: 1000;
            animation: slideInRight 0.3s ease;
            max-width: 400px;
        }
        
        .notification-success {
            background: linear-gradient(135deg, var(--success-color), #27ae60);
        }
        
        .notification-error {
            background: linear-gradient(135deg, var(--danger-color), #c0392b);
        }
        
        .notification-info {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        }
        
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        /* Индикаторы */
        .stats-bar {
            display: flex;
            justify-content: space-between;
            padding: 20px 40px;
            background: rgba(44, 62, 80, 0.05);
            border-top: 1px solid #eee;
            font-size: 14px;
            color: #666;
        }
        
        .stat-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        /* Адаптивность */
        @media (max-width: 1200px) {
            .video-container {
                grid-template-columns: 1fr;
            }
            
            .video-box {
                min-height: 400px;
            }
        }
        
        @media (max-width: 768px) {
            .controls-panel {
                grid-template-columns: 1fr;
            }
            
            .video-container {
                padding: 20px;
                gap: 20px;
            }
            
            header, .controls-panel {
                padding: 20px;
            }
            
            header h1 {
                font-size: 28px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Шапка -->
        <header>
            <h1>🎥 Видеозвонок</h1>
            <p>Подключитесь к комнате для начала видеозвонка с друзьями и коллегами</p>
        </header>
        
        <!-- Панель управления -->
        <div class="controls-panel">
            <div class="control-group">
                <label for="username">👤 Ваше имя</label>
                <input type="text" id="username" class="input-field" placeholder="Введите ваше имя" value="Пользователь">
            </div>
            
            <div class="control-group">
                <label for="roomId">🏠 ID комнаты</label>
                <input type="text" id="roomId" class="input-field" placeholder="Введите ID комнаты" value="комната1">
            </div>
            
            <div class="control-group">
                <label>&nbsp;</label>
                <button class="btn btn-primary" onclick="connectToRoom()" id="connectBtn">
                    <span>🔗</span>
                    <span>Подключиться к комнате</span>
                </button>
            </div>
            
            <div class="control-group">
                <label>&nbsp;</label>
                <button class="btn btn-success" onclick="startVideo()" id="videoBtn" disabled>
                    <span>📹</span>
                    <span>Включить камеру</span>
                </button>
            </div>
            
            <div class="control-group">
                <label>&nbsp;</label>
                <button class="btn btn-danger" onclick="stopVideo()" id="stopBtn" disabled>
                    <span>⏹️</span>
                    <span>Выключить камеру</span>
                </button>
            </div>
        </div>
        
        <!-- Видео контейнер -->
        <div class="video-container" id="videoContainer">
            <!-- Локальное видео -->
            <div class="video-box local">
                <video id="localVideo" autoplay muted playsinline></video>
                <div class="video-overlay">
                    <div class="video-title">
                        <span>Вы</span>
                    </div>
                    <div class="video-status">
                        <span class="status-indicator status-offline" id="localStatus"></span>
                        <span>Камера выключена</span>
                    </div>
                </div>
            </div>
            
            <!-- Удаленное видео (появится когда подключится другой участник) -->
            <div class="video-box remote" id="remoteVideoPlaceholder">
                <div class="empty-state">
                    <div class="empty-state-icon">👤</div>
                    <h3>Ожидание участников</h3>
                    <p>Подключитесь к комнате и пригласите других участников по тому же ID комнаты</p>
                    <p style="margin-top: 10px; font-size: 14px; opacity: 0.7;">
                        Как только кто-то подключится, здесь появится видео
                    </p>
                </div>
            </div>
        </div>
        
        <!-- Панель статистики -->
        <div class="stats-bar">
            <div class="stat-item">
                <span>👥 Участников в комнате:</span>
                <strong id="participantCount">0</strong>
            </div>
            <div class="stat-item">
                <span>🌐 Статус соединения:</span>
                <strong id="connectionStatus">Не подключено</strong>
            </div>
            <div class="stat-item">
                <span>📹 Статус камеры:</span>
                <strong id="cameraStatus">Выключена</strong>
            </div>
        </div>
    </div>
    
    <!-- Уведомления -->
    <div class="notification" id="notification" style="display: none;"></div>

    <!-- Основной скрипт -->
    <script>
        // ============================================
        // КОНФИГУРАЦИЯ И ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
        // ============================================
        const CONFIG = {
            ICE_SERVERS: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'stun:stun2.l.google.com:19302' },
                { urls: 'stun:stun3.l.google.com:19302' },
                { urls: 'stun:stun4.l.google.com:19302' }
            ],
            MEDIA_CONSTRAINTS: {
                video: {
                    width: { ideal: 1280, min: 640, max: 1920 },
                    height: { ideal: 720, min: 480, max: 1080 },
                    frameRate: { ideal: 30, min: 15, max: 60 },
                    facingMode: "user"
                },
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    channelCount: 2
                }
            }
        };
        
        // Глобальные переменные
        let ws = null;
        let clientId = null;
        let roomId = null;
        let username = null;
        let localStream = null;
        let peerConnections = {};
        let userNames = {};
        let notificationTimeout = null;
        
        // DOM элементы
        const connectBtn = document.getElementById('connectBtn');
        const videoBtn = document.getElementById('videoBtn');
        const stopBtn = document.getElementById('stopBtn');
        const localVideo = document.getElementById('localVideo');
        const localStatus = document.getElementById('localStatus');
        const videoContainer = document.getElementById('videoContainer');
        const remoteVideoPlaceholder = document.getElementById('remoteVideoPlaceholder');
        const notification = document.getElementById('notification');
        const participantCount = document.getElementById('participantCount');
        const connectionStatus = document.getElementById('connectionStatus');
        const cameraStatus = document.getElementById('cameraStatus');
        
        // ============================================
        // УТИЛИТЫ И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
        // ============================================
        
        function showNotification(message, type = 'info', duration = 5000) {
            // Скрываем предыдущее уведомление
            if (notificationTimeout) {
                clearTimeout(notificationTimeout);
            }
            
            // Настраиваем уведомление
            notification.textContent = message;
            notification.className = 'notification';
            
            switch(type) {
                case 'success':
                    notification.classList.add('notification-success');
                    break;
                case 'error':
                    notification.classList.add('notification-error');
                    break;
                case 'info':
                    notification.classList.add('notification-info');
                    break;
            }
            
            // Показываем
            notification.style.display = 'block';
            
            // Автоскрытие
            notificationTimeout = setTimeout(() => {
                notification.style.display = 'none';
            }, duration);
        }
        
        function hideNotification() {
            if (notificationTimeout) {
                clearTimeout(notificationTimeout);
            }
            notification.style.display = 'none';
        }
        
        function updateParticipantCount() {
            const count = Object.keys(peerConnections).length;
            participantCount.textContent = count;
        }
        
        function updateConnectionStatus(status, isConnected = false) {
            connectionStatus.textContent = status;
            connectionStatus.style.color = isConnected ? '#2ecc71' : '#e74c3c';
        }
        
        function updateCameraStatus(status, isActive = false) {
            cameraStatus.textContent = status;
            cameraStatus.style.color = isActive ? '#2ecc71' : '#e74c3c';
        }
        
        function updateLocalStatus(isActive) {
            if (isActive) {
                localStatus.className = 'status-indicator status-online';
                updateCameraStatus('Включена', true);
            } else {
                localStatus.className = 'status-indicator status-offline';
                updateCameraStatus('Выключена', false);
            }
        }
        
        // ============================================
        // ПОДКЛЮЧЕНИЕ К КОМНАТЕ
        // ============================================
        
        async function connectToRoom() {
            // Получаем данные из формы
            roomId = document.getElementById('roomId').value.trim() || 'комната1';
            username = document.getElementById('username').value.trim() || 'Пользователь';
            
            // Генерируем уникальный ID клиента
            clientId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            
            // Обновляем UI
            connectBtn.disabled = true;
            connectBtn.innerHTML = '<span>🔄</span><span>Подключаемся...</span>';
            showNotification('🔄 Подключаемся к серверу...', 'info');
            updateConnectionStatus('Подключаемся...');
            
            try {
                // Определяем URL для WebSocket
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const hostname = window.location.hostname;
                const port = window.location.port || (protocol === 'wss:' ? '8443' : '8000');
                const wsUrl = `${protocol}//${hostname}:${port}/ws/${clientId}`;
                
                console.log('WebSocket URL:', wsUrl);
                
                // Создаем WebSocket соединение
                ws = new WebSocket(wsUrl);
                
                // Обработчики WebSocket
                ws.onopen = () => {
                    console.log('✅ WebSocket подключен');
                    showNotification('✅ Подключено к серверу', 'success');
                    updateConnectionStatus('Подключено', true);
                    
                    // Отправляем запрос на присоединение к комнате
                    ws.send(JSON.stringify({
                        type: 'join',
                        room: roomId,
                        username: username
                    }));
                    
                    // Обновляем кнопку
                    connectBtn.innerHTML = '<span>✅</span><span>Подключено</span>';
                    
                    // Включаем кнопку камеры
                    videoBtn.disabled = false;
                };
                
                ws.onmessage = handleWebSocketMessage;
                
                ws.onclose = (event) => {
                    console.log('📤 WebSocket отключен:', event.code, event.reason);
                    showNotification('❌ Соединение с сервером потеряно', 'error');
                    updateConnectionStatus('Отключено', false);
                    resetConnection();
                };
                
                ws.onerror = (error) => {
                    console.error('❌ WebSocket ошибка:', error);
                    showNotification('❌ Ошибка подключения к серверу', 'error');
                    updateConnectionStatus('Ошибка', false);
                    resetConnection();
                };
                
            } catch (error) {
                console.error('❌ Ошибка подключения:', error);
                showNotification(`❌ Ошибка: ${error.message}`, 'error');
                updateConnectionStatus('Ошибка', false);
                resetConnection();
            }
        }
        
        // ============================================
        // ОБРАБОТКА СООБЩЕНИЙ ОТ СЕРВЕРА
        // ============================================
        
        function handleWebSocketMessage(event) {
            try {
                const data = JSON.parse(event.data);
                console.log('📨 Получено от сервера:', data.type, data);
                
                switch(data.type) {
                    case 'joined':
                        handleJoined(data);
                        break;
                    case 'user_joined':
                        handleUserJoined(data);
                        break;
                    case 'user_left':
                        handleUserLeft(data);
                        break;
                    case 'offer':
                        handleOffer(data);
                        break;
                    case 'answer':
                        handleAnswer(data);
                        break;
                    case 'ice_candidate':
                        handleIceCandidate(data);
                        break;
                    case 'error':
                        showNotification(`❌ Ошибка: ${data.message}`, 'error');
                        break;
                    default:
                        console.warn('Неизвестный тип сообщения:', data.type);
                }
            } catch (error) {
                console.error('❌ Ошибка обработки сообщения:', error);
            }
        }
        
        function handleJoined(data) {
            showNotification(`✅ Присоединились к комнате: ${data.room_id}`, 'success');
            
            // Сохраняем информацию о других участниках
            if (data.participants && data.participants.length > 0) {
                showNotification(`👥 В комнате уже есть участники: ${data.participants.map(p => p.username).join(', ')}`);
                
                // Создаем соединения с существующими участниками
                data.participants.forEach(participant => {
                    userNames[participant.client_id] = participant.username;
                    createPeerConnection(participant.client_id);
                });
                
                updateParticipantCount();
            }
        }
        
        function handleUserJoined(data) {
            const userId = data.client_id;
            const userName = data.username;
            
            // Сохраняем имя пользователя
            userNames[userId] = userName;
            
            showNotification(`👋 ${userName} присоединился к комнате`, 'info');
            
            // Создаем peer connection
            createPeerConnection(userId).then(pc => {
                // Отправляем офер новому пользователю
                if (localStream) {
                    sendOffer(userId);
                }
            });
            
            updateParticipantCount();
        }
        
        function handleUserLeft(data) {
            const userId = data.client_id;
            const userName = data.username || userNames[userId] || 'Участник';
            
            showNotification(`👋 ${userName} вышел из комнаты`, 'info');
            
            // Закрываем peer connection
            if (peerConnections[userId]) {
                peerConnections[userId].close();
                delete peerConnections[userId];
            }
            
            // Удаляем имя пользователя
            delete userNames[userId];
            
            // Удаляем видео элемент
            removeRemoteVideo(userId);
            
            updateParticipantCount();
        }
        
        // ============================================
        // РАБОТА С КАМЕРОЙ И МИКРОФОНОМ
        // ============================================
        
        async function startVideo() {
            try {
                showNotification('🔄 Запрашиваю доступ к камере и микрофону...', 'info');
                
                // Запрашиваем доступ к медиаустройствам
                localStream = await navigator.mediaDevices.getUserMedia(CONFIG.MEDIA_CONSTRAINTS);
                
                // Отображаем локальное видео
                localVideo.srcObject = localStream;
                updateLocalStatus(true);
                
                // Обновляем кнопки
                videoBtn.disabled = true;
                stopBtn.disabled = false;
                
                showNotification('✅ Камера и микрофон включены', 'success');
                
                // Отправляем оферы всем подключенным пользователям
                for (const userId in peerConnections) {
                    const pc = peerConnections[userId];
                    if (pc) {
                        // Добавляем локальные треки в существующее соединение
                        localStream.getTracks().forEach(track => {
                            try {
                                pc.addTrack(track, localStream);
                            } catch (e) {
                                // Трек уже добавлен, создаем новое соединение
                                console.log('Трек уже добавлен, создаем новое соединение');
                                createPeerConnection(userId).then(newPc => {
                                    sendOffer(userId);
                                });
                            }
                        });
                        
                        // Отправляем офер
                        await sendOffer(userId);
                    }
                }
                
            } catch (error) {
                console.error('❌ Ошибка при включении камеры:', error);
                handleCameraError(error);
            }
        }
        
        function handleCameraError(error) {
            let message = '❌ Ошибка доступа к медиаустройствам: ';
            
            if (error.name === 'NotAllowedError') {
                message += 'Доступ запрещен. Разрешите доступ к камере и микрофону в настройках браузера.';
            } else if (error.name === 'NotFoundError') {
                message += 'Камера или микрофон не найдены.';
            } else if (error.name === 'NotReadableError') {
                message += 'Не могу получить доступ к камере. Возможно, она уже используется другим приложением.';
            } else if (error.name === 'OverconstrainedError') {
                message += 'Запрошенные настройки камеры не поддерживаются.';
            } else {
                message += error.message;
            }
            
            showNotification(message, 'error');
            updateLocalStatus(false);
            
            // Включаем кнопку повторно
            videoBtn.disabled = false;
            stopBtn.disabled = true;
        }
        
        function stopVideo() {
            if (localStream) {
                // Останавливаем все треки
                localStream.getTracks().forEach(track => {
                    track.stop();
                });
                localStream = null;
                
                // Очищаем видео элемент
                localVideo.srcObject = null;
                updateLocalStatus(false);
                
                // Закрываем все peer connections
                for (const userId in peerConnections) {
                    peerConnections[userId].close();
                }
                peerConnections = {};
                
                // Удаляем все удаленные видео
                removeAllRemoteVideos();
                
                // Обновляем кнопки
                videoBtn.disabled = false;
                stopBtn.disabled = true;
                
                showNotification('Камера и микрофон выключены', 'info');
            }
        }
        
        // ============================================
        // WEBRTC: PEER CONNECTION
        // ============================================
        
        async function createPeerConnection(userId) {
            // Если соединение уже существует, возвращаем его
            if (peerConnections[userId]) {
                console.log(`✅ Соединение с ${userId} уже существует`);
                return peerConnections[userId];
            }
            
            console.log(`🔗 Создаю новое соединение с ${userId}`);
            
            // Создаем новый RTCPeerConnection
            const pc = new RTCPeerConnection({
                iceServers: CONFIG.ICE_SERVERS,
                iceTransportPolicy: 'all',
                bundlePolicy: 'max-bundle',
                rtcpMuxPolicy: 'require'
            });
            
            peerConnections[userId] = pc;
            
            // Добавляем локальные треки если камера включена
            if (localStream) {
                localStream.getTracks().forEach(track => {
                    try {
                        pc.addTrack(track, localStream);
                    } catch (e) {
                        console.log('Трек уже добавлен в это соединение');
                    }
                });
            }
            
            // Обработка ICE кандидатов
            pc.onicecandidate = (event) => {
                if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        type: 'ice_candidate',
                        target: userId,
                        candidate: event.candidate
                    }));
                }
            };
            
            // Обработка изменения состояния ICE соединения
            pc.oniceconnectionstatechange = () => {
                console.log(`ICE состояние для ${userId}:`, pc.iceConnectionState);
                
                if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
                    console.log(`Перезапускаю ICE для ${userId}`);
                    pc.restartIce();
                }
            };
            
            // Обработка удаленного потока
            pc.ontrack = (event) => {
                console.log(`🎬 Получен поток от ${userId}`);
                const stream = event.streams[0];
                
                // Создаем или обновляем видео элемент
                createRemoteVideoElement(userId, stream);
                
                // Показываем уведомление
                const userName = userNames[userId] || 'Участник';
                showNotification(`✅ Видео от ${userName} получено`, 'success');
            };
            
            return pc;
        }
        
        // ============================================
        // WEBRTC: ОБРАБОТКА ОФЕРОВ И ОТВЕТОВ
        // ============================================
        
        async function sendOffer(userId) {
            const pc = peerConnections[userId];
            if (!pc) {
                console.error(`❌ Нет соединения для отправки офера ${userId}`);
                return;
            }
            
            try {
                console.log(`📤 Создаю офер для ${userId}`);
                
                const offerOptions = {
                    offerToReceiveAudio: true,
                    offerToReceiveVideo: true,
                    voiceActivityDetection: false
                };
                
                const offer = await pc.createOffer(offerOptions);
                await pc.setLocalDescription(offer);
                
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        type: 'offer',
                        target: userId,
                        offer: {
                            sdp: pc.localDescription.sdp,
                            type: pc.localDescription.type
                        }
                    }));
                    
                    console.log(`✅ Офер отправлен ${userId}`);
                }
            } catch (error) {
                console.error(`❌ Ошибка создания/отправки офера для ${userId}:`, error);
            }
        }
        
        async function handleOffer(data) {
            const userId = data.sender;
            console.log(`📥 Получен офер от ${userId}`);
            
            // Создаем или получаем существующее соединение
            const pc = await createPeerConnection(userId);
            
            try {
                await pc.setRemoteDescription(new RTCSessionDescription(data.offer));
                
                const answerOptions = {
                    voiceActivityDetection: false
                };
                
                const answer = await pc.createAnswer(answerOptions);
                await pc.setLocalDescription(answer);
                
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        type: 'answer',
                        target: userId,
                        answer: {
                            sdp: pc.localDescription.sdp,
                            type: pc.localDescription.type
                        }
                    }));
                    
                    console.log(`✅ Ответ отправлен ${userId}`);
                }
            } catch (error) {
                console.error(`❌ Ошибка обработки офера от ${userId}:`, error);
            }
        }
        
        async function handleAnswer(data) {
            const userId = data.sender;
            const pc = peerConnections[userId];
            
            if (pc) {
                try {
                    await pc.setRemoteDescription(new RTCSessionDescription(data.answer));
                    console.log(`✅ Ответ от ${userId} установлен`);
                } catch (error) {
                    console.error(`❌ Ошибка установки ответа от ${userId}:`, error);
                }
            }
        }
        
        async function handleIceCandidate(data) {
            const userId = data.sender;
            const pc = peerConnections[userId];
            
            if (pc && data.candidate) {
                try {
                    await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
                    console.log(`✅ ICE кандидат от ${userId} добавлен`);
                } catch (error) {
                    console.error(`❌ Ошибка добавления ICE кандидата от ${userId}:`, error);
                }
            }
        }
        
        // ============================================
        // УПРАВЛЕНИЕ ВИДЕО ЭЛЕМЕНТАМИ
        // ============================================
        
        function createRemoteVideoElement(userId, stream) {
            // Убираем placeholder
            remoteVideoPlaceholder.style.display = 'none';
            
            // Удаляем существующее видео если есть
            removeRemoteVideo(userId);
            
            // Создаем новый контейнер для видео
            const videoBox = document.createElement('div');
            videoBox.className = 'video-box remote';
            videoBox.id = `remote_${userId}`;
            
            // Создаем video элемент
            const video = document.createElement('video');
            video.id = `remoteVideo_${userId}`;
            video.autoplay = true;
            video.playsInline = true;
            video.srcObject = stream;
            
            // Создаем оверлей с информацией
            const overlay = document.createElement('div');
            overlay.className = 'video-overlay';
            
            const title = document.createElement('div');
            title.className = 'video-title';
            
            const userName = userNames[userId] || 'Участник';
            title.innerHTML = `
                <span>${userName}</span>
                <span class="status-indicator status-online"></span>
            `;
            
            const status = document.createElement('div');
            status.className = 'video-status';
            status.textContent = 'Включено';
            
            overlay.appendChild(title);
            overlay.appendChild(status);
            videoBox.appendChild(video);
            videoBox.appendChild(overlay);
            
            // Добавляем в контейнер
            videoContainer.appendChild(videoBox);
            
            console.log(`✅ Видео элемент для ${userId} создан`);
        }
        
        function removeRemoteVideo(userId) {
            const videoElement = document.getElementById(`remote_${userId}`);
            if (videoElement) {
                videoElement.remove();
                console.log(`🗑️ Видео элемент ${userId} удален`);
            }
            
            // Если больше нет удаленных видео, показываем placeholder
            const remoteVideos = document.querySelectorAll('.remote.video-box');
            if (remoteVideos.length === 0) {
                remoteVideoPlaceholder.style.display = 'block';
            }
        }
        
        function removeAllRemoteVideos() {
            // Удаляем все удаленные видео элементы
            document.querySelectorAll('.remote.video-box').forEach(el => {
                if (el.id !== 'remoteVideoPlaceholder') {
                    el.remove();
                }
            });
            
            // Показываем placeholder
            remoteVideoPlaceholder.style.display = 'block';
        }
        
        // ============================================
        // СБРОС СОЕДИНЕНИЯ И ОЧИСТКА
        // ============================================
        
        function resetConnection() {
            // Закрываем WebSocket
            if (ws) {
                ws.close();
                ws = null;
            }
            
            // Выключаем камеру
            stopVideo();
            
            // Очищаем peer connections
            peerConnections = {};
            userNames = {};
            
            // Удаляем все удаленные видео
            removeAllRemoteVideos();
            
            // Сбрасываем кнопки
            connectBtn.disabled = false;
            connectBtn.innerHTML = '<span>🔗</span><span>Подключиться к комнате</span>';
            videoBtn.disabled = true;
            stopBtn.disabled = true;
            
            // Сбрасываем статусы
            updateConnectionStatus('Не подключено', false);
            updateParticipantCount();
        }
        
        // ============================================
        // ИНИЦИАЛИЗАЦИЯ И ОБРАБОТЧИКИ СОБЫТИЙ
        // ============================================
        
        function initializeEventHandlers() {
            // Обработка нажатия Enter в полях ввода
            document.getElementById('roomId').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') connectToRoom();
            });
            
            document.getElementById('username').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') connectToRoom();
            });
            
            // Очистка при закрытии страницы
            window.addEventListener('beforeunload', () => {
                if (ws) {
                    ws.close();
                }
                if (localStream) {
                    localStream.getTracks().forEach(track => track.stop());
                }
            });
            
            // Периодическая проверка соединения
            setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ping' }));
                }
            }, 30000);
        }
        
        // ============================================
        // ЗАГРУЗКА СТРАНИЦЫ
        // ============================================
        
        window.addEventListener('load', () => {
            console.log('🚀 Страница видеозвонка загружена');
            initializeEventHandlers();
            showNotification('✅ Страница готова к работе', 'success');
            
            // Автоматически показываем информацию о подключении
            setTimeout(() => {
                if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
                    showNotification(`📱 Для подключения с других устройств откройте этот же адрес на другом устройстве`, 'info', 10000);
                }
            }, 2000);
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint для обработки соединений"""
    # Подключаем клиента
    success = await manager.connect(websocket, client_id)
    if not success:
        return
    
    try:
        while True:
            # Ждем сообщение от клиента
            data = await websocket.receive_json()
            await handle_websocket_message(client_id, data)
            
    except WebSocketDisconnect:
        await handle_client_disconnect(client_id)
    except Exception as e:
        logger.error(f"❌ Ошибка с клиентом {client_id}: {str(e)}")
        await handle_client_disconnect(client_id)

async def handle_websocket_message(client_id: str, data: dict):
    """Обработка входящих WebSocket сообщений"""
    message_type = data.get("type")
    
    if message_type == "join":
        await handle_join(client_id, data)
    
    elif message_type == "offer":
        await handle_offer(client_id, data)
    
    elif message_type == "answer":
        await handle_answer(client_id, data)
    
    elif message_type == "ice_candidate":
        await handle_ice_candidate(client_id, data)
    
    elif message_type == "chat":
        await handle_chat(client_id, data)
    
    elif message_type == "ping":
        await handle_ping(client_id)

async def handle_join(client_id: str, data: dict):
    """Обработка присоединения к комнате"""
    room_id = data.get("room", "default")
    username = data.get("username", "Anonymous")
    
    logger.info(f"👤 {username} пытается присоединиться к комнате {room_id}")
    
    # Получаем существующих участников ДО добавления нового
    existing_users = []
    if room_id in manager.rooms:
        existing_users = manager.rooms[room_id].copy()
    
    # Добавляем нового пользователя в комнату
    other_users = await manager.join_room(client_id, room_id, username)
    
    # 1. Отправляем подтверждение новому пользователю
    await manager.send_to_client({
        "type": "joined",
        "room_id": room_id,
        "client_id": client_id,
        "username": username,
        "participants": other_users,
        "timestamp": datetime.now().isoformat()
    }, client_id)
    
    logger.info(f"✅ {username} присоединился к комнате {room_id}. Участников: {len(existing_users) + 1}")
    
    # 2. Уведомляем существующих участников о новом пользователе
    for existing_user in other_users:
        await manager.send_to_client({
            "type": "user_joined",
            "client_id": client_id,
            "username": username,
            "timestamp": datetime.now().isoformat(),
            "should_initiate": True  # Существующие участники инициируют соединение
        }, existing_user["client_id"])
        
        # 3. Уведомляем нового пользователя о существующих участниках
        await manager.send_to_client({
            "type": "user_joined",
            "client_id": existing_user["client_id"],
            "username": existing_user["username"],
            "timestamp": datetime.now().isoformat(),
            "should_initiate": False  # Новый пользователь будет отвечать на оферы
        }, client_id)

async def handle_offer(client_id: str, data: dict):
    """Обработка WebRTC офера"""
    target_client_id = data.get("target")
    offer = data.get("offer")
    
    if target_client_id and offer:
        logger.info(f"📤 {client_id} отправляет офер {target_client_id}")
        
        await manager.send_to_client({
            "type": "offer",
            "sender": client_id,
            "offer": offer,
            "timestamp": datetime.now().isoformat()
        }, target_client_id)

async def handle_answer(client_id: str, data: dict):
    """Обработка WebRTC ответа"""
    target_client_id = data.get("target")
    answer = data.get("answer")
    
    if target_client_id and answer:
        logger.info(f"📥 {client_id} отправляет ответ {target_client_id}")
        
        await manager.send_to_client({
            "type": "answer",
            "sender": client_id,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        }, target_client_id)

async def handle_ice_candidate(client_id: str, data: dict):
    """Обработка ICE кандидата"""
    target_client_id = data.get("target")
    candidate = data.get("candidate")
    
    if target_client_id and candidate:
        await manager.send_to_client({
            "type": "ice_candidate",
            "sender": client_id,
            "candidate": candidate,
            "timestamp": datetime.now().isoformat()
        }, target_client_id)

async def handle_chat(client_id: str, data: dict):
    """Обработка сообщений чата"""
    room_id = data.get("room")
    message = data.get("message")
    
    if room_id and message:
        # Получаем информацию об отправителе
        user_info = manager.user_info.get(client_id, {})
        username = user_info.get("username", "Unknown")
        
        # Отправляем сообщение всем в комнате, кроме отправителя
        if room_id in manager.rooms:
            for user_id in manager.rooms[room_id]:
                if user_id != client_id:
                    await manager.send_to_client({
                        "type": "chat",
                        "sender": username,
                        "message": message,
                        "timestamp": datetime.now().isoformat()
                    }, user_id)

async def handle_ping(client_id: str):
    """Обработка ping-сообщений для поддержания соединения"""
    await manager.send_to_client({
        "type": "pong",
        "timestamp": datetime.now().isoformat()
    }, client_id)

async def handle_client_disconnect(client_id: str):
    """Обработка отключения клиента"""
    # Получаем информацию о пользователе
    user_info = manager.user_info.get(client_id, {})
    room_id = user_info.get("room_id")
    username = user_info.get("username", "Unknown")
    
    logger.info(f"📤 {username} отключается")
    
    # Отключаем пользователя
    manager.disconnect(client_id)
    
    # Уведомляем других участников комнаты
    if room_id and room_id in manager.rooms:
        for user_id in manager.rooms[room_id]:
            if user_id != client_id and user_id in manager.active_connections:
                await manager.send_to_client({
                    "type": "user_left",
                    "client_id": client_id,
                    "username": username,
                    "timestamp": datetime.now().isoformat()
                }, user_id)

@app.get("/health")
async def health_check():
    """Проверка здоровья сервера"""
    return {
        "status": "healthy",
        "server_ip": LOCAL_IP,
        "clients": len(manager.active_connections),
        "rooms": len(manager.rooms),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/stats")
async def get_stats():
    """Получение статистики сервера"""
    room_stats = {}
    for room_id, users in manager.rooms.items():
        room_stats[room_id] = {
            "users": users,
            "count": len(users),
            "usernames": [manager.user_info.get(uid, {}).get("username", "Unknown") for uid in users]
        }
    
    return {
        "total_clients": len(manager.active_connections),
        "total_rooms": len(manager.rooms),
        "rooms": room_stats,
        "server_started": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import os
    import ssl
    
    print("=" * 70)
    print("🎥 ВИДЕОЧАТ HTTPS - КАМЕРА БУДЕТ РАБОТАТЬ!")
    print("=" * 70)
    
    # Проверяем SSL файлы
    if os.path.exists("localhost.key") and os.path.exists("localhost.crt"):
        print("✅ SSL сертификаты найдены")
        print()
        print("💻 На компьютере откройте:")
        print("   https://localhost:8443")
        print()
        print("📱 На телефоне откройте:")
        print(f"   https://{LOCAL_IP}:8443")
        print("=" * 70)
        print("❗ При первом открытии:")
        print("1. Появится 'Небезопасное соединение'")
        print("2. Нажмите 'Дополнительно'")
        print("3. Нажмите 'Перейти на сайт (небезопасно)'")
        print("4. Разрешите камеру и микрофон")
        print("=" * 70)
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8443,
            ssl_keyfile="localhost.key",
            ssl_certfile="localhost.crt",
            log_level="info"
        )
    else:
        print("❌ SSL сертификаты не найдены!")
        print("Создайте их командой:")
        print("openssl req -x509 -out localhost.crt -keyout localhost.key -newkey rsa:2048 -nodes -sha256 -subj '/CN=localhost'")
        print()
        print("🌐 Альтернатива: Запуск в HTTP режиме")
        print("   (камера будет работать только на localhost)")
        print()
        print("💻 Откройте: http://localhost:8000")
        print(f"📱 Или: http://{LOCAL_IP}:8000")
        print("=" * 70)
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
