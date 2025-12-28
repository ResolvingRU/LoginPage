// WebSocket подключение
const socket = io();

let currentMuteUserId = null;
let currentMuteUsername = null;

// Подключение к чату
socket.on('connect', () => {
    console.log('Connected to chat');
    startHeartbeat();
});

// Отключение от чата
socket.on('disconnect', () => {
    console.log('Disconnected from chat');
});

// Пользователь подключился
socket.on('user_connected', (data) => {
    updateUserStatus(data.user_id, true);
    updateOnlineCount();
    showSystemMessage(`${data.username} подключился к чату`);
});

// Пользователь отключился
socket.on('user_disconnected', (data) => {
    updateUserStatus(data.user_id, false);
    updateOnlineCount();
    showSystemMessage(`${data.username} покинул чат`);
});

// Новое сообщение
socket.on('new_message', (message) => {
    addMessageToChat(message);
    scrollToBottom();
});

// Сообщение удалено
socket.on('message_deleted', (data) => {
    const messageEl = document.querySelector(`[data-message-id="${data.message_id}"]`);
    if (messageEl) {
        messageEl.style.animation = 'messageOut 0.3s ease';
        setTimeout(() => messageEl.remove(), 300);
    }
});

// Пользователь замучен
socket.on('user_muted', (data) => {
    let durationText = '';
    switch(data.duration) {
        case 'forever': durationText = 'навсегда'; break;
        case '10m': durationText = 'на 10 минут'; break;
        case '1h': durationText = 'на 1 час'; break;
        default: durationText = data.duration;
    }
    showSystemMessage(`${data.username} был замучен ${durationText} модератором ${data.moderator}`, 'warning');
});

// Пользователь размучен
socket.on('user_unmuted', (data) => {
    showSystemMessage(`С ${data.username} снят мут модератором ${data.moderator}`, 'success');
});

// Ошибка сообщения
socket.on('message_error', (data) => {
    showFlash(data.message, 'error');
});

// Отправка сообщения
const messageForm = document.getElementById('messageForm');
const messageInput = document.getElementById('messageInput');

if (messageForm) {
    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const message = messageInput.value.trim();
        if (!message) return;

        socket.emit('send_message', { message });
        messageInput.value = '';
    });
}

// Удаление сообщения
function deleteMessage(messageId) {
    if (confirm('Удалить это сообщение?')) {
        socket.emit('delete_message', { message_id: messageId });
    }
}

// Добавление сообщения в чат
function addMessageToChat(message) {
    const chatMessages = document.getElementById('chatMessages');

    const messageEl = document.createElement('div');
    messageEl.className = 'message';
    messageEl.dataset.messageId = message.id;
    messageEl.dataset.userId = message.user_id;

    const currentUserId = parseInt(document.body.dataset.userId || 0);
    const isCurrentUser = message.user_id === currentUserId;
    const isModerator = document.body.dataset.isModerator === 'true';

    messageEl.innerHTML = `
        <div class="message-avatar">${message.username[0].toUpperCase()}</div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-author">${message.username}</span>
                <span class="message-role role-${message.role}">${message.role}</span>
                <span class="message-time">${message.timestamp}</span>
            </div>
            <div class="message-text">${escapeHtml(message.text)}</div>
        </div>
        ${isCurrentUser || isModerator ? `<button class="message-delete" onclick="deleteMessage(${message.id})">🗑️</button>` : ''}
    `;

    chatMessages.appendChild(messageEl);
}

// Обновление статуса пользователя
function updateUserStatus(userId, isOnline) {
    const statusIndicator = document.getElementById(`status-${userId}`);
    if (statusIndicator) {
        if (isOnline) {
            statusIndicator.classList.add('status-online');
            statusIndicator.classList.remove('status-offline');
        } else {
            statusIndicator.classList.add('status-offline');
            statusIndicator.classList.remove('status-online');
        }
    }
}

// Обновление счетчика онлайн
function updateOnlineCount() {
    const onlineIndicators = document.querySelectorAll('.status-online');
    const onlineCount = document.getElementById('onlineCount');
    if (onlineCount) {
        onlineCount.textContent = `${onlineIndicators.length} онлайн`;
    }
}

// Показ системного сообщения
function showSystemMessage(text, type = 'info') {
    const chatMessages = document.getElementById('chatMessages');

    const messageEl = document.createElement('div');
    messageEl.className = `message system-message system-${type}`;
    messageEl.innerHTML = `
        <div class="message-content" style="text-align: center; width: 100%; color: var(--text-muted); font-size: 0.9rem;">
            ${text}
        </div>
    `;

    chatMessages.appendChild(messageEl);
    scrollToBottom();
}

// Показ flash сообщения
function showFlash(message, type = 'error') {
    const flashContainer = document.querySelector('.flash-container') || createFlashContainer();

    const flash = document.createElement('div');
    flash.className = `flash flash-${type}`;
    flash.innerHTML = `
        ${message}
        <button class="flash-close" onclick="this.parentElement.remove()">×</button>
    `;

    flashContainer.appendChild(flash);

    setTimeout(() => flash.remove(), 5000);
}

// Создание контейнера для flash сообщений
function createFlashContainer() {
    const container = document.createElement('div');
    container.className = 'flash-container';
    document.body.appendChild(container);
    return container;
}

// Прокрутка вниз
function scrollToBottom() {
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Heartbeat для обновления статуса онлайн
function startHeartbeat() {
    setInterval(() => {
        socket.emit('heartbeat');
    }, 30000); // Каждые 30 секунд
}

// Мут пользователя - открыть модальное окно
function openMuteModal(userId, username) {
    currentMuteUserId = userId;
    currentMuteUsername = username;

    document.getElementById('muteUsername').textContent = username;
    document.getElementById('muteModal').classList.add('active');
}

// Закрыть модальное окно мута
function closeMuteModal() {
    document.getElementById('muteModal').classList.remove('active');
    currentMuteUserId = null;
    currentMuteUsername = null;
}

// Мут пользователя
async function muteUser(duration) {
    if (!currentMuteUserId) return;

    try {
        const response = await fetch('/mute_user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: currentMuteUserId,
                duration: duration
            })
        });

        const data = await response.json();

        if (data.success) {
            showFlash(data.message, 'success');
            closeMuteModal();

            // Обновить кнопку мута
            const muteBtn = document.querySelector(`[data-user-id="${currentMuteUserId}"] .btn-mute`);
            if (muteBtn) {
                muteBtn.outerHTML = `<button class="btn-icon btn-unmute" onclick="unmuteUser(${currentMuteUserId})" title="Размутить">🔊</button>`;
            }
        } else {
            showFlash(data.message, 'error');
        }
    } catch (error) {
        showFlash('Ошибка при муте пользователя', 'error');
        console.error(error);
    }
}

// Мут с пользовательским временем
function muteUserCustom() {
    const minutes = parseInt(document.getElementById('customMuteMinutes').value);

    if (!minutes || minutes < 1) {
        showFlash('Укажите корректное количество минут', 'error');
        return;
    }

    muteUser('custom').then(() => {
        // Отправляем кастомное время
        fetch('/mute_user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: currentMuteUserId,
                duration: 'custom',
                custom_minutes: minutes
            })
        });
    });
}

// Размут пользователя
async function unmuteUser(userId) {
    if (!confirm('Снять мут с этого пользователя?')) return;

    try {
        const response = await fetch('/unmute_user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId
            })
        });

        const data = await response.json();

        if (data.success) {
            showFlash(data.message, 'success');

            // Обновить кнопку размута
            const unmuteBtn = document.querySelector(`[data-user-id="${userId}"] .btn-unmute`);
            if (unmuteBtn) {
                unmuteBtn.outerHTML = `<button class="btn-icon btn-mute" onclick="openMuteModal(${userId}, '...')" title="Замутить">🔇</button>`;
            }
        } else {
            showFlash(data.message, 'error');
        }
    } catch (error) {
        showFlash('Ошибка при размуте пользователя', 'error');
        console.error(error);
    }
}

// Закрытие модального окна при клике вне его
document.addEventListener('click', (e) => {
    const modal = document.getElementById('muteModal');
    if (e.target === modal) {
        closeMuteModal();
    }
});

// Прокрутка вниз при загрузке страницы
window.addEventListener('load', () => {
    scrollToBottom();
    updateOnlineCount();

    // Сохраняем данные пользователя в body для использования
    const currentUserEl = document.querySelector('.username');
    if (currentUserEl) {
        document.body.dataset.userId = currentUserEl.dataset.userId || 0;
    }
});

// Enter для отправки, Shift+Enter для новой строки
if (messageInput) {
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            messageForm.dispatchEvent(new Event('submit'));
        }
    });
}

// Анимация исчезновения сообщения
const style = document.createElement('style');
style.textContent = `
    @keyframes messageOut {
        to {
            transform: translateX(-100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);