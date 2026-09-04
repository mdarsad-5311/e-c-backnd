from django.urls import path
from .views import UserReviewHistoryView

urlpatterns = [
    path("", UserReviewHistoryView.as_view(), name="user_reviews_history"),
]
