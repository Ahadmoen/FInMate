from django.db import IntegrityError

from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from dashboard.cache_invalidation import invalidate_dashboard_portfolio_health

from .analytics import compute_portfolio_analytics
from .models import PortfolioHolding, Transaction
from .serializers import (
    PortfolioHoldingReadSerializer,
    PortfolioHoldingUpdateSerializer,
    PortfolioHoldingWriteSerializer,
    TransactionSerializer,
)
from .services import get_holdings_enriched


class PortfolioHoldingListCreateView(generics.ListCreateAPIView):
    """GET  /api/v1/portfolio/holdings/  — authenticated user's holdings, enriched with live data.
    POST /api/v1/portfolio/holdings/  — add a new holding.

    POST body:
        { "symbol_id": "<StockSymbol UUID>", "quantity": 500, "avg_buy_price": 162.20 }

    Error scenarios handled:
        - symbol_id not found / inactive          → 400 (DRF validation)
        - quantity ≤ 0 or avg_buy_price ≤ 0       → 400 (serializer validation)
        - stock already in portfolio (duplicate)  → 400 with human-readable message
    """

    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PortfolioHoldingWriteSerializer
        return PortfolioHoldingReadSerializer

    def get_queryset(self):
        return get_holdings_enriched(self.request.user)

    def create(self, request, *args, **kwargs):
        write_serializer = PortfolioHoldingWriteSerializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)

        try:
            holding = write_serializer.save(user=request.user)
        except IntegrityError:
            return Response(
                {"detail": "This stock is already in your portfolio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Return the full enriched shape so the client can update its list immediately.
        invalidate_dashboard_portfolio_health(request.user)

        enriched = get_holdings_enriched(request.user).filter(id=holding.id).first()
        read_serializer = PortfolioHoldingReadSerializer(enriched)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


class PortfolioHoldingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH / DELETE /api/v1/portfolio/holdings/<id>/

    GET and PATCH return the enriched shape (live price included).
    PATCH accepts partial updates; only quantity and avg_buy_price are writable.
    DELETE removes the holding permanently.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return PortfolioHoldingUpdateSerializer
        return PortfolioHoldingReadSerializer

    def get_queryset(self):
        return PortfolioHolding.objects.filter(user=self.request.user)

    def get_object(self):
        if self.request.method == "GET":
            holding = (
                get_holdings_enriched(self.request.user)
                .filter(pk=self.kwargs[self.lookup_field])
                .first()
            )
            if holding is None:
                raise NotFound("Holding not found.")
            return holding
        return super().get_object()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write_serializer = PortfolioHoldingUpdateSerializer(
            instance, data=request.data, partial=partial
        )
        write_serializer.is_valid(raise_exception=True)
        holding = write_serializer.save()

        invalidate_dashboard_portfolio_health(request.user)

        enriched = get_holdings_enriched(request.user).filter(id=holding.id).first()
        read_serializer = PortfolioHoldingReadSerializer(enriched)
        return Response(read_serializer.data)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_dashboard_portfolio_health(self.request.user)


class TransactionListCreateView(generics.ListCreateAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PortfolioAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(compute_portfolio_analytics(request.user))
