class RouteOptimizerBaseException(Exception):
    """Base exception for route optimization domain errors."""
    status_code = 400
    default_code = "route_error"

    def __init__(self, message: str, status_code: int = None, code: str = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code if status_code is not None else self.__class__.status_code
        self.code = code or self.default_code


class GeocodingNotFoundError(RouteOptimizerBaseException):
    status_code = 404
    default_code = "location_not_found"


class NonUSALocationError(RouteOptimizerBaseException):
    status_code = 400
    default_code = "non_usa_location"


class GeocodingServiceError(RouteOptimizerBaseException):
    status_code = 503
    default_code = "geocoding_service_unavailable"


class NoRouteFoundError(RouteOptimizerBaseException):
    status_code = 404
    default_code = "no_route_found"


class RoutingServiceError(RouteOptimizerBaseException):
    status_code = 503
    default_code = "routing_service_unavailable"


class InfeasibleRouteError(RouteOptimizerBaseException):
    status_code = 422
    default_code = "infeasible_route"
