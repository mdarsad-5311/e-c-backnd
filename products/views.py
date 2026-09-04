from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .filters import ProductFilterBackend
from .models import Product, ProductImage
from .pagination import ProductPagination
from .serializers import (
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
)


class ProductListCreateView(generics.ListCreateAPIView):
    """
    get:
    List all active products with pagination, search, category filtering, price filtering, and ordering.
    
    post:
    Create a new product (Staff/Admin only).
    """
    pagination_class = ProductPagination
    filter_backends = [ProductFilterBackend]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProductDetailSerializer
        return ProductListSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = (
            Product.objects.select_related("category")
            .prefetch_related("images")
            .all()
        )
        if self.request.user and self.request.user.is_staff:
            return qs
        return qs.filter(is_active=True, category__is_active=True)


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    get:
    Retrieve a product by primary key (ID) or slug with full details, category, and gallery images.
    
    put / patch:
    Update product (Staff/Admin only).
    
    delete:
    Delete product (Staff/Admin only).
    """
    serializer_class = ProductDetailSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = (
            Product.objects.select_related("category")
            .prefetch_related("images")
            .all()
        )
        if self.request.user and self.request.user.is_staff:
            return qs
        return qs.filter(is_active=True, category__is_active=True)

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


class ProductImageListCreateView(generics.ListCreateAPIView):
    """
    get:
    List images for a specific product.
    
    post:
    Upload a new image for a product (Staff/Admin only).
    """
    serializer_class = ProductImageSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        product_id = self.kwargs.get("product_id")
        return ProductImage.objects.filter(product_id=product_id)

    def perform_create(self, serializer):
        product_id = self.kwargs.get("product_id")
        product = get_object_or_404(Product, id=product_id)
        serializer.save(product=product)
