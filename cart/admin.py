from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ("product", "quantity", "subtotal", "created_at")
    readonly_fields = ("subtotal", "created_at")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "total_items_count",
        "unique_items_count",
        "subtotal",
        "total_savings",
        "created_at",
        "updated_at",
    )
    search_fields = ("user__username", "user__email")
    readonly_fields = (
        "total_items_count",
        "unique_items_count",
        "subtotal",
        "total_original_price",
        "total_savings",
        "created_at",
        "updated_at",
    )
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "quantity", "subtotal", "created_at")
    search_fields = ("product__name", "cart__user__username")
    list_filter = ("created_at",)
