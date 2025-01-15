import sqlite3

# Connect to the old databases
news_conn = sqlite3.connect('./../news.db')
user_news_conn = sqlite3.connect('./../userNews.db')

# Connect to the new database
new_db_conn = sqlite3.connect('./../Database.db')

# Create tables in the new database
new_db_conn.execute("""
CREATE TABLE IF NOT EXISTS News (
    id TEXT PRIMARY KEY NOT NULL,
    siteId TEXT NOT NULL,
    newsAgency TEXT NOT NULL,
    title TEXT NOT NULL,
    abstract TEXT NOT NULL,
    topic TEXT NOT NULL,
    link TEXT NOT NULL,
    published TEXT NOT NULL,
    image TEXT NOT NULL,
    vector TEXT NOT NULL
);
""")

new_db_conn.execute("""
CREATE TABLE IF NOT EXISTS Viewed (
    username TEXT NOT NULL,
    newsId TEXT NOT NULL,
    star INTEGER NOT NULL,
    isTrained INTEGER NOT NULL
);
""")

# Migrate data from news.db
news_cursor = news_conn.cursor()
news_cursor.execute("SELECT * FROM News")
news_rows = news_cursor.fetchall()
new_db_conn.executemany("INSERT INTO News VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", news_rows)

# Migrate data from userNews.db
user_news_cursor = user_news_conn.cursor()
user_news_cursor.execute("SELECT * FROM Viewed")
viewed_rows = user_news_cursor.fetchall()
new_db_conn.executemany("INSERT INTO Viewed VALUES (?, ?, ?, ?)", viewed_rows)

# Commit and close connections
new_db_conn.commit()
news_conn.close()
user_news_conn.close()
new_db_conn.close()