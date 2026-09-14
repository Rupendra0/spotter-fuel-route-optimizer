import logging
from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from routes.models import FuelStation
from routes.serializers import (
    RouteOptimizeRequestSerializer,
    RouteOptimizationResponseSerializer,
)
from routes.services.route_service import RouteService
from routes.exceptions import RouteOptimizerBaseException

logger = logging.getLogger(__name__)


class RouteOptimizeView(APIView):
    """
    POST /api/v1/routes/optimize/
    Calculates driving route, identifies candidate stations within the route corridor,
    and returns cost-optimal fuel stops adhering to 500-mile range and vehicle constraints.
    """

    @extend_schema(
        request=RouteOptimizeRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=RouteOptimizationResponseSerializer,
                description="Optimal route and fuel stop schedule calculated successfully.",
            ),
            400: OpenApiResponse(description="Invalid request payload or non-USA location."),
            404: OpenApiResponse(description="Location or driving route could not be found."),
            422: OpenApiResponse(description="Route is physically infeasible with vehicle range."),
            503: OpenApiResponse(description="External routing or geocoding service unavailable."),
        },
        summary="Plan cost-optimal fuel stops along a driving route",
        description=(
            "Accepts a USA starting location and destination location, fetches road geometry, "
            "and schedules fuel stops to minimize total fuel cost while respecting a 500-mile "
            "range limit and 10 MPG fuel economy."
        ),
    )
    def post(self, request, *args, **kwargs):
        serializer = RouteOptimizeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Validation failed", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_loc = serializer.validated_data["start"]
        finish_loc = serializer.validated_data["finish"]
        corridor_radius = serializer.validated_data.get("corridor_radius_miles", 15.0)

        route_service = RouteService()

        try:
            result = route_service.plan_optimized_route(
                start_location=start_loc,
                finish_location=finish_loc,
                corridor_radius_miles=corridor_radius,
            )
            return Response(result, status=status.HTTP_200_OK)

        except RouteOptimizerBaseException as e:
            logger.warning(f"Route optimization domain error ({e.code}): {e.message}")
            return Response(
                {"error": e.message, "code": e.code},
                status=e.status_code,
            )
        except Exception as e:
            logger.exception(f"Unexpected internal error during route optimization: {e}")
            return Response(
                {"error": "An unexpected internal error occurred while processing the route."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class HealthCheckView(APIView):
    """
    GET /api/v1/health/
    Health check endpoint returning system status and station database count.
    """

    @extend_schema(summary="Service health check")
    def get(self, request, *args, **kwargs):
        station_count = FuelStation.objects.count()
        return Response(
            {
                "status": "ok",
                "service": "spotter-fuel-route-optimizer",
                "database": "sqlite3",
                "stations_loaded": station_count,
            },
            status=status.HTTP_200_OK,
        )


class MapDemoView(TemplateView):
    """
    GET /
    Interactive map interface using Leaflet.js and OpenStreetMap.
    """
    template_name = "map_demo.html"
