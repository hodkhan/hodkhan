from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination 
from django.db.models import Q
from django.db import transaction
from .models import KeyWordTable, SearchKeyWord, AgencyKey, ArticleKeywordTable
from app.models import Article
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import datetime
import pytz
import jdatetime


def build_whole_word_query(field_name, words, exclude_mode=False):
    query = Q()
    for word in words:
        w = word.strip()
        if not w:
            continue
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
        q =  start | end | middle
        for pv in punct_variants:
            q |= pv
        query |= q

    if exclude_mode:
        return ~query
    return query


# Search All or some Articles for Keywords
# send a list of Articles or set articles_to_search = None for searching all 
def Search_Articles(keyword_table, articles_to_search = None):

    words = keyword_table.words.values_list('text', flat=True)
    exclude_words = keyword_table.ban_words.values_list('text', flat=True)
    if not words:
        return []
    
    title_q = build_whole_word_query('title', words)
    abstract_q = build_whole_word_query('abstract', words)
    include_query = title_q | abstract_q

    exclude_query = Q()
    
    if exclude_words:
        title_exclude_q = build_whole_word_query('title', exclude_words)
        abstract_exclude_q = build_whole_word_query('abstract', exclude_words)
        exclude_query = title_exclude_q | abstract_exclude_q

    if articles_to_search is not None:
        article_ids = [article.id for article in articles_to_search if hasattr(article, 'id') and article.id]
        articles = Article.objects.filter(include_query, id__in=article_ids)
    else:
        articles = Article.objects.filter(include_query)
    if exclude_words:
        articles = articles.exclude(exclude_query)
    
    articles = articles.distinct()
    return articles

def connect_article_to_keywordTable(articles, keyword_table):
    created_connections = []
    for article in articles:
        connection, created = ArticleKeywordTable.objects.get_or_create(
            article = article,
            keyword_table=keyword_table
        )
        if created:
            created_connections.append(connection)
    

    return created_connections

def Append_new_articles(articles):
    keyword_tables = KeyWordTable.objects.all()
    connection_count = 0
    for keyword_table in keyword_tables:
        found_articles = Search_Articles(keyword_table, articles)
        created_connections = connect_article_to_keywordTable(found_articles, keyword_table)
        connection_count += len(created_connections)
        
    return connection_count


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
        key = request.headers.get('Authorization')
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
            articles = Article.objects.filter(
                articlekeywordtable__keyword_table=keyword_table
            ).distinct()
            print(len(articles))           

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
                    "id": a.id,
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


# Append Key words for a user
class SearchAndAppendArticles(APIView):
    authentication_classes = [APIKeyAuthentication]

    def post(self, request):
        agency = request.user
        keyword_table = agency.keyword_table # get agency keywords

        try:

            delete_count, _ = ArticleKeywordTable.objects.filter(
                keyword_table=keyword_table
            ).delete()
            articles = Search_Articles(keyword_table)
            created = connect_article_to_keywordTable(articles, keyword_table)

            return Response({
                "message": "Keyword table updated successfully",
                "deleted articles" : delete_count,
                "added articles": len(created),
                "agency": agency.name
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Failed to updated Keyword table", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )