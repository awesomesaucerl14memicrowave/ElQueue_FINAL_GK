class NotificationManager {
    constructor() {
        this.socket = null;
        this.notificationPermission = false;
        this.initialize();
    }

    async initialize() {
        // Запрашиваем разрешение на отправку уведомлений
        if ("Notification" in window) {
            const permission = await Notification.requestPermission();
            this.notificationPermission = permission === "granted";
        }

        // Подключаемся к WebSocket
        this.connectWebSocket();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;
        
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log('WebSocket соединение установлено');
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'notification') {
                this.showNotification(data.message);
            }
        };

        this.socket.onclose = () => {
            console.log('WebSocket соединение закрыто');
            // Пытаемся переподключиться через 5 секунд
            setTimeout(() => this.connectWebSocket(), 5000);
        };
    }

    showNotification(message) {
        // Показываем браузерное уведомление
        if (this.notificationPermission) {
            new Notification('ElQueue', {
                body: message,
                icon: '/static/images/logo.png'
            });
        }

        // Показываем уведомление в интерфейсе
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.innerHTML = `
            <div class="toast-header">
                <strong class="me-auto">ElQueue</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;

        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            const container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(container);
        }

        document.getElementById('toast-container').appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
    }
}

// Инициализируем менеджер уведомлений при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.notificationManager = new NotificationManager();
}); 