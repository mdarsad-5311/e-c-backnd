from rest_framework import serializers
from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category model with computed product counts and frontend aliases.
    """
    item_count = serializers.SerializerMethodField()
    itemCount = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "image",
            "icon",
            "is_active",
            "item_count",
            "itemCount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"slug": {"required": False}}

    def get_item_count(self, obj):
        # Count only active products in this category
        if hasattr(obj, "active_products_count"):
            return obj.active_products_count
        return obj.products.filter(is_active=True).count()

    def get_itemCount(self, obj):
        return self.get_item_count(obj)

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class CategoryDetailSerializer(CategorySerializer):
    """
    Detailed serializer for category including active products.
    """
    pass
