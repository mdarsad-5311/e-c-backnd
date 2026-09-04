from rest_framework import serializers

from products.models import Product
from products.serializers import ProductListSerializer
from .models import WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    """
    Serializer representing a wishlist item with nested product details.
    """
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = WishlistItem
        fields = ["id", "product", "created_at"]
        read_only_fields = ["id", "created_at"]


class AddWishlistSerializer(serializers.Serializer):
    """
    Serializer for validating product addition to wishlist.
    """
    product_id = serializers.IntegerField(required=True)

    def validate_product_id(self, value):
        try:
            product = Product.objects.select_related("category").get(id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found.")

        if not product.is_active or not product.category.is_active:
            raise serializers.ValidationError("This product is currently unavailable.")

        return value
