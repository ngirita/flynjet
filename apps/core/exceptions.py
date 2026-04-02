from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied
from django.http import Http404
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Log the exception
    logger.error(f"Exception occurred: {exc}", exc_info=True)
    
    if response is not None:
        # Customize error responses
        response.data = {
            'error': {
                'code': response.status_code,
                'message': response.data.get('detail', str(exc)),
                'type': exc.__class__.__name__
            }
        }
    
    # Handle specific exceptions
    if isinstance(exc, Http404):
        return Response(
            {'error': {'code': 404, 'message': 'Resource not found'}},
            status=status.HTTP_404_NOT_FOUND
        )
    
    elif isinstance(exc, PermissionDenied):
        return Response(
            {'error': {'code': 403, 'message': 'Permission denied'}},
            status=status.HTTP_403_FORBIDDEN
        )
    
    elif isinstance(exc, ValueError):
        return Response(
            {'error': {'code': 400, 'message': str(exc)}},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return response


class BookingError(Exception):
    """Custom exception for booking-related errors."""
    pass


class PaymentError(Exception):
    """Custom exception for payment-related errors."""
    pass


class FleetError(Exception):
    """Custom exception for fleet-related errors."""
    pass


class AuthenticationError(Exception):
    """Custom exception for authentication errors."""
    pass


class ValidationError(Exception):
    """Custom exception for validation errors."""
    
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(message)


class ServiceUnavailableError(Exception):
    """Exception for when a service is unavailable."""
    pass


class RateLimitExceededError(Exception):
    """Exception for when rate limit is exceeded."""
    pass


def handle_validation_error(errors):
    """
    Helper function to format validation errors.
    """
    formatted_errors = {}
    for field, error_list in errors.items():
        formatted_errors[field] = [str(error) for error in error_list]
    
    return Response(
        {'error': {'code': 400, 'validation_errors': formatted_errors}},
        status=status.HTTP_400_BAD_REQUEST
    )