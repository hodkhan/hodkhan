import sqlite3

def record(username, news_id, n):
    conn = sqlite3.connect('./../Database.db')
    cursor = conn.cursor() 
    cursor.execute(f"INSERT INTO Viewed VALUES ('{username}', '{news_id}', {n}, 0)")
    conn.commit()   
    conn.close()

"""CREATE TABLE Viewed
(username TEXT NOT NULL,
newsId TEXT NOT NULL,
star INTEGER NOT NULL,
isTrained INTEGER NOT NULL);"""

"""CREATE TABLE Interests
(username TEXT NOT NULL,
interest TEXT NOT NULL);"""

"""CREATE TABLE Rating
(username TEXT NOT NULL,
newsId TEXT NOT NULL,
rate INTEGER NOT NULL);"""
