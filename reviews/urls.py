from django.urls import path
from .views import (
    ProductReviewsView,
    ReviewDetailView,
    UserReviewHistoryView,
)

urlpatterns = [
    path("<int:pk>/", ReviewDetailView.as_view(), name="review_detail"),
    path("my-reviews/", UserReviewHistoryView.as_view(), name="my_reviews"),
    path("products/<int:pk>/reviews/", ProductReviewsView.as_view(), name="product_reviews_direct"),
]
