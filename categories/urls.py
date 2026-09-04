from django.urls import path
from .views import CategoryListCreateView, CategoryDetailView

urlpatterns = [
    path("", CategoryListCreateView.as_view(), name="category-list-create"),
    path("<str:pk_or_slug>/", CategoryDetailView.as_view(), name="category-detail"),
]
