from django.urls import path

from .views import DashboardNewsView, DashboardStocksView

urlpatterns = [
    path("stocks/", DashboardStocksView.as_view(), name="dashboard-stocks"),
    path("news/", DashboardNewsView.as_view(), name="dashboard-news"),
]
