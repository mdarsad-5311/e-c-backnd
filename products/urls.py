from django.urls import path
from reviews.views import ProductReviewsView
from .views import (
    ProductDetailView,
    ProductImageListCreateView,
    ProductListCreateView,
)

urlpatterns = [
    path("", ProductListCreateView.as_view(), name="product-list-create"),
    path("<int:pk>/reviews/", ProductReviewsView.as_view(), name="product-reviews-id"),
    path("<str:pk_or_slug>/reviews/", ProductReviewsView.as_view(), name="product-reviews"),
    path("<str:pk_or_slug>/", ProductDetailView.as_view(), name="product-detail"),
    path("<int:product_id>/images/", ProductImageListCreateView.as_view(), name="product-images"),
]

