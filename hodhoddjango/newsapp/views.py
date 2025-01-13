from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect
from .models import News, Topic, NewsAgency, IFrame, API
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

module_path = os.path.abspath("../newsSelection/")
sys.path.append(module_path)

from main import record, rating, deleteRating, readRating


def news(requests):
    if requests.user.is_authenticated:
        username = requests.user.username
    else:
        username = "sampleUser"
    
    return render(requests, "index.html", context={"username": username})

def single(requests, id):
    news = News.objects.filter(id=id)
    if len(news) == 0:
        print("NotFound!")
        return render(requests, "404.html")
    news = news[0]
    n = {}
    n["id"] = news.id
    n["newsAgency"] = news.newsAgency.title
    n["title"] = news.title
    # n["abstract"] = thenews.abstract[:150] + "..."
    n["abstract"] = news.abstract
    date = int(news.published)
    date = datetime.datetime.fromtimestamp(date)
    date = pytz.timezone("GMT").localize(date)
    date = date.astimezone(pytz.timezone("Asia/Tehran"))
    jdate = jdatetime.datetime.fromgregorian(year=date.year,month=date.month,day=date.day, hour=date.hour, minute=date.minute, second=date.second)
    # if (int(now) - int(thenews.published)) > 345600:
    #     continue
    n["published"] = str(jdate)
    n["published"] = "".join(list(map(lambda x: x in "1234567890" and "۰۱۲۳۴۵۶۷۸۹"[int(x)] or x, n["published"])))
    topic = news.topic.title
    n["topic"] = topic
    n["image"] = news.image
    n["link"] = news.link
    new_data = {"title": n["title"], "abstract": n["abstract"], "newsAgency": n["newsAgency"]}
    # n['stars'] = str(predict_star(new_data, mlp, tfidf_title, tfidf_abstract, trained_news_agency_columns))

    return render(requests, "single.html", context={"news": n})

def iframe(requests, token):
    try:
        iframe = IFrame.objects.filter(token=token)[0]
    except:
        return JsonResponse({"404": "IFrame not found!"})

    username = iframe.user.username
    return render(requests, "iframe.html", context={"username": username})

def stream_articles(request, username, count = 0):
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

            
    print('loading pickles:',time.time()-start)

    oldnews = News.objects.filter(published__gte=int(time.time())-86400)

    lnews = []
    for e in oldnews:
        if flag:
            i = 0
        else:        
            # Convert the stored vector string back to a numpy array
            new_vector = np.fromstring(e.vector, sep=',')
            i = int(predict_star(new_vector, mlp))
        e.star = i
        lnews.append(e)

    lnews.sort(key=lambda x: x.star)
    lnews.reverse()

    x = []
    c = int(count)
    try:
        x = lnews[:int((c+1)*12)]
    except:
        x = lnews[:]
        
    print("newsLen:", len(lnews))
    print('loading news:',time.time()-start)
    def regressor(x):
        # now = time.time()
        allNews = []
        for thenews in x:
            n = {}
            n["id"] = thenews.id
            n["newsAgency"] = thenews.newsAgency.title
            n["title"] = thenews.title
            n["abstract"] = thenews.abstract
            date = int(thenews.published)
            date = datetime.datetime.fromtimestamp(date)
            date = pytz.timezone("GMT").localize(date)
            date = date.astimezone(pytz.timezone("Asia/Tehran"))
            jdate = jdatetime.datetime.fromgregorian(year=date.year,month=date.month,day=date.day, hour=date.hour, minute=date.minute, second=date.second)
            n["published"] = str(jdate)
            n["published"] = "".join(list(map(lambda x: x in "1234567890" and "۰۱۲۳۴۵۶۷۸۹"[int(x)] or x, n["published"])))
            topic = thenews.topic.title
            n["topic"] = topic
            n["image"] = thenews.image
            n["link"] = thenews.link
            if flag:
                n['stars'] = 0
            else:
                n['stars'] = thenews.star
            if len(n['abstract']) > 150:
                n['abstract'] = n['abstract'][:150] + '...'
            
            allNews.append(n)
        
        print('end regressing:',time.time()-start)

        print('end saving:',time.time()-start)
        return allNews

    response = regressor(x)
    return JsonResponse({'result': response})

def saveAllNewsRating(username, mlp, tfidf_title, tfidf_abstract, trained_news_agency_columns):
    deleteRating(username)
    news = News.objects.filter(published__gte=int(time.time())-345600)
    for i in news:
        new_data = {"title": i.title, "abstract": i.abstract, "newsAgency": i.newsAgency.title}
        star = int(predict_star(new_data, mlp, tfidf_title, tfidf_abstract, trained_news_agency_columns))
        rating(username, i.id, star)

def newsRating(request):
    result = dict(request.GET)
    n = float(result["result[n]"][0])
    id = result["result[id]"][0]
    if request.user.is_authenticated:
        username = request.user.username
    else:
        return JsonResponse({"404":"User Not Found"})
    record(username, id, n)
    return JsonResponse({})

def dbToDjango(requests):
    fromDbToDjango()
    return HttpResponse("OK")

def fromDbToDjango():

    conn = sqlite3.connect('./../news.db')

    x = list(News.objects.all().values("id"))
    ids = list(map(lambda x: x['id'], x))

    cursor = list(conn.execute(f"SELECT id, title, newsAgency, abstract, topic, link, published, image, vector from News where id not in ({', '.join(ids)})"))

    for row in cursor:
        try:
            newsAgency = NewsAgency.objects.filter(title=row[2])[0]
        except:
            newsAgency = NewsAgency(title=row[2])
            newsAgency.save()
        news = News(id=row[0], title=row[1], abstract=row[3], link=row[5], published=int(float(row[6])), image=row[7], newsAgency=newsAgency, vector=row[8])

        topic = row[4]
        oldtopics = Topic.objects.all()
        newtopics = []
        exist = list(filter(lambda x: x.title == topic, oldtopics))
        if (len(exist) > 0):
            exist = exist[0]
            newtopics = exist
        else:
            topic = Topic(title=topic)
            topic.save()
            newtopics = topic
        news.topic = newtopics

        try:
            news.save()
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

def api(requests, token):
    try:
        api = API.objects.filter(token=token)[0]
    except:
        return JsonResponse({"404": "API not found!"})
    
    username = api.user.username
    jsonNews = stream_articles(requests, username, 0)
    return HttpResponse(jsonNews.content , content_type="application/json")

def topic(requests, topic):
    news = News.objects.filter(topic__title=topic)
    if len(news) == 0:
        return render(requests, "404.html")
    news = news[:24]
    allNews = []
    for thenews in news:
        n = {}
        n["id"] = thenews.id
        n["newsAgency"] = thenews.newsAgency.title
        n["title"] = thenews.title
        n["abstract"] = thenews.abstract
        date = int(thenews.published)
        date = datetime.datetime.fromtimestamp(date)
        date = pytz.timezone("GMT").localize(date)
        date = date.astimezone(pytz.timezone("Asia/Tehran"))
        jdate = jdatetime.datetime.fromgregorian(year=date.year,month=date.month,day=date.day, hour=date.hour, minute=date.minute, second=date.second)
        n["published"] = str(jdate)
        n["published"] = "".join(list(map(lambda x: x in "1234567890" and "۰۱۲۳۴۵۶۷۸۹"[int(x)] or x, n["published"])))
        topic = thenews.topic.title
        n["topic"] = topic
        n["image"] = thenews.image
        n["link"] = thenews.link
        allNews.append(n)
    return render(requests, "newsList.html", context={"news": allNews})

def newsAgency(requests, newsAgency):
    news = News.objects.filter(newsAgency__title=newsAgency)
    if len(news) == 0:
        return render(requests, "404.html")
    news = news[:24]
    allNews = []
    for thenews in news:
        n = {}
        n["id"] = thenews.id
        n["newsAgency"] = thenews.newsAgency.title
        n["title"] = thenews.title
        n["abstract"] = thenews.abstract
        date = int(thenews.published)
        date = datetime.datetime.fromtimestamp(date)
        date = pytz.timezone("GMT").localize(date)
        date = date.astimezone(pytz.timezone("Asia/Tehran"))
        jdate = jdatetime.datetime.fromgregorian(year=date.year,month=date.month,day=date.day, hour=date.hour, minute=date.minute, second=date.second)
        n["published"] = str(jdate)
        n["published"] = "".join(list(map(lambda x: x in "1234567890" and "۰۱۲۳۴۵۶۷۸۹"[int(x)] or x, n["published"])))
        topic = thenews.topic.title
        n["topic"] = topic
        n["image"] = thenews.image
        n["link"] = thenews.link
        allNews.append(n)
    return render(requests, "newsList.html", context={"news": allNews})

def E404(requests, slug):
    return render(requests, "404.html")