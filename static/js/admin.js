// Создание пользователя
const createUserForm = document.getElementById('createUserForm');

if (createUserForm) {
    createUserForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const username = document.getElementById('newUsername').value.trim();
        const password = document.getElementById('newPassword').value;
        const role = document.getElementById('newRole').value;

        if (!username || !password) {
            showFlash('Заполните все поля', 'error');
            return;
        }

        try {
            const response = await fetch('/admin/create_user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password, role })
            });

            const data = await response.json();

            if (data.success) {
                showFlash(data.message, 'success');
                // Очистить форму
                createUserForm.reset();
                // Перезагрузить страницу для обновления списка
                setTimeout(() => location.reload(), 1000);
            } else {
                showFlash(data.message, 'error');
            }
        } catch (error) {
            showFlash('Ошибка при создании пользователя', 'error');
            console.error(error);
        }
    });
}

// Изменение роли пользователя
async function changeRole(userId, newRole) {
    try {
        const response = await fetch('/admin/change_role', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                role: newRole
            })
        });

        const data = await response.json();

        if (data.success) {
            showFlash(data.message, 'success');
        } else {
            showFlash(data.message, 'error');
            // Вернуть предыдущее значение
            location.reload();
        }
    } catch (error) {
        showFlash('Ошибка при изменении роли', 'error');
        console.error(error);
        location.reload();
    }
}

// Удаление пользователя
async function deleteUser(userId, username) {
    if (!confirm(`Вы уверены, что хотите удалить пользователя "${username}"? Это действие нельзя отменить.`)) {
        return;
    }

    try {
        const response = await fetch('/admin/delete_user', {
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

            // Удалить строку из таблицы с анимацией
            const row = document.querySelector(`tr[data-user-id="${userId}"]`);
            if (row) {
                row.style.animation = 'fadeOut 0.3s ease';
                setTimeout(() => row.remove(), 300);
            }
        } else {
            showFlash(data.message, 'error');
        }
    } catch (error) {
        showFlash('Ошибка при удалении пользователя', 'error');
        console.error(error);
    }
}

// Генерация случайного пароля
function generatePassword() {
    const length = 12;
    const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
    let password = '';

    for (let i = 0; i < length; i++) {
        password += charset.charAt(Math.floor(Math.random() * charset.length));
    }

    return password;
}

// Добавить кнопку генерации пароля
const passwordInput = document.getElementById('newPassword');
if (passwordInput && !document.getElementById('generatePasswordBtn')) {
    const generateBtn = document.createElement('button');
    generateBtn.type = 'button';
    generateBtn.id = 'generatePasswordBtn';
    generateBtn.className = 'btn btn-secondary';
    generateBtn.textContent = '🎲 Сгенерировать';
    generateBtn.style.marginTop = '0.5rem';

    generateBtn.addEventListener('click', () => {
        const password = generatePassword();
        passwordInput.value = password;

        // Копировать в буфер обмена
        navigator.clipboard.writeText(password).then(() => {
            showFlash('Пароль скопирован в буфер обмена', 'success');
        }).catch(() => {
            showFlash('Не удалось скопировать пароль', 'error');
        });
    });

    passwordInput.parentElement.appendChild(generateBtn);
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

// Анимация удаления
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        to {
            opacity: 0;
            transform: translateX(-20px);
        }
    }
`;
document.head.appendChild(style);

// Поиск по таблице пользователей
function addSearchFunctionality() {
    const tableBody = document.getElementById('usersTableBody');
    if (!tableBody) return;

    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = '🔍 Поиск пользователей...';
    searchInput.style.marginBottom = '1rem';
    searchInput.style.width = '100%';
    searchInput.style.maxWidth = '400px';

    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const rows = tableBody.querySelectorAll('tr');

        rows.forEach(row => {
            const username = row.querySelector('td:nth-child(2)')?.textContent.toLowerCase();
            if (username && username.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });

    const tableContainer = document.querySelector('.users-table');
    if (tableContainer) {
        tableContainer.insertBefore(searchInput, tableContainer.firstChild);
    }
}

// Инициализация при загрузке страницы
window.addEventListener('load', () => {
    addSearchFunctionality();
});