from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from app.models import Article, Feed
from django.shortcuts import render, redirect
from .forms import SignupForm, LoginForm
import sqlite3
import os


def user_signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect('/')
            else:
                return redirect('login')
        else:
            errors = str(form.errors)
            d = {
                "A user with that username already exists.": "حسابی با این نام کاربری قبلا وجود دارد!",
                "The two password fields didn’t match.": "تکرار رمز عبور، اشتباه وارد شده است!",
                "This password is too short. It must contain at least 8 characters.": "رمز عبور کوتاه است، حداقل متشکل از ۸ حرف باید باشد!",
                "This password is too common.": "رمز عبور خیلی رایج است!",
                "This password is entirely numeric.": "رمز عبور کاملا از اعداد است!",
            }
            error = ""
            for key in d.keys():
                if key in errors:
                    error = d[key]
            if error == "":
                error = form.errors
            return render(request, 'signup.html', {'form': form, 'status': error})
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form, 'status': True})


def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect('/')
            else:
                return render(request, 'login.html', {'form': form, "status": False})
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form, "status": True})


@login_required(login_url='/account/login')
def user_logout(request):
    logout(request)
    return redirect('/')


def privacy(requests):
    return render(requests, "privacy.html")


def terms(requests):
    return render(requests, "terms.html")


def csrf_failure(requests, reason=""):
    return redirect('/')


@login_required(login_url='/account/login')
def account(requests):
    article = len(Article.objects.all())
    feed = len(Feed.objects.all())
    from pathlib import Path
    DB_PATH = Path(__file__).resolve().parent.parent / 'db.sqlite3'
    conn = sqlite3.connect(DB_PATH)
    q = (
        "SELECT i.article_id FROM app_interaction i "
        "LEFT JOIN auth_user u ON i.user_id = u.id "
        "WHERE u.username = ? AND i.type = 'read' OR i.type = 'view'"
    )
    viewed = conn.execute(q, (requests.user.username,))
    viewed = len(viewed.fetchall())
    q = (
        "SELECT i.article_id FROM app_interaction i "
        "LEFT JOIN auth_user u ON i.user_id = u.id "
        "WHERE u.username = ? AND i.type = 'like'"
    )
    liked = conn.execute(q, (requests.user.username,))
    liked = len(liked.fetchall())
    return render(
        requests,
        "account.html",
        context={
            "viewed": viewed,
            "liked": liked
        },
    )


@login_required(login_url='/account/login')
def deleteFeed(requests):
    username = requests.user.username
    from pathlib import Path
    DB_PATH = Path(__file__).resolve().parent.parent / 'db.sqlite3'
    conn = sqlite3.connect(DB_PATH)
    sql = (
        "DELETE FROM app_interaction WHERE user_id IN (SELECT id FROM auth_user "
        "WHERE username = ?) "
        "AND type = 'view'"
    )
    conn.execute(sql, (username,))
    conn.commit()
    conn.close()
    if os.path.exists(f"./../pickles/{username}_MLP.pkl"):
        # os.remove(f"./../pickles/{username}_agency.pkl")
        os.remove(f"./../pickles/{username}_MLP.pkl")
        # os.remove(f"./../pickles/{username}_tfidfAbs.pkl")
        # os.remove(f"./../pickles/{username}_tfidfTitle.pkl")
    return redirect('/account/')
