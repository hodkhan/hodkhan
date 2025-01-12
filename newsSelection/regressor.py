from sklearn.feature_extraction.text import TfidfVectorizer
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
    user_news_conn = sqlite3.connect('./../userNews.db')
    usernames = list(user_news_conn.execute("SELECT username from Viewed"))
    usernames = list(map(lambda x: x[0], usernames))
    usernames = list(set(usernames))
    user_news_df = pd.read_sql_query("SELECT * FROM Viewed", user_news_conn)
    news_conn = sqlite3.connect('./../news.db')
    news_df = pd.read_sql_query("SELECT * FROM News", news_conn)

    for username in usernames:
        user_entries = user_news_df[user_news_df['username'] == username]
        if user_entries['isTrained'].all() == 1:
        # if False:
            print(f"\033[34mAll entries for {username} are already trained. continuing...\033[0m")
            continue
        else:
            user_news_df.loc[user_news_df['username'] == username, 'isTrained'] = 0
            news_ids_to_train = user_entries['newsId'].unique()

        valid_news_ids = news_df['id'].unique()
        user_news_df = user_news_df[user_news_df['newsId'].isin(valid_news_ids)]

        user_news_df = user_news_df.sort_values(by='star').drop_duplicates(subset=['username', 'newsId'], keep='last')

        filtered_news_df = news_df[news_df['id'].isin(news_ids_to_train)]

        merged_df = pd.merge(user_news_df, filtered_news_df, left_on='newsId', right_on='id')

        # Replace TF-IDF vectors with precomputed vectors from the database
        X_vectors = merged_df['vector'].apply(lambda x: np.fromstring(x, sep=',')).tolist()
        X_vectors = np.array(X_vectors)

        # news_agency_dummies = pd.get_dummies(merged_df['newsAgency'])

        # Combine vectors and dummy variables
        # X = np.hstack((X_vectors, news_agency_dummies.values))
        X = X_vectors
        y = merged_df['star'].values

        try:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            mlp = MLPRegressor(random_state=42, max_iter=500)
            mlp.fit(X_train, y_train)
        except Exception as e:
            print(f"\033[31mData not trained for {username}!\033[0m")
            continue
        
        y_pred = mlp.predict(X_test)

        mse = mean_squared_error(y_test, y_pred)
        print(f"\033[32m{username} Mean Squared Error: {mse}\033[0m")

        user_news_df.loc[user_news_df['username'] == username, 'isTrained'] = 1
        user_news_df.to_sql('Viewed', user_news_conn, if_exists='replace', index=False)

        news_agency_dummies_columns = news_agency_dummies.columns

        with open(f'../pickles/{username}_MLP.pkl', 'wb') as f:
            pickle.dump(mlp, f)
        # with open(f'../pickles/{username}_tfidfTitle.pkl', 'wb') as f:
        #     pickle.dump(tfidf_title, f)
        # with open(f'../pickles/{username}_tfidfAbs.pkl', 'wb') as f:
        #     pickle.dump(tfidf_abstract, f)
        with open(f'../pickles/{username}_agency.pkl', 'wb') as f:
            pickle.dump(news_agency_dummies_columns, f)


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

        except Exception as e:
            print(f"\033[31mAn error occurred!\033[0m")
            continue
        print(u"\033[35mEnd Regression!\033[0m")
        time.sleep(60)
