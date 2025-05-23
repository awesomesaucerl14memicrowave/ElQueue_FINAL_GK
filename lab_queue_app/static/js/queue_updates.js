let lastUpdate = 0;

function updateQueueDisplay(queueData) {
    queueData.forEach(queue => {
        // Обновляем информацию о позиции пользователя
        const queueElement = document.querySelector(`[data-subject-id="${queue.subject_id}"]`);
        if (queueElement) {
            const positionElement = queueElement.querySelector('.queue-position');
            const totalElement = queueElement.querySelector('.queue-total');
            const participantsList = queueElement.querySelector('.participants-list');
            
            if (positionElement && queue.position) {
                positionElement.textContent = queue.position;
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
            
            // Отправляем уведомление, если позиция пользователя изменилась
            const oldPosition = parseInt(positionElement?.dataset?.lastPosition || '0');
            if (queue.position && oldPosition !== queue.position) {
                if (Notification.permission === "granted") {
                    const notification = new Notification("Изменение позиции в очереди", {
                        body: `Ваша позиция в очереди ${queue.subject_name} изменилась: ${oldPosition} → ${queue.position}`,
                        icon: "/static/images/notification-icon.png"
                    });
                }
                if (positionElement) {
                    positionElement.dataset.lastPosition = queue.position;
                }
            }
            
            // Отправляем уведомление при достижении определенных позиций
            if (queue.position === 1 || queue.position === 2 || queue.position === 3) {
                if (Notification.permission === "granted") {
                    const notification = new Notification("Важное уведомление", {
                        body: `Вы ${queue.position}-й в очереди ${queue.subject_name}!`,
                        icon: "/static/images/notification-icon.png"
                    });
                }
            }
        }
    });
}

function requestNotificationPermission() {
    if (!("Notification" in window)) {
        console.log("This browser does not support desktop notification");
        return;
    }
    
    if (Notification.permission !== "granted" && Notification.permission !== "denied") {
        Notification.requestPermission();
    }
}

function pollQueueUpdates() {
    fetch(`/queue-updates/?last_update=${lastUpdate}`)
        .then(response => response.json())
        .then(data => {
            if (data.queues && data.queues.length > 0) {
                updateQueueDisplay(data.queues);
            }
            lastUpdate = data.timestamp;
            // Сразу запускаем следующий запрос
            pollQueueUpdates();
        })
        .catch(error => {
            console.error('Error polling queue updates:', error);
            // В случае ошибки пробуем снова через 5 секунд
            setTimeout(pollQueueUpdates, 5000);
        });
}

// Запускаем long polling при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    requestNotificationPermission();
    if (document.querySelector('[data-subject-id]')) {
        pollQueueUpdates();
    }
}); 