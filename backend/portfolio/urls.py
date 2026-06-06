from django.urls import path

from .views import (
    PortfolioAnalyticsView,
    PortfolioHoldingDetailView,
    PortfolioHoldingListCreateView,
    TransactionListCreateView,
)

urlpatterns = [
    path("holdings/", PortfolioHoldingListCreateView.as_view(), name="portfolio-holdings"),
    path("holdings/<uuid:id>/", PortfolioHoldingDetailView.as_view(), name="portfolio-holding-detail"),
    path("transactions/", TransactionListCreateView.as_view(), name="portfolio-transactions"),
    path("analytics/", PortfolioAnalyticsView.as_view(), name="portfolio-analytics"),
]
