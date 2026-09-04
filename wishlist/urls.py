from django.urls import path
from .views import (
    AddWishlistView,
    MoveToCartView,
    RemoveWishlistView,
    WishlistListView,
)

urlpatterns = [
    path("", WishlistListView.as_view(), name="wishlist-list"),
    path("add/", AddWishlistView.as_view(), name="wishlist-add"),
    path("remove/<int:product_id>/", RemoveWishlistView.as_view(), name="wishlist-remove"),
    path("move-to-cart/<int:product_id>/", MoveToCartView.as_view(), name="wishlist-move-to-cart"),
]
