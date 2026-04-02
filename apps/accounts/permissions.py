from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        return obj.user == request.user or request.user.is_staff

class IsAdminOrAgent(permissions.BasePermission):
    """
    Allows access only to admin or agent users.
    """
    def has_permission(self, request, view):
        return request.user and (request.user.user_type in ['admin', 'agent'] or request.user.is_staff)

class IsVerifiedUser(permissions.BasePermission):
    """
    Allows access only to verified users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.email_verified

class HasTwoFactorEnabled(permissions.BasePermission):
    """
    Allows access only to users with 2FA enabled.
    """
    def has_permission(self, request, view):
        return request.user and request.user.security_settings.two_factor_enabled