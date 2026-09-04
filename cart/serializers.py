from decimal import Decimal
from rest_framework import serializers

from products.models import Product
from products.serializers import ProductListSerializer
from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    """
    Serializer representing a single item in a shopping cart with nested product details.
    """
    product = ProductListSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    original_price_subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    originalPriceSubtotal = serializers.DecimalField(
        source="original_price_subtotal", max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "quantity",
            "subtotal",
            "original_price_subtotal",
            "originalPriceSubtotal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "subtotal", "created_at", "updated_at"]


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer representing full user cart with nested items and server-side summary calculations.
    """
    items = CartItemSerializer(many=True, read_only=True)
    total_items_count = serializers.IntegerField(read_only=True)
    totalItemsCount = serializers.IntegerField(source="total_items_count", read_only=True)
    item_count = serializers.IntegerField(source="total_items_count", read_only=True)
    itemCount = serializers.IntegerField(source="total_items_count", read_only=True)
    unique_items_count = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_original_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    totalOriginalPrice = serializers.DecimalField(source="total_original_price", max_digits=12, decimal_places=2, read_only=True)
    total_savings = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    totalSavings = serializers.DecimalField(source="total_savings", max_digits=12, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_items_count",
            "totalItemsCount",
            "item_count",
            "itemCount",
            "unique_items_count",
            "subtotal",
            "total_original_price",
            "totalOriginalPrice",
            "total_savings",
            "totalSavings",
            "total",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AddToCartSerializer(serializers.Serializer):
    """
    Serializer for validating product additions to cart.
    """
    product_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(default=1, min_value=1)

    def validate_product_id(self, value):
        try:
            product = Product.objects.select_related("category").get(id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found.")

        if not product.is_active or not product.category.is_active:
            raise serializers.ValidationError("This product is currently unavailable.")

        if product.stock <= 0:
            raise serializers.ValidationError("This product is out of stock.")

        return value

    def validate(self, attrs):
        product_id = attrs.get("product_id")
        quantity = attrs.get("quantity", 1)

        if quantity < 1:
            raise serializers.ValidationError({"quantity": "Quantity must be at least 1."})

        product = Product.objects.get(id=product_id)
        if quantity > product.stock:
            raise serializers.ValidationError(
                {"quantity": f"Only {product.stock} units available in stock."}
            )

        return attrs


class UpdateCartItemSerializer(serializers.Serializer):
    """
    Serializer for updating cart item quantity.
    """
    quantity = serializers.IntegerField(required=True)

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be a positive integer (at least 1).")
        return value
