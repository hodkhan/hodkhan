import feedparser
import requests 
import signal
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


def crawler():
    feed = feedparser.parse("https://gadgetnews.net/feed/")
    # feed = feedparser.parse("./download.rss")

    conn = sqlite3.connect('./../news.db')

    siteIds = list(conn.execute("SELECT siteId from News"))
    siteIds = list(map(lambda x: x[0], siteIds))
    ids = list(conn.execute("SELECT id from News"))
    ids = list(map(lambda x: x[0], ids))
    ids = list(filter(lambda x: x[:2] == "15", ids))
    ids = list(map(int, ids))

    cursor = conn.cursor() 
    i = 1
    for entry in feed.entries:  
        try:        
            siteId = entry.id
            x = re.findall(r"\?p=\d{6,}", siteId)
            siteId = x[0][3:]
            if (siteId in siteIds):
                print("Exist")
                continue

            try:
                id = max(ids) + i
                i += 1
            except:
                print("ID Not found! generated to 35100001")
                id = "35100001"
                ids = [35100001]


            pub = entry.published_parsed
            pub = time.mktime(pub)

            abstract = entry.summary
            abstract = re.findall(r"\<p\>[^\<]*\<\/p\>", abstract)[0][3:-6]
            print("\n" + abstract + ":")
            topic = classifier(str(entry.title) + "\n" + abstract)
            if topic == "استان‌ها":
                topic = "ایران"
            print(topic)

            
            image = entry.summary

            image = re.findall(r'src="https://.*wp-content/uploads/.*\.jpg"', image)[0][5:-1]

            cursor.execute(f"INSERT INTO News VALUES ('{id}', '{siteId}', 'GadgetNews', '{entry.title}', '{abstract}', '{topic}',  '{entry.link}', '{pub}', '{image}')")
            conn.commit() 
            print("Added")
        except Exception as e:
            i -= 1
            continue
        

    
    print("commited")
    conn.close()
    try:
        if i > 1:
            print(requests.get("http://hodkhan.ir/dbToDjango/"))
    except:
        return


if __name__ == "__main__":
    while True:
        print(u"\033[34mGadgetNews Crawler Is Running!\033[0m")
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)
            
            crawler()
            
            signal.alarm(0)

        except TimeoutException:
            print("\033[31mExecution time took too long!\033[0m")
            continue

        except Exception as e:
            print(f"\033[31mAn error occurred!\033[0m")
            continue
        print(u"\033[35mEnd Crawling!\033[0m")
        time.sleep(1)



"""{
  title: '208 هزار میلیارد تومان، زیان انباشته خودروسازان در ایران!',
  title_detail: {
    type: 'text/plain',
    language: null,
    base: 'https://gadgetnews.net/feed/',
    value: '208 هزار میلیارد تومان، زیان انباشته خودروسازان در ایران!'
  },
  links: [
    {
      rel: 'alternate',
      type: 'text/html',
      href: 'https://gadgetnews.net/933926/accumulated-losses-automobile-manufacturers-iran/'
    }
  ],
  link: 'https://gadgetnews.net/933926/accumulated-losses-automobile-manufacturers-iran/',
  comments: 'https://gadgetnews.net/933926/accumulated-losses-automobile-manufacturers-iran/#respond',
  authors: [ { name: 'پوریا هاشم پور' } ],
  author: 'پوریا هاشم پور',
  author_detail: { name: 'پوریا هاشم پور' },
  published: 'Thu, 28 Nov 2024 08:08:26 +0000',
  published_parsed: 'time',
  tags: [
    { term: 'خودرو', scheme: null, label: null },
    { term: 'خودرو داخلی', scheme: null, label: null },
    { term: 'وسایل نقلیه', scheme: null, label: null },
    { term: 'ایران خودرو', scheme: null, label: null },
    { term: 'پارس خودرو', scheme: null, label: null },
    { term: 'خودروسازان داخلی', scheme: null, label: null },
    { term: 'سایپا', scheme: null, label: null }
  ],
  id: 'https://gadgetnews.net/?p=933926',
  guidislink: false,
  summary: '<p><img alt="زیان انباشته خودروسازان" class="attachment-post-thumbnail size-post-thumbnail wp-post-image" height="330" src="https://gadgetnews.net/wp-content/uploads/2024/11/Accumulated-losses-of-automobile-manufacturers-5.jpg" width="620" /></p>\n' +
    '<p>جدیدترین صورت های مالی منتشر شده از خودروسازان ایرانی در مهر ماه ۱۴۰۳, حاکی از زیان انباشته ۲۰۸ هزار میلیارد تومانی است. از سال ۱۳۹۱ که شورای رقابت مطابق با ماده ۵۸ قانون اجرای سیستم های کلی اصل ۴۴ قانون اساسی، به‌عنوان نهاد نظارتی بر قیمت‌گذاری خودروها انتخاب شد، همواره شاهد تنش و رقابت در ...</p>\n' +
    '<p>The post <a href="https://gadgetnews.net/933926/accumulated-losses-automobile-manufacturers-iran/">208 هزار میلیارد تومان، زیان انباشته خودروسازان در ایران!</a>\t appeared first on <a href="https://gadgetnews.net">گجت نیوز</a>\t.</p>',
  summary_detail: {
    type: 'text/html',
    language: null,
    base: 'https://gadgetnews.net/feed/',
    value: '<p><img alt="زیان انباشته خودروسازان" class="attachment-post-thumbnail size-post-thumbnail wp-post-image" height="330" src="https://gadgetnews.net/wp-content/uploads/2024/11/Accumulated-losses-of-automobile-manufacturers-5.jpg" width="620" /></p>\n' +
      '<p>جدیدترین صورت های مالی منتشر شده از خودروسازان ایرانی در مهر ماه ۱۴۰۳, حاکی از زیان انباشته ۲۰۸ هزار میلیارد تومانی است. از سال ۱۳۹۱ که شورای رقابت مطابق با ماده ۵۸ قانون اجرای سیستم های کلی اصل ۴۴ قانون اساسی، به‌عنوان نهاد نظارتی بر قیمت‌گذاری خودروها انتخاب شد، همواره شاهد تنش و رقابت در ...</p>\n' +
      '<p>The post <a href="https://gadgetnews.net/933926/accumulated-losses-automobile-manufacturers-iran/">208 هزار میلیارد تومان، زیان انباشته خودروسازان در ایران!</a>\t appeared first on <a href="https://gadgetnews.net">گجت نیوز</a>\t.</p>'
  },
  wfw_commentrss: '',
  slash_comments: '0'
}
"""