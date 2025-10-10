from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination 
from django.db.models import Q
from django.db import transaction
from .models import KeyWordTable, SearchKeyWord

from app.models import Article
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import AgencyKey
import datetime
import pytz
import jdatetime

def build_whole_word_query(field_name, words):
    query = Q()
    for word in words:
        w = word.strip()
        if not w:
            continue
        base = Q(**{f"{field_name}__iexact": w})
        start = Q(**{f"{field_name}__istartswith": w + " "})
        end = Q(**{f"{field_name}__iendswith": " " + w})
        middle = Q(**{f"{field_name}__icontains": " " + w + " "})
        # Add common punctuation variants
        punct_variants = [
            Q(**{f"{field_name}__icontains": f" {w},"}),
            Q(**{f"{field_name}__icontains": f" {w}."}),
            Q(**{f"{field_name}__icontains": f",{w} "}),
            Q(**{f"{field_name}__icontains": f".{w} "}),
            Q(**{f"{field_name}__iendswith": f" {w},"}),
            Q(**{f"{field_name}__iendswith": f" {w}."}),
        ]
        q = base | start | end | middle
        for pv in punct_variants:
            q |= pv
        query |= q
    return query


def convert_timestamp_to_jalali(timestamp):
    if timestamp is None:
        return None
    # Convert Unix timestamp to GMT datetime
    dt_gmt = datetime.datetime.fromtimestamp(int(timestamp), tz=pytz.UTC)
    # Convert to Iran time
    tehran_tz = pytz.timezone("Asia/Tehran")
    dt_tehran = dt_gmt.astimezone(tehran_tz)
    # Convert to Jalali datetime
    jdt = jdatetime.datetime.fromgregorian(
        year=dt_tehran.year,
        month=dt_tehran.month,
        day=dt_tehran.day,
        hour=dt_tehran.hour,
        minute=dt_tehran.minute,
        second=dt_tehran.second,
        tzinfo=tehran_tz
    )
    return jdt.strftime("%Y-%m-%d %H:%M:%S") 

# Agency authentication
class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        key = request.headers.get('Authentication')
        if not key:
            raise AuthenticationFailed('No API key provided')

        try:
            agency = AgencyKey.objects.get(key=key, active=True)
            return (agency, None)
        except AgencyKey.DoesNotExist:
            raise AuthenticationFailed('Invalid API key')

# Search Key words
class GetFeedView(APIView):
    authentication_classes = [APIKeyAuthentication] # Authentication via APIKeyAuth class
    def get(self, request):
        agency = request.user

        try:
            keyword_table = agency.keyword_table # get agency keywords
        except KeyWordTable.DoesNotExist:
            return Response({"error": "No keywords configured for your agency"}, status=404)
        try:
            words = keyword_table.words.values_list('text', flat=True)
            if not words:
                return Response({"articles": []})
            
            title_q = build_whole_word_query('title', words)
            abstract_q = build_whole_word_query('abstract', words)
            articles = Article.objects.filter(title_q | abstract_q).distinct()
            paginator = PageNumberPagination()
            paginated_articles = paginator.paginate_queryset(articles, request)

            # Serialize data
            data = []
            for a in paginated_articles:
                published_jalali = None
                if a.published is not None:
                    try:
                        published_jalali = convert_timestamp_to_jalali(a.published)
                    except (ValueError, OSError, OverflowError):
                        published_jalali = None
                
                article_feed = a.feed

                data.append({
                    "title": a.title,
                    "link": a.link,
                    "abstract": a.abstract,
                    "cover": a.cover,
                    "published": published_jalali,
                    "feed": {"name": article_feed.name, "icon": article_feed.favicon}
                })
            return paginator.get_paginated_response({"articles": data})
        except KeyWordTable.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


# Append Key words for a user
class AddKeywordsView(APIView):
    authentication_classes = [APIKeyAuthentication]

    def post(self, request):
        agency = request.user
        keywords_str = request.data.get('keywords', '').strip()

        if not keywords_str:
            return Response(
                {"error": "Missing 'keywords' field (comma-separated string)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        keyword_list = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
        if not keyword_list:
            return Response(
                {"error": "No valid keywords provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        for kw in keyword_list:
            if len(kw) > 100:
                return Response(
                    {"error": f"Keyword too long: '{kw}' (max 100 chars)"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            keyword_table, created = KeyWordTable.objects.get_or_create(agency=agency)

            with transaction.atomic():
                created_words = []
                for word in keyword_list:
                    obj, created = SearchKeyWord.objects.get_or_create(text=word)
                    if created:
                        created_words.append(word)
                    keyword_table.words.add(obj)

            return Response({
                "message": "Keywords added successfully",
                "total_keywords_added": len(keyword_list),
                "newly_created_words": created_words,
                "agency": agency.name
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": "Failed to add keywords", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

# Search Key words
class Search(APIView):
    def get(self, request):
        query_word = request.query_params.get('q', '').strip()

        if not query_word:
            return Response(
                {"error": "Missing 'q' parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        articles = Article.objects.filter(
                Q(title__icontains=query_word) | Q(abstract__icontains=query_word)
            )
        print(len(articles))
        paginator = PageNumberPagination()

        paginated_articles = paginator.paginate_queryset(articles, request)
        data = []
        for a in paginated_articles:
            published_jalali = None
            if a.published is not None:
                try:
                    published_jalali = convert_timestamp_to_jalali(a.published)
                except (ValueError, OSError, OverflowError):
                    published_jalali = None
            
            article_feed = a.feed

            data.append({
                "title": a.title,
                "link": a.link,
                "abstract": a.abstract,
                "cover": a.cover,
                "published": published_jalali,
                "feed": {"name": article_feed.name, "icon": article_feed.favicon}
            })
        return paginator.get_paginated_response({"articles": data})