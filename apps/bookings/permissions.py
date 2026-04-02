from rest_framework import permissions

class IsBookingOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of a booking to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner, admin, or assigned agent
        return (
            obj.user == request.user or
            request.user.is_staff or
            request.user.user_type == 'admin' or
            (request.user.user_type == 'agent' and obj.assigned_agent == request.user)
        )


class CanCreateBooking(permissions.BasePermission):
    """
    Permission to check if user can create a booking.
    """
    
    def has_permission(self, request, view):
        # Any authenticated user can create a booking
        return request.user and request.user.is_authenticated


class CanCancelBooking(permissions.BasePermission):
    """
    Permission to check if user can cancel a booking.
    """
    
    def has_object_permission(self, request, view, obj):
        # Check if booking can be cancelled
        if obj.status in ['completed', 'cancelled']:
            return False
        
        # Check if user has permission
        return (
            obj.user == request.user or
            request.user.is_staff or
            request.user.user_type == 'admin'
        )


class CanModifyPassengers(permissions.BasePermission):
    """
    Permission to modify passenger list.
    """
    
    def has_object_permission(self, request, view, obj):
        # Only allow modifications for draft or pending bookings
        if obj.status not in ['draft', 'pending']:
            return False
        
        return (
            obj.user == request.user or
            request.user.is_staff or
            request.user.user_type == 'admin'
        )


class IsInvoiceOwner(permissions.BasePermission):
    """
    Permission for invoice access.
    """
    
    def has_object_permission(self, request, view, obj):
        return (
            obj.user == request.user or
            request.user.is_staff or
            request.user.user_type == 'admin'
        )