from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Admin interface for managing and inspecting Payment transactions.
    """
    list_display = [
        "id",
        "user",
        "order",
        "amount",
        "currency",
        "status",
        "razorpay_order_id",
        "razorpay_payment_id",
        "created_at",
    ]
    list_filter = [
        "status",
        "currency",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "razorpay_order_id",
        "razorpay_payment_id",
        "razorpay_signature",
        "user__username",
        "user__email",
        "order__order_number",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
