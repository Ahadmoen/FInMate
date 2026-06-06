from django.urls import path

from news.views import (
    MarketSentimentIndexView,
    NewsFeedView,
    NewsFiltersView,
    NewsSearchView,
)

urlpatterns = [
    path("filters/", NewsFiltersView.as_view(), name="news-filters"),
    path("sentiment-index/", MarketSentimentIndexView.as_view(), name="news-sentiment-index"),
    path("feed/", NewsFeedView.as_view(), name="news-feed"),
    path("search/", NewsSearchView.as_view(), name="news-search"),
]
