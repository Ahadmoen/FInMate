from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from news import services
from news.pagination import NewsPagination
from news.serializers import serialize_article


class NewsFiltersView(APIView):
    """GET /api/v1/news/filters/ — sentiment, industry, stock dropdown options."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "sentiments": services.SENTIMENT_FILTERS,
            "industries": services.list_industry_filters(),
            "stocks": services.list_stock_filters(),
        })


class MarketSentimentIndexView(APIView):
    """GET /api/v1/news/sentiment-index/ — Fear & Greed-style market card."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.compute_market_sentiment_index())


class NewsFeedView(APIView):
    """GET /api/v1/news/feed/?sentiment=&industry=&stock=&page=1"""

    permission_classes = [IsAuthenticated]
    pagination_class = NewsPagination

    def get(self, request):
        sentiment = request.query_params.get("sentiment", "all")
        industry = request.query_params.get("industry", "all")
        stock = request.query_params.get("stock", "all")

        qs = services.apply_news_filters(
            services.news_feed_queryset(),
            sentiment=sentiment,
            industry=industry,
            stock=stock,
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        results = [serialize_article(a) for a in page]
        return paginator.get_paginated_response(results)


class NewsSearchView(APIView):
    """GET /api/v1/news/search/?q=&sentiment=&industry=&stock=&page=1

    Headline search (``headline__icontains``), same pagination as feed.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = NewsPagination

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if not q:
            return Response(
                {"detail": "Query parameter 'q' is required."},
                status=400,
            )

        sentiment = request.query_params.get("sentiment", "all")
        industry = request.query_params.get("industry", "all")
        stock = request.query_params.get("stock", "all")

        qs = services.apply_headline_search(
            services.apply_news_filters(
                services.news_feed_queryset(),
                sentiment=sentiment,
                industry=industry,
                stock=stock,
            ),
            q,
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        results = [serialize_article(a) for a in page]
        response = paginator.get_paginated_response(results)
        response.data["q"] = q
        return response
