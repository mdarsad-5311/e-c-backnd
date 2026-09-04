from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema

from .models import Category
from .serializers import CategorySerializer


class CategoryListCreateView(generics.ListCreateAPIView):
    """
    get:
    Return a list of all active categories with product counts.
    
    post:
    Create a new category (Staff/Admin only).
    """
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        # Annotate active products count to avoid N+1 queries
        qs = Category.objects.annotate(
            active_products_count=Count("products", filter=Q(products__is_active=True))
        )
        # Admin can view inactive categories, public sees only active categories
        if self.request.user and self.request.user.is_staff:
            return qs.all()
        return qs.filter(is_active=True)


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    get:
    Retrieve a category by primary key (ID) or slug.
    
    put / patch:
    Update category (Staff/Admin only).
    
    delete:
    Delete category (Staff/Admin only).
    """
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = Category.objects.annotate(
            active_products_count=Count("products", filter=Q(products__is_active=True))
        )
        if self.request.user and self.request.user.is_staff:
            return qs.all()
        return qs.filter(is_active=True)

    def get_object(self):
        lookup = self.kwargs.get("pk_or_slug")
        queryset = self.get_queryset()

        if str(lookup).isdigit():
            obj = queryset.filter(id=int(lookup)).first()
            if obj:
                self.check_object_permissions(self.request, obj)
                return obj

        obj = get_object_or_404(queryset, slug=lookup)
        self.check_object_permissions(self.request, obj)
        return obj
