from django.urls import path
from routes.views import RouteOptimizeView, HealthCheckView, MapDemoView

urlpatterns = [
    path("", MapDemoView.as_view(), name="map-demo"),
    path("api/v1/routes/optimize/", RouteOptimizeView.as_view(), name="route-optimize"),
    path("api/v1/health/", HealthCheckView.as_view(), name="health-check"),
]
