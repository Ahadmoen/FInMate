from django.urls import path

from .views import (
    InsightsFiltersView,
    InsightsStockDetailView,
    InsightsStockListView,
    InsightsStockNewsView,
)

urlpatterns = [
    path("filters/", InsightsFiltersView.as_view(), name="insights-filters"),
    path("stocks/", InsightsStockListView.as_view(), name="insights-stocks"),
    path("stocks/<str:ticker>/", InsightsStockDetailView.as_view(), name="insights-stock-detail"),
    path(
        "stocks/<str:ticker>/news/",
        InsightsStockNewsView.as_view(),
        name="insights-stock-news",
    ),
]
