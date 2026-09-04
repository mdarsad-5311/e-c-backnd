from rest_framework import serializers
from orders.models import Order, OrderItem
from products.models import Product
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """
    Standard serializer for viewing product reviews.
    """
    user_name = serializers.CharField(read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "product",
            "product_name",
            "user",
            "user_id",
            "user_name",
            "rating",
            "title",
            "comment",
            "is_verified_purchase",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "product",
            "product_name",
            "user",
            "user_id",
            "user_name",
            "is_verified_purchase",
            "created_at",
            "updated_at",
        ]


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new Review on a product by an authenticated verified purchaser.
    """
    rating = serializers.IntegerField(
        min_value=1,
        max_value=5,
        required=True,
        help_text="Rating score from 1 (lowest) to 5 (highest)",
    )
    title = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=255,
    )
    comment = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="Detailed review commentary",
    )

    class Meta:
        model = Review
        fields = ["id", "rating", "title", "comment"]

    def validate(self, attrs):
        user = self.context["request"].user
        product = self.context.get("product")

        if not product:
            raise serializers.ValidationError({"detail": "Product is required."})

        # 1. Prevent duplicate reviews by same user
        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError(
                {"detail": "You have already reviewed this product."}
            )

        # 2. Verified purchase validation: user must have bought product in a non-cancelled order
        has_purchased = OrderItem.objects.filter(
            order__user=user,
            product=product,
        ).exclude(order__status=Order.OrderStatus.CANCELLED).exists()

        if not has_purchased:
            raise serializers.ValidationError(
                {"detail": "Only verified buyers can review this product."}
            )

        return attrs


class ReviewUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for editing an existing Review by its author or admin.
    """
    rating = serializers.IntegerField(
        min_value=1,
        max_value=5,
        required=False,
        help_text="Updated rating score (1-5)",
    )
    title = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=False,
    )

    class Meta:
        model = Review
        fields = ["id", "rating", "title", "comment", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class ReviewHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for displaying the user's review history.
    """
    user_name = serializers.CharField(read_only=True)
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "product_id",
            "product_name",
            "product_slug",
            "product_image",
            "user_name",
            "rating",
            "title",
            "comment",
            "is_verified_purchase",
            "created_at",
            "updated_at",
        ]

    def get_product_image(self, obj):
        primary = obj.product.primary_image
        if primary and primary.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(primary.image.url)
            return primary.image.url
        return None
