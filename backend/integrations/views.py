from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class IntegrationStatusView(APIView):
    """Lightweight status probe — Ahad expands this with run history later."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "status": "ready",
                "scrapers": ["historical", "live", "news"],
                "note": "Scraper logic stubs — Ahad fills implementation.",
            }
        )
