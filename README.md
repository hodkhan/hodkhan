# HodKhan، Khabar Khan Solomon(Solomon's Newsreader)

* This is FastLoad version
HodHod is a website for displaying news according to people's interests


## Installation

* download from Github
```bash
git clone https://github.com/mahdiahmadi87/hodhod.git
```

* download Persian Fasttext Model
[Download](https://fasttext.cc/docs/en/crawl-vectors.html#models)

* Install requirements
```bash
pip install -r requirements.txt
```

* Migrate django
```bash
cd hodkhan
python3 manage.py migrate
```

* Create a superuser
```bash
python3 manage.py createsuperuser
```

* Create the Database
```python
import sqlite3
conn = sqlite3.connect('./Database.db')

conn.execute("""
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

conn.execute("""
CREATE TABLE IF NOT EXISTS Viewed (
    username TEXT NOT NULL,
    newsId TEXT NOT NULL,
    star INTEGER NOT NULL,
    isTrained INTEGER NOT NULL
);
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS Users (
    username TEXT NOT NULL,
    accuracy INTEGER NOT NULL
);
""")
conn.commit()
conn.close()
```


## Usage
* WebSite:
```bash
cd hodkhan
python3 manage.py runserver
```

* Crawler:
```bash
cd crawlers
python3 crawler.py
```

* Regressos:
```bash
cd newsSelection
python3 regressor.py
```


## Download for Android

you can download APK from this link:

[Download](https://github.com/mahdiahmadi87/hodhod/blob/fastLoad/hodhoddjango/hodkhan/app/static/files/base.apk "github path")

## License

[Apache](http://www.apache.org/licenses/)
