"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

# Swagger / OpenAPI Schema Configuration
schema_view = get_schema_view(
    openapi.Info(
        title="E-Commerce API",
        default_version="v1",
        description="RESTful API backend for E-Commerce Platform built with Django & DRF",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@ecommerce.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # Swagger & ReDoc API Documentation
    re_path(
        r"^swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path(
        "redoc/",
        schema_view.with_ui("redoc", cache_timeout=0),
        name="schema-redoc",
    ),
    path(
        "api/docs/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui-api-docs",
    ),
    path(
        "docs/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui-docs",
    ),

    # Accounts / User Management Endpoints (v1 and default API namespaces)
    path("api/v1/", include("accounts.urls")),
    path("api/", include("accounts.urls")),

    # Categories Endpoints
    path("api/v1/categories/", include("categories.urls")),
    path("api/categories/", include("categories.urls")),

    # Products Endpoints
    path("api/v1/products/", include("products.urls")),
    path("api/products/", include("products.urls")),

    # Cart Endpoints
    path("api/v1/cart/", include("cart.urls")),
    path("api/cart/", include("cart.urls")),

    # Wishlist Endpoints
    path("api/v1/wishlist/", include("wishlist.urls")),
    path("api/wishlist/", include("wishlist.urls")),

    # Orders & Checkout Endpoints
    path("api/v1/orders/", include("orders.urls")),
    path("api/orders/", include("orders.urls")),

    # Payments & Razorpay Endpoints
    path("api/v1/payments/", include("payment.urls")),
    path("api/payments/", include("payment.urls")),

    # Reviews & Ratings Endpoints
    path("api/v1/reviews/", include("reviews.urls")),
    path("api/reviews/", include("reviews.urls")),
    path("api/v1/my-reviews/", include("reviews.urls_user")),
    path("api/my-reviews/", include("reviews.urls_user")),



    # JWT Authentication Endpoints (SimpleJWT standard routes)
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/v1/auth/token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair_unversioned"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh_unversioned"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify_unversioned"),
    path("api/auth/token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist_unversioned"),
]

# Serve static & media files
from django.views.static import serve

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
