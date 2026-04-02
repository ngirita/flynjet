from rest_framework import permissions

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to admin/staff
        return request.user and (request.user.is_staff or request.user.user_type == 'admin')
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to admin/staff
        return request.user and (request.user.is_staff or request.user.user_type == 'admin')


class IsMaintenanceTeamOrReadOnly(permissions.BasePermission):
    """
    Custom permission for maintenance team access.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions are only allowed to maintenance team, admin, or staff
        return request.user and (
            request.user.is_staff or 
            request.user.user_type in ['admin', 'maintenance']
        )
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions are only allowed to maintenance team, admin, or staff
        return request.user and (
            request.user.is_staff or 
            request.user.user_type in ['admin', 'maintenance']
        )


class IsAircraftOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an aircraft to edit it.
    Note: Aircraft don't have owners, so this is for future expansion
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # For now, only admin/staff can edit
        return request.user and (request.user.is_staff or request.user.user_type == 'admin')


class CanViewMaintenanceRecords(permissions.BasePermission):
    """
    Permission to view maintenance records.
    """
    
    def has_permission(self, request, view):
        # Any authenticated user can view maintenance records
        return request.user.is_authenticated


class CanScheduleMaintenance(permissions.BasePermission):
    """
    Permission to schedule maintenance.
    """
    
    def has_permission(self, request, view):
        # Only admin, staff, and maintenance team can schedule maintenance
        return request.user and (
            request.user.is_staff or 
            request.user.user_type in ['admin', 'maintenance']
        )


class CanUploadDocuments(permissions.BasePermission):
    """
    Permission to upload aircraft documents.
    """
    
    def has_permission(self, request, view):
        # Only admin, staff, and maintenance team can upload documents
        return request.user and (
            request.user.is_staff or 
            request.user.user_type in ['admin', 'maintenance']
        )


class CanApproveDocuments(permissions.BasePermission):
    """
    Permission to approve documents.
    """
    
    def has_permission(self, request, view):
        # Only admin and staff can approve documents
        return request.user and (request.user.is_staff or request.user.user_type == 'admin')