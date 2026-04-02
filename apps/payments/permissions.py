from rest_framework import permissions

class IsPaymentOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of a payment to view it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to the owner
        if request.method in permissions.SAFE_METHODS:
            return obj.user == request.user or request.user.is_staff
        
        # No write permissions for regular users on payments
        return request.user.is_staff or request.user.user_type == 'admin'


class CanProcessRefund(permissions.BasePermission):
    """
    Permission to check if user can process refunds.
    """
    
    def has_permission(self, request, view):
        return request.user.is_staff or request.user.user_type == 'admin'


class IsRefundOwnerOrStaff(permissions.BasePermission):
    """
    Permission for refund requests.
    """
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.user == request.user or request.user.is_staff
        
        # Only staff can update refund status
        return request.user.is_staff


class CanViewPayouts(permissions.BasePermission):
    """
    Permission to view payouts (admin/agent only).
    """
    
    def has_permission(self, request, view):
        return request.user.is_staff or request.user.user_type in ['admin', 'agent']