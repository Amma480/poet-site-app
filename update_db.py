import sqlite3

conn = sqlite3.connect('poems.db')
c = conn.cursor()
c.execute('ALTER TABLE feedback ADD COLUMN created_at TEXT')
conn.commit()
conn.close()
print("Столбец created_at добавлен в таблицу feedback")