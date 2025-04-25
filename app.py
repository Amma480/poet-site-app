
import os

from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Замени на свой ключ


# Инициализация базы данных
def init_db():
    with sqlite3.connect('poems.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     username TEXT UNIQUE,
                     password TEXT,
                     role TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS poems (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     title TEXT,
                     content TEXT,
                     position INTEGER,
                     audio_url TEXT,
                     views INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS comments (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     poem_id INTEGER,
                     username TEXT,
                     comment TEXT,
                     FOREIGN KEY (poem_id) REFERENCES poems(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS likes (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     poem_id INTEGER,
                     username TEXT,
                     FOREIGN KEY (poem_id) REFERENCES poems(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS feedback (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     username TEXT,
                     message TEXT,
                     created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS news (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     title TEXT,
                     content TEXT,
                     created_at TEXT,
                     position INTEGER)''')
        try:
            c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                      ('admin', generate_password_hash('admin123'), 'admin'))
            c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                      ('author', generate_password_hash('author123'), 'author'))
        except sqlite3.IntegrityError:
            pass
        conn.commit()


# Проверка авторизации
def is_authenticated():
    return 'username' in session


def is_author_or_admin():
    return is_authenticated() and session.get('role') in ['author', 'admin']

# Функция плохих слов
def filter_bad_words(text):
    bad_words = ['херня', 'хуйня', 'полное гавно']  # Замени на реальный список
    for word in bad_words:
        text = text.replace(word, '***')
    return text

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')


# Страница "Обо мне"
@app.route('/about')
def about():
    return render_template('about.html')


# Страница со стихами
@app.route('/poems', methods=['GET', 'POST'])
def poems():
    conn = sqlite3.connect('poems.db')
    c = conn.cursor()

    if request.method == 'POST':
        poem_id = request.form.get('poem_id')
        action = request.form.get('action')
        anchor = f'#poem-{poem_id}'  # Для сохранения позиции

        if action == 'comment':
            username = request.form.get('username')
            comment = request.form.get('comment')
            filtered_comment = filter_bad_words(comment)  # Фильтр плохих слов
            c.execute('INSERT INTO comments (poem_id, username, comment) VALUES (?, ?, ?)',
                      (poem_id, username, filtered_comment))
            conn.commit()
            return redirect(url_for('poems') + anchor)
        elif action == 'like':
            liked_poems = request.cookies.get('liked_poems', '').split(',')
            if poem_id not in liked_poems:
                c.execute('INSERT INTO likes (poem_id, username) VALUES (?, ?)',
                          (poem_id, 'anonymous'))
                conn.commit()
                response = make_response(redirect(url_for('poems') + anchor))
                liked_poems.append(poem_id)
                response.set_cookie('liked_poems', ','.join(liked_poems), max_age=31536000)
                flash('Лайк добавлен!')
                return response
            else:
                flash('Вы уже лайкнули этот стих!')
                return redirect(url_for('poems') + anchor)
        elif action == 'delete_comment' and is_author_or_admin():
            comment_id = request.form.get('comment_id')
            c.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
            conn.commit()
            return redirect(url_for('poems') + anchor)
        elif action == 'delete_poem' and is_author_or_admin():
            c.execute('DELETE FROM poems WHERE id = ?', (poem_id,))
            conn.commit()
            return redirect(url_for('poems'))
        elif action == 'move_up' and is_author_or_admin():
            c.execute('SELECT position FROM poems WHERE id = ?', (poem_id,))
            pos = c.fetchone()[0]
            if pos > 1:
                c.execute('UPDATE poems SET position = position + 1 WHERE position = ?', (pos - 1,))
                c.execute('UPDATE poems SET position = position - 1 WHERE id = ?', (poem_id,))
                conn.commit()
            return redirect(url_for('poems') + anchor)
        elif action == 'move_down' and is_author_or_admin():
            c.execute('SELECT position FROM poems WHERE id = ?', (poem_id,))
            pos = c.fetchone()[0]
            c.execute('UPDATE poems SET position = position - 1 WHERE position = ?', (pos + 1,))
            c.execute('UPDATE poems SET position = position + 1 WHERE id = ?', (poem_id,))
            conn.commit()
            return redirect(url_for('poems') + anchor)
        elif action == 'clear_likes' and is_author_or_admin():
            c.execute('DELETE FROM likes WHERE poem_id = ?', (poem_id,))
            conn.commit()
            flash('Лайки для стиха очищены!')
            return redirect(url_for('poems') + anchor)

    c.execute('SELECT id, title, content, position, audio_url, views FROM poems ORDER BY position')
    poems = c.fetchall()
    poems_with_comments = []
    poem_likes = {}
    liked_poems = request.cookies.get('liked_poems', '').split(',')
    for poem in poems:
        c.execute('UPDATE poems SET views = views + 1 WHERE id = ?', (poem[0],))  # Увеличиваем просмотры
        c.execute('SELECT id, username, comment FROM comments WHERE poem_id = ?', (poem[0],))
        comments = c.fetchall()
        c.execute('SELECT COUNT(*) FROM likes WHERE poem_id = ?', (poem[0],))
        likes = c.fetchone()[0]
        poem_likes[poem[0]] = str(poem[0]) in liked_poems
        poems_with_comments.append((poem, comments, likes))

    conn.commit()
    conn.close()
    return render_template('poems.html', poems=poems_with_comments, poem_likes=poem_likes)

app.config['UPLOAD_FOLDER'] = 'static/audio'
ALLOWED_EXTENSIONS = {'mp3'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Страница добавления стиха
@app.route('/add_poem', methods=['GET', 'POST'])
def add_poem():
    if not is_author_or_admin():
        flash('Только Автор или Админ могут добавлять стихи! Авторизуйтесь.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        audio_url = request.form.get('audio_url')

        conn = sqlite3.connect('poems.db')
        c = conn.cursor()
        c.execute('SELECT MAX(position) FROM poems')
        max_pos = c.fetchone()[0] or 0
        c.execute('INSERT INTO poems (title, content, position, audio_url, views) VALUES (?, ?, ?, ?, ?)',
                  (title, content, max_pos + 1, audio_url, 0))
        conn.commit()
        conn.close()
        flash('Стих успешно добавлен!')
        return redirect(url_for('poems'))

    return render_template('add_poem.html')


@app.route('/edit_poem/<int:poem_id>', methods=['GET', 'POST'])
def edit_poem(poem_id):
    if not is_author_or_admin():
        flash('Только Автор или Админ могут редактировать стихи! Авторизуйтесь.')
        return redirect(url_for('login'))

    conn = sqlite3.connect('poems.db')
    c = conn.cursor()

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        audio_url = request.form.get('audio_url')
        c.execute('UPDATE poems SET title = ?, content = ?, audio_url = ? WHERE id = ?',
                  (title, content, audio_url, poem_id))
        conn.commit()
        conn.close()
        flash('Стих успешно отредактирован!')
        return redirect(url_for('poems'))

    c.execute('SELECT title, content, audio_url FROM poems WHERE id = ?', (poem_id,))
    poem = c.fetchone()
    conn.close()
    if not poem:
        flash('Стих не найден!')
        return redirect(url_for('poems'))

    return render_template('edit_poem.html', poem_id=poem_id, title=poem[0], content=poem[1], audio_url=poem[2])

# Страница Новостей
@app.route('/news', methods=['GET', 'POST'])
def news():
    conn = sqlite3.connect('poems.db')
    c = conn.cursor()

    if request.method == 'POST' and is_author_or_admin():
        news_id = request.form.get('news_id')
        action = request.form.get('action')
        anchor = f'#news-{news_id}'

        if action == 'delete_news':
            c.execute('DELETE FROM news WHERE id = ?', (news_id,))
            conn.commit()
            flash('Новость удалена!')
            return redirect(url_for('news'))
        elif action == 'move_up':
            c.execute('SELECT position FROM news WHERE id = ?', (news_id,))
            pos = c.fetchone()[0]
            if pos > 1:
                c.execute('UPDATE news SET position = position + 1 WHERE position = ?', (pos - 1,))
                c.execute('UPDATE news SET position = position - 1 WHERE id = ?', (news_id,))
                conn.commit()
            return redirect(url_for('news') + anchor)
        elif action == 'move_down':
            c.execute('SELECT position FROM news WHERE id = ?', (news_id,))
            pos = c.fetchone()[0]
            c.execute('UPDATE news SET position = position - 1 WHERE position = ?', (pos + 1,))
            c.execute('UPDATE news SET position = position + 1 WHERE id = ?', (news_id,))
            conn.commit()
            return redirect(url_for('news') + anchor)

    c.execute('SELECT id, title, content, created_at, position FROM news ORDER BY position')
    news_items = c.fetchall()
    conn.close()
    return render_template('news.html', news_items=news_items)


@app.route('/add_news', methods=['GET', 'POST'])
def add_news():
    if not is_author_or_admin():
        flash('Только Автор или Админ могут добавлять новости! Авторизуйтесь.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        created_at = datetime.now().strftime('%d.%m.%Y в %H:%M')

        conn = sqlite3.connect('poems.db')
        c = conn.cursor()
        c.execute('SELECT MAX(position) FROM news')
        max_pos = c.fetchone()[0] or 0
        c.execute('INSERT INTO news (title, content, created_at, position) VALUES (?, ?, ?, ?)',
                  (title, content, created_at, max_pos + 1))
        conn.commit()
        conn.close()
        flash('Новость добавлена!')
        return redirect(url_for('news'))

    return render_template('add_news.html')


@app.route('/edit_news/<int:news_id>', methods=['GET', 'POST'])
def edit_news(news_id):
    if not is_author_or_admin():
        flash('Только Автор или Админ могут редактировать новости! Авторизуйтесь.')
        return redirect(url_for('login'))

    conn = sqlite3.connect('poems.db')
    c = conn.cursor()

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        c.execute('UPDATE news SET title = ?, content = ? WHERE id = ?', (title, content, news_id))
        conn.commit()
        conn.close()
        flash('Новость отредактирована!')
        return redirect(url_for('news'))

    c.execute('SELECT title, content FROM news WHERE id = ?', (news_id,))
    news = c.fetchone()
    conn.close()
    if not news:
        flash('Новость не найдена!')
        return redirect(url_for('news'))

    return render_template('edit_news.html', news_id=news_id, title=news[0], content=news[1])

# Страница обратной связи
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    conn = sqlite3.connect('poems.db')
    c = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'submit_feedback':
            username = request.form.get('username')
            message = request.form.get('message')
            created_at = datetime.now().strftime('%d.%m.%Y в %H:%M')
            c.execute('INSERT INTO feedback (username, message, created_at) VALUES (?, ?, ?)',
                      (username, message, created_at))
            flash('Сообщение отправлено!')
        elif action == 'clear_feedback' and is_author_or_admin():
            c.execute('DELETE FROM feedback')
            flash('Сообщения очищены!')
        conn.commit()

    messages = []
    if is_author_or_admin():
        c.execute('SELECT username, message, created_at FROM feedback ORDER BY id DESC')
        messages = c.fetchall()

    conn.close()
    return render_template('feedback.html', messages=messages)


# Страница смены пароля
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if not is_authenticated():
        flash('Авторизуйтесь для смены пароля.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        conn = sqlite3.connect('poems.db')
        c = conn.cursor()
        c.execute('SELECT password FROM users WHERE username = ?', (session['username'],))
        stored_password = c.fetchone()[0]
        if check_password_hash(stored_password, old_password):
            c.execute('UPDATE users SET password = ? WHERE username = ?',
                      (generate_password_hash(new_password), session['username']))
            conn.commit()
            flash('Пароль успешно изменён!')
        else:
            flash('Неверный старый пароль!')
        conn.close()

    return render_template('change_password.html')


# Страница авторизации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect('poems.db')
        c = conn.cursor()
        c.execute('SELECT password, role FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[0], password):
            session['username'] = username
            session['role'] = user[1]
            flash('Успешная авторизация!')
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль!')

    return render_template('login.html')


# Выход
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    flash('Вы вышли из системы.')
    return redirect(url_for('index'))


# Вспомогательная функция
def get_user_password(username):
    conn = sqlite3.connect('poems.db')
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE username = ?', (username,))
    password = c.fetchone()[0]
    conn.close()
    return password


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
    