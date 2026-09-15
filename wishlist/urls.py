from django.urls import path
from .views import (
    AddWishlistView,
    MoveToCartView,
    RemoveWishlistView,
    ToggleWishlistView,
    WishlistListView,
)

urlpatterns = [
    path("", WishlistListView.as_view(), name="wishlist-list"),
    path("add/", AddWishlistView.as_view(), name="wishlist-add"),
    path("toggle/", ToggleWishlistView.as_view(), name="wishlist-toggle"),
    path("toggle/<int:product_id>/", ToggleWishlistView.as_view(), name="wishlist-toggle-id"),
    path("<int:product_id>/toggle/", ToggleWishlistView.as_view(), name="wishlist-toggle-id-alt"),
    path("remove/<int:product_id>/", RemoveWishlistView.as_view(), name="wishlist-remove"),
    path("move-to-cart/<int:product_id>/", MoveToCartView.as_view(), name="wishlist-move-to-cart"),
]
