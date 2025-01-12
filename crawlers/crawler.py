import compress_fasttext
import feedparser
import requests 
import signal
import fasttext
import sqlite3
import time
import sys
import os
import re

module_path = os.path.abspath("../classification/")
sys.path.append(module_path)

from main import classifier

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException()

# Load FastText model
# model_path = './../cc.fa.300.bin'  # مسیر مدل دانلودشده
# fasttext_model = fasttext.load_model(model_path)
model_path = './../cc.fa.300.q.bin'  # مسیر مدل دانلودشده
fasttext_model = compress_fasttext.models.CompressedFastTextKeyedVectors.load(model_path)



def vectorize_text(text):
    """Convert text to vector using FastText."""
    return fasttext_model.get_sentence_vector(text)

def extract_entry_data(entry, source):
    """Extract relevant data based on the source (Zoomit, Tasnim, etc.)."""
    if source == "Zoomit":
        site_id = re.findall(r"\/\d{6,}", entry.id)[0][1:]
        pub_date = time.mktime(entry.published_parsed)
        abstract = re.findall(r"\<p\>.*\<\/p\>", entry.summary)[0][3:-4]
        image = re.findall(r'src="https://.*q=\d+"', entry.summary)[0][5:-1]
    elif source == "TasnimNews":
        site_id = entry.id[-7:]
        pub_date = time.mktime(entry.published_parsed)
        abstract = entry.summary
        image = entry.media_thumbnail[0]["url"]
    elif source == "KhabarVarzeshi":
        site_id = re.findall(r"\/\d{6,}", entry.id)[0][1:]
        pub_date = time.mktime(entry.published_parsed)
        abstract = entry.summary
        image = entry.links[1].href
    elif source == "GadgetNews":
        site_id = re.findall(r"\?p=\d{6,}", entry.id)[0][3:]
        pub_date = time.mktime(entry.published_parsed)
        abstract = re.findall(r"\<p\>[^\<]*\<\/p\>", entry.summary)[0][3:-6]
        image = re.findall(r'src="https://.*wp-content/uploads/.*\.jpg"', entry.summary)[0][5:-1]
    elif source == "Etemad":
        site_id = re.findall(r"\/news-\d+", entry.link)[0][6:]
        pub_date = time.mktime(entry.published_parsed)
        abstract = re.findall(r"\<div\>.*\<\/div\>", entry.summary)[0][5:-6]
        image = re.findall(r'src="https://.*"', entry.summary)[0][5:-1]
    elif source == "donyaEEghtesad":
        site_id = re.findall(r"\/\d{3,}", entry.id)[0][1:]
        pub_date = time.mktime(entry.published_parsed)
        abstract = re.findall(r"\<div\>.*\<\/div\>", entry.summary)[0][5:-6]
        image = re.findall(r'src="https://.*"', entry.summary)[0][5:-1]
    else:
        raise ValueError(f"Unknown source: {source}")

    return {
        "site_id": site_id,
        "pub_date": pub_date,
        "abstract": abstract,
        "image": image
    }

def crawl_and_store(feed_url, source_name, conn, cursor):
    """Fetch and store news from a single RSS feed."""
    feed = feedparser.parse(feed_url)

    # Retrieve existing site IDs to avoid duplicates
    existing_site_ids = list(cursor.execute("SELECT siteId from News"))
    existing_site_ids = set(map(lambda x: x[0], existing_site_ids))

    try:
        # Generate new unique IDs
        existing_ids = list(cursor.execute("SELECT id from News"))
        existing_ids = list(map(lambda x: int(x[0]), existing_ids))
        d = {"Zoomit": "15", "TasnimNews": "10", "KhabarVarzeshi": "20", "GadgetNews": "35", "Etemad": "25", "donyaEEghtesad": "30"}
        new_id_base = int(f"{d[source_name]}100000") 
        new_id = max(existing_ids, default=new_id_base)
        F = new_id
    except:
        print("Err while generating id")
        return

    for entry in feed.entries:
        try:
            data = extract_entry_data(entry, source_name)
            if data["site_id"] in existing_site_ids:
                print(f"Entry already exists for {source_name}: {data['site_id']}")
                continue

            # Classify topic
            topic = classifier(f"{entry.title}\n{data['abstract']}")
            if topic == "استان‌ها":
                topic = "ایران"

            # Vectorize abstract
            vector = vectorize_text(f"{entry.title} {data['abstract']}")
            vector_str = ','.join(map(str, vector))

            # Insert into database
            new_id += 1
            cursor.execute(f"""
                INSERT INTO News
                (id, siteId, newsAgency, title, abstract, topic, link, published, image, vector)
                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_id, data["site_id"], source_name, entry.title, data["abstract"], topic,
                  entry.link, data["pub_date"], data["image"], vector_str))
            conn.commit()
            print(f"Added news from {source_name}: {entry.title}")
        except Exception as e:
            print(f"Error processing entry from {source_name}: {e}")
            continue
    if F == new_id:
        print(f"No new news found from {source_name}.")
    else:
        print(requests.get("http://hodkhan.ir/dbToDjango/"))
    
    
if __name__ == "__main__":
    # Define RSS feeds
    rss_feeds = {
        "Zoomit": "https://www.zoomit.ir/feed/",
        "TasnimNews": "https://www.tasnimnews.com/fa/rss/feed/0/8/0/%D8%A2%D8%AE%D8%B1%DB%8C%D9%86-%D8%AE%D8%A8%D8%B1%D9%87%D8%A7%DB%8C-%D8%B1%D9%88%D8%B2",
        "KhabarVarzeshi": "https://www.khabarvarzeshi.com/rss",
        "GadgetNews": "https://gadgetnews.net/feed/",
        "Etemad": "https://www.etemadonline.com/feeds/",
        "donyaEEghtesad": "https://donya-e-eqtesad.com/feeds/"
    }

    # Connect to the database
    conn = sqlite3.connect('./../news.db')
    cursor = conn.cursor()

    # # Add "vector" column if not exists
    # try:
    #     cursor.execute("ALTER TABLE News ADD COLUMN vector TEXT")
    # except sqlite3.OperationalError:
    #     pass  # Column already exists

    # # Crawl each RSS feed
    # for source, url in rss_feeds.items():
    #     print(f"Processing RSS feed from {source}...")
    #     crawl_and_store(url, source, conn, cursor)

    # conn.close()
    # print("All RSS feeds processed.")


    while True:
        print(u"\033[34mCrawler Is Running!\033[0m")
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(300)
            
            for source, url in rss_feeds.items():
                print(f"Processing RSS feed from {source}...")
                crawl_and_store(url, source, conn, cursor)   

            signal.alarm(0)

        except TimeoutException:
            print("\033[31mExecution time took too long!\033[0m")
            continue

        except Exception as e:
            print(f"\033[31mAn error occurred!\033[0m", "\n", e)
            continue
        print(u"\033[35mEnd Crawling!\033[0m")
        time.sleep(1)