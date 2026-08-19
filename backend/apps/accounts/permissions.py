from rest_framework.permissions import BasePermission


class IsOrganizer(BasePermission):
    message = "Apenas organizadores podem realizar esta ação."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_organizer)


class IsCustomer(BasePermission):
    message = "Apenas clientes podem realizar esta ação."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_customer)


class IsGate(BasePermission):
    message = "Apenas usuários de portaria podem realizar esta ação."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_gate)
