import sqlite3
import fasttext
import numpy as np

# Load FastText model
model_path = './../cc.fa.300.bin'  # مسیر مدل دانلودشده
fasttext_model = fasttext.load_model(model_path)

def vectorize_text(text):
    """Convert text to vector using FastText."""
    return fasttext_model.get_sentence_vector(text)

def update_vectors_in_db(db_path):
    """Update all rows in the database to include vectorized abstracts."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure "vector" column exists
    try:
        cursor.execute("ALTER TABLE News ADD COLUMN vector TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Fetch all rows without vectors
    cursor.execute("SELECT id, title, abstract FROM News WHERE vector IS NULL")
    rows = cursor.fetchall()

    for row in rows:
        news_id, title, abstract = row
        try:
            # Vectorize abstract
            string = title + ' ' + abstract
            vector = vectorize_text(string)
            vector_str = ','.join(map(str, vector))

            # Update row in the database
            cursor.execute("UPDATE News SET vector = ? WHERE id = ?", (vector_str, news_id))
            conn.commit()
            print(f"Updated vector for news ID: {news_id}")
        except Exception as e:
            print(f"Error updating vector for news ID {news_id}: {e}")
            continue

    conn.close()
    print("All vectors updated.")

if __name__ == "__main__":
    db_path = './../news.db'  # مسیر فایل دیتابیس
    update_vectors_in_db(db_path)
