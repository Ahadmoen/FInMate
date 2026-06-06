from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from insights import services
from insights.pagination import InsightsPagination
from insights.serializers import (
    serialize_forecast,
    serialize_list_item,
    serialize_live,
    serialize_news_item,
    serialize_signal,
)


class InsightsFiltersView(APIView):
    """GET /api/v1/insights/filters/ — sector/trend/sort options for the UI."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # No Redis cache — local dev often has no broker; query is cheap (distinct sectors).
        return Response({
            "sectors": services.list_sector_filters(),
            "trends": services.TREND_FILTERS,
            "sort_options": services.SORT_OPTIONS,
        })


class InsightsStockListView(APIView):
    """GET /api/v1/insights/stocks/

    Query params: q, sector, trend, sort, page (10 per page).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = InsightsPagination

    def get(self, request):
        q = request.query_params.get("q", "")
        sector = request.query_params.get("sector", "all")
        trend = request.query_params.get("trend", "all")
        sort = request.query_params.get("sort", "name")

        qs = services.apply_insights_filters(
            services.insights_symbols_queryset(),
            q=q,
            sector=sector,
            trend=trend,
            sort=sort,
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        results = [serialize_list_item(sym) for sym in page]
        return paginator.get_paginated_response(results)


class InsightsStockDetailView(APIView):
    """GET /api/v1/insights/stocks/<ticker>/ — live, signal, forecast for detail screen."""

    permission_classes = [IsAuthenticated]

    def get(self, request, ticker: str):
        sym = services.get_symbol(ticker)
        if sym is None:
            raise NotFound(f"Stock '{ticker.upper()}' not found.")

        ticker_u = sym.ticker
        live = services.latest_live_for(ticker_u)
        sig = services.latest_signal_for(ticker_u)
        fc = services.latest_forecast_for(ticker_u)

        return Response({
            "symbol_id": str(sym.id),
            "ticker": sym.ticker,
            "company_name": sym.company_name,
            "sector": sym.sector or "",
            "live": serialize_live(live),
            "signal": serialize_signal(sig),
            "forecast": serialize_forecast(fc),
        })


class InsightsStockNewsView(APIView):
    """GET /api/v1/insights/stocks/<ticker>/news/?offset=0&limit=5"""

    permission_classes = [IsAuthenticated]

    def get(self, request, ticker: str):
        sym = services.get_symbol(ticker)
        if sym is None:
            raise NotFound(f"Stock '{ticker.upper()}' not found.")

        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
        except (TypeError, ValueError):
            offset = 0
        try:
            limit = min(50, max(1, int(request.query_params.get("limit", 5))))
        except (TypeError, ValueError):
            limit = 5

        articles, total = services.news_for_ticker(sym.ticker, offset=offset, limit=limit)
        items = [serialize_news_item(a) for a in articles]

        return Response({
            "ticker": sym.ticker,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(items) < total,
            "items": items,
        })
