from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """
    Admin configuration for inspecting and managing product customer reviews.
    """
    list_display = [
        "id",
        "product",
        "user",
        "rating",
        "is_verified_purchase",
        "created_at",
    ]
    list_filter = [
        "rating",
        "is_verified_purchase",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "user__username",
        "user__email",
        "product__name",
        "title",
        "comment",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
