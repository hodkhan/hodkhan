import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent.parent / 'db.sqlite3'

conn = sqlite3.connect(DB_PATH)

# find distinct usernames from app_interaction where type='view'
rows = conn.execute(
    "SELECT DISTINCT u.username "
    "FROM app_interaction i LEFT JOIN auth_user u ON i.user_id = u.id "
    "WHERE i.type = 'view'",
)

for row in rows:
    username = row[0]
    if not username:
        continue
    sql = (
        "DELETE FROM app_interaction WHERE user_id IN (SELECT id FROM auth_user "
        "WHERE username = ?) AND type = 'view'"
    )
    conn.execute(sql, (username,))

conn.commit()
conn.close()


# import sqlite3


# tables = ["""CREATE TABLE Viewed
# (username TEXT NOT NULL,
# newsId TEXT NOT NULL);""",
# """CREATE TABLE Interests
# (username TEXT NOT NULL,
# interest TEXT NOT NULL);"""]

# connection_obj = sqlite3.connect('./Database.db')
 
# # cursor object
# cursor_obj = connection_obj.cursor()
# for table in tables:
 
#     cursor_obj.execute(table)
     
# connection_obj.close()
