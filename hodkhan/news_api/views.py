from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import KeyWordTable

from app.models import Article
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import AgencyKey
import datetime
import pytz
import jdatetime


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

class GetFeedView(APIView):
    authentication_classes = [APIKeyAuthentication]
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
            query = Q()
            for word in words:
                query |= Q(title__icontains=word) | Q(abstract__icontains=word)

            articles = Article.objects.filter(query)

            data = []
            for a in articles:
                published_jalali = None
                if a.published is not None:
                    try:
                        published_jalali = convert_timestamp_to_jalali(a.published)
                    except (ValueError, OSError, OverflowError):
                        published_jalali = None

                data.append({
                    "title": a.title,
                    "link": a.link,
                    "abstract": a.abstract,
                    "cover": a.cover,
                    "published": published_jalali
                })
            return Response({"articles": data})
        except KeyWordTable.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
