class NotificationManager {
    constructor() {
        this.notificationPermission = false;
        this.isPolling = false;
        this.pollInterval = 3000; // интервал опроса в миллисекундах
        this.lastUpdate = 0;
        this.retryAttempts = 0;
        this.maxRetryAttempts = 5;
        this.retryTimeout = 5000; // начальный таймаут для повторных попыток
        this.initialize();
    }

    async initialize() {
        // Запрашиваем разрешение на отправку уведомлений
        console.log('Initializing notifications...');
        if ("Notification" in window) {
            console.log('Notifications are supported');
            try {
                const permission = await Notification.requestPermission();
                console.log('Notification permission:', permission);
                this.notificationPermission = permission === "granted";
            } catch (error) {
                console.error('Error requesting notification permission:', error);
            }
        } else {
            console.log('Notifications are not supported');
        }

        // Начинаем long polling
        this.startPolling();
    }

    async startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;
        this.poll();
    }

    async poll() {
        if (!this.isPolling) return;

        try {
            const response = await fetch(`/queue-updates/?last_update=${this.lastUpdate}`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            });

            // Сбрасываем счетчик попыток при успешном запросе
            this.retryAttempts = 0;

            if (response.status === 204) {
                // Нет контента, просто делаем следующий запрос
                setTimeout(() => this.poll(), this.pollInterval);
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Обновляем timestamp последнего обновления
            if (data.timestamp) {
                this.lastUpdate = data.timestamp;
            }

            // Обрабатываем полученные обновления
            if (data.queues && data.queues.length > 0) {
                this.processQueueUpdates(data.queues);
            }

            // Планируем следующий запрос
            setTimeout(() => this.poll(), this.pollInterval);

        } catch (error) {
            console.error('Ошибка при получении обновлений:', error);
            
            // Увеличиваем счетчик попыток
            this.retryAttempts++;
            
            if (this.retryAttempts >= this.maxRetryAttempts) {
                console.log('Достигнуто максимальное количество попыток. Останавливаем polling.');
                this.isPolling = false;
                return;
            }
            
            // Экспоненциальная задержка перед следующей попыткой
            const timeout = Math.min(this.retryTimeout * Math.pow(2, this.retryAttempts - 1), 30000);
            console.log(`Повторная попытка через ${timeout/1000} секунд...`);
            setTimeout(() => this.poll(), timeout);
        }
    }

    processQueueUpdates(queues) {
        console.log('Processing queue updates:', queues);
        queues.forEach(queue => {
            // Обновляем информацию о позиции пользователя
            const queueElement = document.querySelector(`[data-subject-id="${queue.subject_id}"]`);
            if (queueElement) {
                const positionElement = queueElement.querySelector('.queue-position');
                const totalElement = queueElement.querySelector('.queue-total');
                const participantsList = queueElement.querySelector('.participants-list');
                
                if (positionElement && queue.position) {
                    const oldPosition = parseInt(positionElement.dataset.lastPosition || '0');
                    const newPosition = queue.position;
                    console.log(`Queue ${queue.subject_name}: Position changed from ${oldPosition} to ${newPosition}`);

                    // Показываем уведомление при изменении позиции
                    if (oldPosition !== newPosition) {
                        if (oldPosition > 0) { // Не показываем при первом получении позиции
                            this.showNotification(`Ваша позиция в очереди ${queue.subject_name} изменилась: ${oldPosition} → ${newPosition}`);
                        }
                        positionElement.textContent = newPosition;
                        positionElement.dataset.lastPosition = newPosition;

                        // Уведомление при достижении определенных позиций
                        if (newPosition <= 3 && oldPosition > 3) {
                            this.showNotification(`Осталось совсем немного! Ваша позиция в очереди ${queue.subject_name}: ${newPosition}`);
                        }
                        if (newPosition === 1 && oldPosition > 1) {
                            this.showNotification(`Вы следующий! Ваша позиция в очереди ${queue.subject_name}: 1`);
                        }
                    }
                }

                if (totalElement) {
                    totalElement.textContent = queue.total_participants;
                }
                
                // Обновляем список участников
                if (participantsList && queue.participants) {
                    const participantsHtml = queue.participants.map(participant => `
                        <div class="participant-item">
                            <span class="badge bg-primary me-2">#${participant.position}</span>
                            ${participant.username}
                            <span class="text-muted ms-2">
                                (Лаба ${participant.work_number} - ${participant.work_name})
                            </span>
                        </div>
                    `).join('');
                    participantsList.innerHTML = participantsHtml;
                }
            }
        });
    }

    showNotification(message) {
        console.log('Showing notification:', message);
        console.log('Notification permission status:', this.notificationPermission);
        
        // Показываем браузерное уведомление
        if (this.notificationPermission) {
            try {
                new Notification('ElQueue', {
                    body: message,
                    icon: '/static/images/logo.png'
                });
                console.log('Browser notification sent');
            } catch (error) {
                console.error('Error showing browser notification:', error);
            }
        } else {
            console.log('Browser notifications are not permitted');
        }

        // Показываем уведомление в интерфейсе
        try {
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
                console.log('Creating new toast container');
                const container = document.createElement('div');
                container.id = 'toast-container';
                container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
                document.body.appendChild(container);
            }

            document.getElementById('toast-container').appendChild(toast);
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
            console.log('Toast notification shown');
        } catch (error) {
            console.error('Error showing toast notification:', error);
        }
    }
}

// Инициализируем менеджер уведомлений при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.notificationManager = new NotificationManager();
}); 