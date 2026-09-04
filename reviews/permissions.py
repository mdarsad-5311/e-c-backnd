from rest_framework import permissions


class IsReviewOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow read access to anyone,
    creation to authenticated users, and editing/deletion only to the review author or admin staff.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user
            and request.user.is_authenticated
            and (obj.user == request.user or request.user.is_staff)
        )
