import markdownify
import markdown
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from .models import Article, Keyword, Feed, Interaction
from django.shortcuts import render, redirect
from django.db.models import Q
import pandas as pd
import numpy as np
import jdatetime
import datetime
import sqlite3
import pickle
import time
import pytz
import json
import sys
import os

module_path = os.path.abspath("feed_creator/")
sys.path.append(module_path)

from main import record


def index(requests):
    if requests.user.is_authenticated:
        username = requests.user.username
    else:
        username = "sampleUser"

    topics = Keyword.objects.all()

    return render(requests, "index.html", context={"username": username, "topics": topics})


def privacy(requests):
    if requests.user.is_authenticated:
        username = requests.user.username
    else:
        username = "sampleUser"
    return render(requests, "privacy.html", context={"username": username})


def article(requests, id):
    article = Article.objects.filter(id=id)
    if len(article) == 0:
        print("NotFound!")
        return render(requests, "404.html")
    article = article[0]
    n = {}
    n["id"] = article.id
    n["feed"] = {"id": article.feed.id, "name": article.feed.name, "favicon": article.feed.favicon}
    n["title"] = article.title
    # n["abstract"] = thearticle.abstract[:150] + "..."
    n["abstract"] = article.abstract
    date = int(article.published)
    date = datetime.datetime.fromtimestamp(date)
    date = pytz.timezone("GMT").localize(date)
    date = date.astimezone(pytz.timezone("Asia/Tehran"))
    jdate = jdatetime.datetime.fromgregorian(year=date.year, month=date.month, day=date.day, hour=date.hour,
                                             minute=date.minute, second=date.second)
    # if (int(now) - int(thearticle.published)) > 345600:
    #     continue
    n["published"] = str(jdate)
    n["published"] = "".join(list(map(lambda x: x in "1234567890" and "۰۱۲۳۴۵۶۷۸۹"[int(x)] or x, n["published"])))
    n["image"] = article.cover
    n["link"] = article.link
    new_data = {"title": n["title"], "abstract": n["abstract"], "feed": n["feed"]}
    from app.management.commands.crawler_tool import fetch_and_process_html
    html_content = fetch_and_process_html(article.link)
    html_content.strip()
    n["html"] = html_content
    return render(requests, "article.html", context={"article": n})


def stream_articles(request, username, count=0):
    start = time.time()
    print('----------started----------')

    try:
        # Load the trained model
        with open(f'../pickles/{username}_MLP.pkl', 'rb') as f:
            mlp = pickle.load(f)
        flag = False
    except:
        flag = True
        mlp = None

    print('loading pickles:', time.time() - start)

    oldarticle = Article.objects.filter(published__gte=int(time.time()) - 86400)

    larticle = []
    for e in oldarticle:
        if flag:
            i = 0
        else:
            # Convert the stored vector string back to a numpy array
            new_vector = np.fromstring(e.vector, sep=',')
            i = int(predict_star(new_vector, mlp))
        e.star = i
        larticle.append(e)

    larticle.sort(key=lambda x: x.star)
    larticle.reverse()

    x = []
    c = int(count)
    try:
        x = larticle[:int((c + 1) * 12)]
    except:
        x = larticle[:]

    print("articleLen:", len(larticle))
    print('loading article:', time.time() - start)

    def regressor(x):
        # now = time.time()
        allArticle = []
        for thearticle in x:
            n = {}
            n["id"] = thearticle.id
            n["feed"] = {"id": thearticle.feed.id, "name": thearticle.feed.name, "favicon": thearticle.feed.favicon}
            n["title"] = thearticle.title
            n["abstract"] = thearticle.abstract
            date = int(thearticle.published)
            date = datetime.datetime.fromtimestamp(date)
            date = pytz.timezone("GMT").localize(date)
            date = date.astimezone(pytz.timezone("Asia/Tehran"))
            jdate = jdatetime.datetime.fromgregorian(year=date.year, month=date.month, day=date.day, hour=date.hour,
                                                     minute=date.minute, second=date.second)
            n["published"] = str(jdate)
            n["published"] = "".join(
                list(map(lambda x: x in "1234567890" and "۰۱۲۳۴۵۶۷۸۹"[int(x)] or x, n["published"])))
            n["image"] = thearticle.cover
            n["link"] = thearticle.link
            if flag:
                n['stars'] = 0
            else:
                n['stars'] = thearticle.star
            if len(n['abstract']) > 150:
                n['abstract'] = n['abstract'][:150] + '...'

            allArticle.append(n)

        print('end regressing:', time.time() - start)

        print('end saving:', time.time() - start)
        return allArticle

    response = regressor(x)
    return JsonResponse({'result': response})


def dbToDjango(requests):
    fromDbToDjango()
    return HttpResponse("OK")


def fromDbToDjango():
    conn = sqlite3.connect('./../Database.db')

    x = list(Article.objects.all().values("id"))
    ids = list(map(lambda x: x['id'], x))

    cursor = list(conn.execute(
        f"SELECT id, title, feed, abstract, topic, link, published, image, vector from Article where id not in ({', '.join(ids)})"))

    for row in cursor:
        try:
            feed = Feed.objects.filter(title=row[2])[0]
        except:
            feed = Feed(title=row[2])
            feed.save()
        article = Article(id=row[0], title=row[1], abstract=row[3], link=row[5], published=int(float(row[6])),
                          image=row[7], feed=feed, vector=row[8])

        topic = row[4]
        oldtopics = Keyword.objects.all()
        newtopics = []
        exist = list(filter(lambda x: x.title == topic, oldtopics))
        if (len(exist) > 0):
            exist = exist[0]
            newtopics = exist
        else:
            topic = Keyword(title=topic)
            topic.save()
            newtopics = topic
        article.keywords = newtopics

        try:
            article.save()
        except:
            print("Err, continue")
            continue


def predict_star(new_vector, mlp):
    """
    Predict the star rating using the precomputed vector and the trained model.
    """
    X_new = np.array([new_vector])
    predicted_ratings = mlp.predict(X_new)
    return predicted_ratings[0]


def topic(requests, topic):
    article = Article.objects.filter(topic__title=topic)
    if len(article) == 0:
        return render(requests, "404.html")
    article = article[:24]
    allArticle = []
    for thearticle in article:
        n = {}
        n["id"] = thearticle.id
        n["feed"] = {"id": thearticle.feed.id, "name": thearticle.feed.name, "favicon": thearticle.feed.favicon}
        n["title"] = thearticle.title
        n["abstract"] = thearticle.abstract
        date = int(thearticle.published)
        date = datetime.datetime.fromtimestamp(date)
        date = pytz.timezone("GMT").localize(date)
        date = date.astimezone(pytz.timezone("Asia/Tehran"))
        jdate = jdatetime.datetime.fromgregorian(year=date.year, month=date.month, day=date.day, hour=date.hour,
                                                 minute=date.minute, second=date.second)
        n["published"] = str(jdate)
        n["published"] = "".join(list(map(lambda x: x in "1234567890" and "۰۱۲۳۴۵۶۷۸۹"[int(x)] or x, n["published"])))
        n["image"] = thearticle.cover
        n["link"] = thearticle.link
        allArticle.append(n)
    return render(requests, "articleList.html", context={"article": allArticle})


def feed(requests, feed):
    article = Article.objects.filter(feed__title=feed)
    if len(article) == 0:
        return render(requests, "404.html")
    article = article[:24]
    allArticle = []
    for thearticle in article:
        n = {}
        n["id"] = thearticle.id
        n["feed"] = {"id": thearticle.feed.id, "name": thearticle.feed.name, "favicon": thearticle.feed.favicon}
        n["title"] = thearticle.title
        n["abstract"] = thearticle.abstract
        date = int(thearticle.published)
        date = datetime.datetime.fromtimestamp(date)
        date = pytz.timezone("GMT").localize(date)
        date = date.astimezone(pytz.timezone("Asia/Tehran"))
        jdate = jdatetime.datetime.fromgregorian(year=date.year, month=date.month, day=date.day, hour=date.hour,
                                                 minute=date.minute, second=date.second)
        n["published"] = str(jdate)
        n["published"] = "".join(list(map(lambda x: x in "1234567890" and "۰۱۲۳۴۵۶۷۸۹"[int(x)] or x, n["published"])))
        n["image"] = thearticle.cover
        n["link"] = thearticle.link
        allArticle.append(n)
    return render(requests, "articleList.html", context={"article": allArticle})


def E404(requests, slug):
    return render(requests, "404.html")


def search_suggestions(request):
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    # Search in article titles and get both title and id, ordered by published date
    suggestions = Article.objects.filter(
        Q(title__icontains=query)
    ).values('title', 'id', 'abstract').order_by('-published')[:5]

    # Convert QuerySet to list of dictionaries
    suggestions = list(suggestions)

    return JsonResponse({'suggestions': suggestions})


def search(request):
    query = request.GET.get('q', '').strip()

    if not query:
        return redirect('/')

    # Search in article titles
    article = Article.objects.filter(
        Q(title__icontains=query) | Q(abstract__icontains=query)
    ).order_by('-published')[:24]

    allArticle = []
    for thearticle in article:
        n = {}
        n["id"] = thearticle.id
        n["feed"] = {"id": thearticle.feed.id, "name": thearticle.feed.name, "favicon": thearticle.feed.favicon}

        n["title"] = thearticle.title
        n["abstract"] = thearticle.abstract
        date = int(thearticle.published)
        date = datetime.datetime.fromtimestamp(date)
        date = pytz.timezone("GMT").localize(date)
        date = date.astimezone(pytz.timezone("Asia/Tehran"))
        jdate = jdatetime.datetime.fromgregorian(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=date.hour,
            minute=date.minute,
            second=date.second
        )
        n["published"] = str(jdate)
        n["published"] = "".join(list(map(
            lambda x: x in "1234567890" and "۰۱۲۳۴۵۶۷۸۹"[int(x)] or x,
            n["published"]
        )))
        n["image"] = thearticle.cover
        n["link"] = thearticle.link
        allArticle.append(n)

    return render(request, "articleList.html", context={
        "articles": allArticle,
        "query": query,
        "count": str(len(allArticle)).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
    })


def getArticleContentView(request, url):
    from app.management.commands.crawler_tool import fetch_and_process_html
    html_content = fetch_and_process_html(url)
    html_content.strip()
    return html_content


def interaction(request):
    result = dict(request.GET)
    if request.user.is_authenticated:
        user = request.user
    else:
        return JsonResponse({"404": "User Not Found"})

    try:
        type_req = result["result[type]"][0]
        if type_req == "view":
            article = Article.objects.get(id=result["result[article]"][0])
            value = float(result["result[value]"][0])
            interaction = Interaction(article=article, user=user, type="view", value=value)
            interaction.save()
        elif type_req == "like":
            article = Article.objects.get(id=result["result[article]"][0])
            interaction = Interaction(article=article, user=user, type="like")
            interaction.save()
        elif type_req == "comment":
            pass
        elif type_req == "archive":
            pass
        elif type_req == "follow":
            pass
        else:
            return JsonResponse({"404": "Type Not Found"})
    except Exception as e:
        print("Error:", e)
        return JsonResponse({"400": "Bad Request"})

    return JsonResponse({"200": "OK"})
    # id = result["result[id]"][0]
    # n = float(result["result[n]"][0])
    # record(username, id, n)
