from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product_name",
        "product_sku",
        "unit_price",
        "quantity",
        "subtotal",
        "created_at",
    )
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "status",
        "total_amount",
        "payment_method",
        "payment_status",
        "tracking_number",
        "created_at",
    )
    list_filter = ("status", "payment_status", "created_at")
    search_fields = (
        "order_number",
        "user__username",
        "user__email",
        "shipping_full_name",
        "tracking_number",
    )
    readonly_fields = (
        "order_number",
        "created_at",
        "updated_at",
        "subtotal",
        "shipping_cost",
        "tax_amount",
        "total_amount",
    )
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "product_name",
        "unit_price",
        "quantity",
        "subtotal",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("product_name", "product_sku", "order__order_number")
