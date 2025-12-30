from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Модели базы данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # creator, moderator, user
    is_muted = db.Column(db.Boolean, default=False)
    mute_until = db.Column(db.DateTime, nullable=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='author', lazy=True, cascade='all, delete-orphan')
    cart_items = db.relationship('CartItem', backref='user', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='customer', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_creator(self):
        return self.role == 'creator'

    def is_moderator(self):
        return self.role in ['creator', 'moderator']

    def check_mute_status(self):
        if self.is_muted and self.mute_until:
            if datetime.utcnow() > self.mute_until:
                self.is_muted = False
                self.mute_until = None
                db.session.commit()
        return self.is_muted


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.author.username,
            'user_id': self.user_id,
            'role': self.author.role,
            'text': self.text,
            'timestamp': self.timestamp.strftime('%H:%M')
        }


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cart_items = db.relationship('CartItem', backref='product', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'image_url': self.image_url,
            'stock': self.stock
        }


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, paid, shipped, completed, cancelled
    delivery_address = db.Column(db.Text, nullable=False)
    contact_info = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    product_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product_image = db.Column(db.String(500), nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Маршруты
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('chat'))
        else:
            flash('Неверный логин или пароль', 'error')

    return render_template('login.html')


@app.route('/chat')
@login_required
def chat():
    if current_user.check_mute_status():
        flash('Вы были замучены и не можете отправлять сообщения', 'error')

    messages = Message.query.order_by(Message.timestamp.asc()).all()
    users = User.query.all()
    online_users = User.query.filter(User.last_seen >= datetime.utcnow() - timedelta(minutes=5)).all()

    return render_template('chat.html',
                           messages=messages,
                           users=users,
                           online_users=online_users)


@app.route('/admin')
@login_required
def admin():
    if not current_user.is_creator():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('chat'))

    users = User.query.all()
    return render_template('admin.html', users=users)


@app.route('/admin/create_user', methods=['POST'])
@login_required
def create_user():
    if not current_user.is_creator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    username = request.json.get('username')
    password = request.json.get('password')
    role = request.json.get('role', 'user')

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Пользователь уже существует'}), 400

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({'success': True, 'message': f'Пользователь {username} создан'})


@app.route('/admin/change_role', methods=['POST'])
@login_required
def change_role():
    if not current_user.is_creator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    user_id = request.json.get('user_id')
    new_role = request.json.get('role')

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

    user.role = new_role
    db.session.commit()

    return jsonify({'success': True, 'message': f'Роль изменена на {new_role}'})


@app.route('/admin/delete_user', methods=['POST'])
@login_required
def delete_user():
    if not current_user.is_creator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    user_id = request.json.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

    if user.is_creator():
        return jsonify({'success': False, 'message': 'Нельзя удалить создателя'}), 400

    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Пользователь удален'})


@app.route('/mute_user', methods=['POST'])
@login_required
def mute_user():
    if not current_user.is_moderator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    user_id = request.json.get('user_id')
    duration = request.json.get('duration')  # 'forever', '10m', '1h', 'custom'
    custom_minutes = request.json.get('custom_minutes', 0)

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

    if user.is_moderator():
        return jsonify({'success': False, 'message': 'Нельзя замутить модератора'}), 400

    user.is_muted = True

    if duration == 'forever':
        user.mute_until = None
    elif duration == '10m':
        user.mute_until = datetime.utcnow() + timedelta(minutes=10)
    elif duration == '1h':
        user.mute_until = datetime.utcnow() + timedelta(hours=1)
    elif duration == 'custom' and custom_minutes > 0:
        user.mute_until = datetime.utcnow() + timedelta(minutes=custom_minutes)

    db.session.commit()

    socketio.emit('user_muted', {
        'username': user.username,
        'moderator': current_user.username,
        'duration': duration
    }, room='chat')

    return jsonify({'success': True, 'message': f'Пользователь {user.username} замучен'})


@app.route('/unmute_user', methods=['POST'])
@login_required
def unmute_user():
    if not current_user.is_moderator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    user_id = request.json.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

    user.is_muted = False
    user.mute_until = None
    db.session.commit()

    socketio.emit('user_unmuted', {
        'username': user.username,
        'moderator': current_user.username
    }, room='chat')

    return jsonify({'success': True, 'message': f'Мут снят с {user.username}'})


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# === МАГАЗИН ===

@app.route('/shop')
@login_required
def shop():
    products = Product.query.filter(Product.stock > 0).all()
    cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    return render_template('shop.html', products=products, cart_count=cart_count)


@app.route('/shop/product/<int:product_id>')
@login_required
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    return render_template('product_detail.html', product=product, cart_count=cart_count)


@app.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)


@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = int(request.json.get('quantity', 1))

    if product.stock < quantity:
        return jsonify({'success': False, 'message': 'Недостаточно товара на складе'}), 400

    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()

    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)

    db.session.commit()

    cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    return jsonify({'success': True, 'message': 'Товар добавлен в корзину', 'cart_count': cart_count})


@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)

    if cart_item.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    quantity = int(request.json.get('quantity', 1))

    if quantity <= 0:
        db.session.delete(cart_item)
    elif cart_item.product.stock >= quantity:
        cart_item.quantity = quantity
    else:
        return jsonify({'success': False, 'message': 'Недостаточно товара'}), 400

    db.session.commit()
    return jsonify({'success': True})


@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)

    if cart_item.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    db.session.delete(cart_item)
    db.session.commit()

    return jsonify({'success': True})


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()

    if not cart_items:
        flash('Корзина пуста', 'error')
        return redirect(url_for('shop'))

    if request.method == 'POST':
        address = request.form.get('address')
        contact = request.form.get('contact')

        if not address or not contact:
            flash('Заполните все поля', 'error')
            return redirect(url_for('checkout'))

        # Создаем заказ
        total = sum(item.product.price * item.quantity for item in cart_items)
        order = Order(
            user_id=current_user.id,
            total_price=total,
            delivery_address=address,
            contact_info=contact
        )
        db.session.add(order)
        db.session.flush()

        # Добавляем товары в заказ
        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_name=item.product.name,
                product_price=item.product.price,
                quantity=item.quantity,
                product_image=item.product.image_url
            )
            db.session.add(order_item)

            # Уменьшаем количество на складе
            item.product.stock -= item.quantity

        # Очищаем корзину
        for item in cart_items:
            db.session.delete(item)

        db.session.commit()

        flash('Заказ успешно оформлен! Мы свяжемся с вами в ближайшее время.', 'success')
        return redirect(url_for('my_orders'))

    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=total)


@app.route('/orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)


# === АДМИНКА МАГАЗИНА ===

@app.route('/admin/shop')
@login_required
def admin_shop():
    if not current_user.is_creator():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('shop'))

    products = Product.query.all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_shop.html', products=products, orders=orders)


@app.route('/admin/shop/product/create', methods=['POST'])
@login_required
def create_product():
    if not current_user.is_creator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    name = request.form.get('name')
    description = request.form.get('description')
    price = float(request.form.get('price'))
    stock = int(request.form.get('stock'))
    image_url = request.form.get('image_url')

    product = Product(
        name=name,
        description=description,
        price=price,
        stock=stock,
        image_url=image_url
    )

    db.session.add(product)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Товар создан'})


@app.route('/admin/shop/product/<int:product_id>/edit', methods=['POST'])
@login_required
def edit_product(product_id):
    if not current_user.is_creator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    product = Product.query.get_or_404(product_id)

    product.name = request.json.get('name', product.name)
    product.description = request.json.get('description', product.description)
    product.price = float(request.json.get('price', product.price))
    product.stock = int(request.json.get('stock', product.stock))
    product.image_url = request.json.get('image_url', product.image_url)

    db.session.commit()

    return jsonify({'success': True, 'message': 'Товар обновлен'})


@app.route('/admin/shop/product/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    if not current_user.is_creator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Товар удален'})


@app.route('/admin/shop/order/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    if not current_user.is_creator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    order = Order.query.get_or_404(order_id)
    status = request.json.get('status')

    if status in ['pending', 'paid', 'shipped', 'completed', 'cancelled']:
        order.status = status
        db.session.commit()
        return jsonify({'success': True, 'message': 'Статус обновлен'})

    return jsonify({'success': False, 'message': 'Неверный статус'}), 400


# WebSocket события
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room('chat')
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        emit('user_connected', {
            'username': current_user.username,
            'user_id': current_user.id
        }, room='chat')


@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room('chat')
        emit('user_disconnected', {
            'username': current_user.username,
            'user_id': current_user.id
        }, room='chat')


@socketio.on('send_message')
def handle_message(data):
    if not current_user.is_authenticated:
        return

    if current_user.check_mute_status():
        emit('message_error', {'message': 'Вы замучены и не можете отправлять сообщения'})
        return

    message_text = data.get('message', '').strip()
    if not message_text:
        return

    message = Message(user_id=current_user.id, text=message_text)
    db.session.add(message)
    db.session.commit()

    emit('new_message', message.to_dict(), room='chat')


@socketio.on('delete_message')
def handle_delete_message(data):
    if not current_user.is_authenticated:
        return

    message_id = data.get('message_id')
    message = Message.query.get(message_id)

    if not message:
        return

    if message.user_id != current_user.id and not current_user.is_moderator():
        emit('message_error', {'message': 'Вы не можете удалить это сообщение'})
        return

    db.session.delete(message)
    db.session.commit()

    emit('message_deleted', {'message_id': message_id}, room='chat')


@socketio.on('heartbeat')
def handle_heartbeat():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()


# Инициализация базы данных
with app.app_context():
    db.create_all()

    # Создание пользователя-создателя если его нет
    if not User.query.filter_by(username='Resolving').first():
        creator = User(username='Resolving', role='creator')
        creator.set_password('admin123')  # ИЗМЕНИ ПАРОЛЬ!
        db.session.add(creator)
        db.session.commit()
        print("Создатель 'Resolving' создан с паролем 'admin123'")

if __name__ == '__main__':
    socketio.run(app, debug=True)