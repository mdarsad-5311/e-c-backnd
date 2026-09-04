from rest_framework import permissions

class IsOrderOwner(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an order to view/edit it.
    """
    def has_object_permission(self, request, view, obj):
        return hasattr(obj, 'user') and obj.user == request.user
