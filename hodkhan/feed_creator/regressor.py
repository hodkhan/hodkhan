# TfidfVectorizer was used previously; keep import commented for future use
# from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from typing import Optional
import pandas as pd
import numpy as np
import sqlite3
import signal
import pickle
import time
import math
from pathlib import Path

class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException()


def interest_score(
    like: int,
    R: float,
    F: float,
    *,
    # زمان‌ها (قابل تیون)
    r_bounce: float = 2.0,       # زیر این مقدار، حضور در صفحه را «بی‌اثر» فرض کن
    r_cap: float = 180.0,        # سقف تاثیر ماندن در صفحه (ثانیه)
    f_min: float = 1.0,          # زیر این مقدار در فید، بی‌اثر
    f_cap: float = 8.0,          # سقف تاثیر مکث فید (ثانیه)
    # وزن‌های پایه (قابل تیون)
    w_like: float = 0.50,
    w_read: float = 0.35,
    w_feed: float = 0.15,
    # تنظیم رفتار لایک‌نکردن یا زیاد لایک‌کردن
    user_like_rate: Optional[float] = None,  # نرخ لایکِ این کاربر (۰..۱)، اگر داری بده
    global_like_rate: float = 0.20,          # میانگین نرخ لایک محصول (۰..۱)
    like_weight_sensitivity: float = 0.5,    # حساسیت تنظیم وزن لایک نسبت به تفاوت نرخ کاربر و میانگین
    # جریمه‌ها/ترمیم‌ها
    shallow_like_penalty: float = 0.70,      # اگر لایک ولی تعامل خیلی کم، این ضریب به ترم لایک ضرب می‌شود
    no_like_high_engagement_discount: float = 0.05  # اگر لایک نکرد ولی تعامل زیاد و کاربر معمولاً اهل لایک است، کمی کسر کن
) -> float:
    """
    محاسبه امتیاز علاقه کاربر به خبر در بازه [1..10].

    like: 0 یا 1
    R: ثانیه ماندن در صفحه خبر
    F: ثانیه مکث روی کارت خبر در فید

    Tips:
    - اگر user_like_rate را نداری، خالی بگذار.
    - r_cap و f_cap را می‌توانی به صدک‌های 90/95 دیتای واقعی‌ات تنظیم کنی.
    """


    R_eff = max(0.0, R - r_bounce)
    r = 0.0 if r_cap <= 0 else min(1.0, math.log1p(R_eff) / math.log1p(max(1e-9, r_cap)))
    if F < f_min:
        f = 0.0
    else:
        f = 1.0 if F >= f_cap else (F - f_min) / max(1e-9, (f_cap - f_min))

    adj_w_like = w_like
    if user_like_rate is not None:
        baseline = max(1e-6, global_like_rate)
        delta = (user_like_rate - global_like_rate) / baseline
        lam = 1.0 + like_weight_sensitivity * delta
        lam = max(0.5, min(1.5, lam))
        adj_w_like = w_like * lam

    like_term = adj_w_like * (1 if like else 0)
    read_term = w_read * r
    feed_term = w_feed * f

    if like == 1 and (r < 0.1 and f < 0.1):
        like_term *= shallow_like_penalty

    if like == 0 and (r > 0.6 or f > 0.6) and (user_like_rate is not None) and (user_like_rate > global_like_rate):
        read_term = max(0.0, read_term - no_like_high_engagement_discount * w_read)
        feed_term = max(0.0, feed_term - no_like_high_engagement_discount * w_feed)

    raw = like_term + read_term + feed_term
    raw = max(0.0, min(1.0, raw)) 
    score = 1.0 + 9.0 * raw

    return round(score, 2)


def regression():
    # use the project's main sqlite DB instead of the local Database.db
    DB_PATH = Path(__file__).resolve().parent.parent / 'db.sqlite3'
    conn = sqlite3.connect(DB_PATH)
    # Read interactions of type 'view' and map them to the legacy Viewed schema
    # We'll produce a DataFrame with columns: username, newsId, star, isTrained
    interactions_q = (
        "SELECT i.id, u.username as username, i.article_id as newsId, "
        "i.is_trained as isTrained, i.type as type, i.value as value, i.created_at as created, n.vector "  # Removed 'cc'
        "FROM app_interaction i "
        "LEFT JOIN auth_user u ON i.user_id = u.id "
        "LEFT JOIN app_article n ON i.article_id = n.id "
        # "WHERE i.type = 'view'"
    )

    try:
        user_news_df = pd.read_sql_query(interactions_q, conn)
        news_df = pd.read_sql_query("SELECT * FROM app_article", conn)
    except Exception as e:
        print(f"\033[31mDatabase error: {e}\033[0m")
        return

    # build distinct usernames list
    if 'username' in user_news_df.columns:
        usernames = user_news_df['username'].dropna().unique().tolist()
    else:
        usernames = []

    for username in usernames:
        user_entries = user_news_df[user_news_df['username'] == username]

        # check if all entries already trained
        if not user_entries.empty and user_entries['isTrained'].all():
            print(
                "\033[34mAll entries already trained for",
                username,
                "\033[0m",
            )
            continue



        # mark entries as not trained before training
        conn.execute(
            "UPDATE app_interaction SET is_trained = 0 WHERE type = 'view' "
            "AND user_id IN (SELECT id FROM auth_user WHERE username = ?)",
            (username,),
        )

        news_ids_to_train = user_entries['newsId'].dropna().unique()
        valid_news_ids = news_df['id'].unique()



        user_news_df_filtered = (
            user_entries[user_entries['newsId'].isin(valid_news_ids)]
        )

        
        # deduplicate keeping last  
        user_news_df_filtered = (
            user_news_df_filtered.sort_values(by='created')
            .drop_duplicates(subset=['username', 'newsId', "type"], keep='last')
        )

        # Select only id and vector from news_df to avoid column conflicts during merge
        filtered_news_df = news_df.loc[news_df['id'].isin(news_ids_to_train), ['id', 'vector']]

        if filtered_news_df.empty or user_news_df_filtered.empty:
            print(f"\033[31mNot enough data to train for {username}\033[0m")
            continue

        # user_news_df_filtered already has a vector column, we don't need to merge it again.
        # Let's just use the vectors from user_news_df_filtered.
        # We need to group by newsId to get one vector per news item.
        merged_df = user_news_df_filtered.drop_duplicates(subset=['newsId']).copy()


        # Filter out rows with NULL vectors and convert vectors to numpy arrays
        merged_df = merged_df.dropna(subset=['vector'])
        try:
            # Convert vector strings to numpy arrays
            def convert_vector(vec_str):
                try:
                    if not isinstance(vec_str, str):
                        return None
                    # Clean the string and split
                    cleaned = vec_str.strip().rstrip(',')
                    numbers = [float(x) for x in cleaned.split(',')]
                    return np.array(numbers)
                except:
                    return None

            # Apply conversion and show debug info
            print("Processing vectors for", username)
            print("Vector column type:", merged_df['vector'].dtype)
            print("First vector raw:", merged_df['vector'].iloc[0] if not merged_df.empty else "No data")
            
            X_vectors = merged_df['vector'].apply(convert_vector)
            X_vectors = X_vectors[X_vectors.notna()]
            
            if len(X_vectors) == 0:
                print(f"\033[31mNo valid vectors found for {username}\033[0m")
                continue
            
            # Stack vectors into array
            X = np.vstack(X_vectors.values)
            print(f"Processed {len(X_vectors)} vectors with shape {X.shape}")
            
            # Update news_ids_to_train to match filtered data
            news_ids_to_train = merged_df['newsId'].values

        except Exception as e:
            print(f"\033[31mError processing vectors for {username}:\033[0m")
            print(f"Error details: {str(e)}")
            print(f"Vector sample: {merged_df['vector'].iloc[0] if not merged_df.empty else 'No data'}")
            continue

        # Calculate interest scores for each news item
        y = []
        for news_id in news_ids_to_train:
            # Get interactions for this news
            news_interactions = user_news_df_filtered[user_news_df_filtered['newsId'] == news_id]
            
            # Get like status (1 if like interaction exists, 0 otherwise)
            like = 1 if 'like' in news_interactions['type'].values else 0
            
            # Get read time (value if read interaction exists, 0 otherwise)
            read_interaction = news_interactions[news_interactions['type'] == 'read']
            R = float(read_interaction['value'].iloc[0]) if not read_interaction.empty else 0.0
            
            # Get view time (value if view interaction exists, 0 otherwise) 
            view_interaction = news_interactions[news_interactions['type'] == 'view']
            F = float(view_interaction['value'].iloc[0]) if not view_interaction.empty else 0.0
            
            # Calculate interest score
            score = interest_score(like=like, R=R, F=F)
            y.append(score)

        y = np.array(y)

        # Ensure we have enough data to split for training and testing
        if len(X) < 2 or len(y) < 2:
            print(f"\033[31mNot enough data points to train for {username} (found {len(X)}). Skipping.\033[0m")
            continue

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.1, random_state=42
            )

            mlp = MLPRegressor(random_state=42, max_iter=500)
            mlp.fit(X_train, y_train)
        except Exception as e:
            print(f"\033[31mData not trained for {username}! Error: {e}\033[0m")
            continue

        y_pred = mlp.predict(X_test)

        mse = mean_squared_error(y_test, y_pred)
        print(f"\033[32m{username} Mean Squared Error: {mse}\033[0m")

        # mark interactions as trained for this user
        conn.execute(
            "UPDATE app_interaction SET is_trained = 1 WHERE type = 'view' "
            "AND user_id IN (SELECT id FROM auth_user WHERE username = ?)",
            (username,),
        )

        # Ensure the pickles directory exists before saving the model
        pickles_dir = Path(__file__).resolve().parent.parent / 'pickles'
        pickles_dir.mkdir(parents=True, exist_ok=True)

        with open(pickles_dir / f'{username}_MLP.pkl', 'wb') as f:
            pickle.dump(mlp, f)
        # with open(f'../pickles/{username}_tfidfTitle.pkl', 'wb') as f:
        #     pickle.dump(tfidf_title, f)
        # with open(f'../pickles/{username}_tfidfAbs.pkl', 'wb') as f:
        #     pickle.dump(tfidf_abstract, f)
        # with open(f'../pickles/{username}_agency.pkl', 'wb') as f:
        #     pickle.dump(news_agency_dummies_columns, f)


if __name__ == "__main__":
    while True:
        print(u"\033[34mRegressor Is Running!\033[0m")
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(60)
            
            regression()

            signal.alarm(0)

        except TimeoutException:
            print("\033[31mExecution time took too long!\033[0m")
            continue

        except TimeoutException:
            # allow outer loop to handle timeout
            raise
        except Exception as e:
            print("\033[31mAn error occurred!\033[0m")
            print(e)
            continue
        print(u"\033[35mEnd Regression!\033[0m")
        time.sleep(60)
