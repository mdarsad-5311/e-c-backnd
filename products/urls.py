from django.urls import path
from reviews.views import ProductReviewsView, ReviewDetailView
from .views import (
    ProductDetailView,
    ProductImageListCreateView,
    ProductListCreateView,
)

urlpatterns = [
    path("", ProductListCreateView.as_view(), name="product-list-create"),
    path("<int:pk>/reviews/", ProductReviewsView.as_view(), name="product-reviews-id"),
    path("<str:pk_or_slug>/reviews/", ProductReviewsView.as_view(), name="product-reviews"),
    path("<int:product_id>/reviews/<int:pk>/", ReviewDetailView.as_view(), name="product-review-detail-id"),
    path("<str:pk_or_slug>/reviews/<int:pk>/", ReviewDetailView.as_view(), name="product-review-detail"),
    path("<str:pk_or_slug>/", ProductDetailView.as_view(), name="product-detail"),
    path("<int:product_id>/images/", ProductImageListCreateView.as_view(), name="product-images"),
]

