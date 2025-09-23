# TfidfVectorizer was used previously; keep import commented for future use
# from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import pandas as pd
import numpy as np
import sqlite3
import signal
import pickle
import time

class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException()


def regression():
    # use the project's main sqlite DB instead of the local Database.db
    from pathlib import Path
    DB_PATH = Path(__file__).resolve().parent.parent.parent / 'db.sqlite3'
    conn = sqlite3.connect(DB_PATH)

    # Read interactions of type 'view' and map them to the legacy Viewed schema
    # We'll produce a DataFrame with columns: username, newsId, star, isTrained
    interactions_q = (
        "SELECT i.id, u.username as username, i.article_id as newsId, "
        "i.star as star, i.is_trained as isTrained, n.vector "
        "FROM app_interaction i "
        "LEFT JOIN auth_user u ON i.user_id = u.id "
        "LEFT JOIN app_article n ON i.article_id = n.id "
        "WHERE i.type = 'view'"
    )

    user_news_df = pd.read_sql_query(interactions_q, conn)
    news_df = pd.read_sql_query("SELECT * FROM app_article", conn)

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

        # deduplicate keeping last by star
        user_news_df_filtered = (
            user_news_df_filtered.sort_values(by='star')
            .drop_duplicates(subset=['username', 'newsId'], keep='last')
        )

        filtered_news_df = news_df[news_df['id'].isin(news_ids_to_train)]

        if filtered_news_df.empty or user_news_df_filtered.empty:
            print(f"\033[31mNot enough data to train for {username}\033[0m")
            continue

        merged_df = pd.merge(
            user_news_df_filtered,
            filtered_news_df,
            left_on='newsId',
            right_on='id',
        )

        # Replace TF-IDF vectors with precomputed vectors from the database
        X_vectors = merged_df['vector'].apply(
            lambda x: np.fromstring(x, sep=',')
        )
        X = np.vstack(X_vectors.values)
        y = merged_df['star'].values

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            mlp = MLPRegressor(random_state=42, max_iter=500)
            mlp.fit(X_train, y_train)
        except Exception:
            print(f"\033[31mData not trained for {username}!\033[0m")
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

        with open(f'../pickles/{username}_MLP.pkl', 'wb') as f:
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
        except Exception:
            print("\033[31mAn error occurred!\033[0m")
            continue
        print(u"\033[35mEnd Regression!\033[0m")
        time.sleep(60)
