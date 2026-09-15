from django.urls import path
from .views import (
    AddToCartView,
    CartView,
    ClearCartView,
    RemoveCartItemView,
    SyncCartView,
    UpdateCartItemView,
)

urlpatterns = [
    path("", CartView.as_view(), name="cart-detail"),
    path("add/", AddToCartView.as_view(), name="cart-add"),
    path("sync/", SyncCartView.as_view(), name="cart-sync"),
    path("migrate/", SyncCartView.as_view(), name="cart-migrate"),
    path("update/<int:item_id>/", UpdateCartItemView.as_view(), name="cart-update"),
    path("remove/<int:item_id>/", RemoveCartItemView.as_view(), name="cart-remove"),
    path("clear/", ClearCartView.as_view(), name="cart-clear"),
]
