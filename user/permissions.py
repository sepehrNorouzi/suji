from rest_framework import permissions


class IsGuestPlayer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.email is None and request.user.device_id is not None


class IsNormalPlayer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.email is not None and request.user.device_id is None
