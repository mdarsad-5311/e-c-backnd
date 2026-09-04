from rest_framework import serializers
from categories.models import Category
from .models import Product, ProductImage


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "is_primary", "sort_order"]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class ProductListSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="name", read_only=True)
    original_price = serializers.DecimalField(source="compare_at_price", max_digits=10, decimal_places=2, read_only=True)
    originalPrice = serializers.DecimalField(source="compare_at_price", max_digits=10, decimal_places=2, read_only=True)
    category = ProductCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    categoryName = serializers.CharField(source="category.name", read_only=True)
    image = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()
    discountPercentage = serializers.SerializerMethodField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True)
    averageRating = serializers.DecimalField(source="average_rating", max_digits=3, decimal_places=2, read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    reviewCount = serializers.IntegerField(source="review_count", read_only=True)
    reviewsCount = serializers.IntegerField(source="reviews_count", read_only=True)
    isFeatured = serializers.BooleanField(source="is_featured", read_only=True)
    isBestSeller = serializers.SerializerMethodField()
    badge = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "title",
            "slug",
            "price",
            "compare_at_price",
            "original_price",
            "originalPrice",
            "discount_percentage",
            "discountPercentage",
            "stock",
            "is_in_stock",
            "category",
            "category_id",
            "category_name",
            "categoryName",
            "brand",
            "rating",
            "average_rating",
            "averageRating",
            "reviews_count",
            "review_count",
            "reviewCount",
            "reviewsCount",
            "image",
            "is_featured",
            "isFeatured",
            "isBestSeller",
            "badge",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "created_at"]
        extra_kwargs = {"slug": {"required": False}}

    def get_image(self, obj):
        primary = obj.primary_image
        if primary and primary.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(primary.image.url)
            return primary.image.url
        return None

    def get_discount_percentage(self, obj):
        if obj.compare_at_price and obj.compare_at_price > obj.price:
            diff = obj.compare_at_price - obj.price
            return int(round((diff / obj.compare_at_price) * 100))
        return 0

    def get_discountPercentage(self, obj):
        return self.get_discount_percentage(obj)

    def get_isBestSeller(self, obj):
        return obj.is_featured or obj.reviews_count >= 100

    def get_badge(self, obj):
        if obj.is_featured:
            return "BESTSELLER"
        disc = self.get_discount_percentage(obj)
        if disc >= 15:
            return "SALE"
        return ""


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    gallery_images = serializers.SerializerMethodField()
    galleryImages = serializers.SerializerMethodField()
    latest_reviews = serializers.SerializerMethodField()
    latestReviews = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description",
            "sku",
            "images",
            "gallery_images",
            "galleryImages",
            "latest_reviews",
            "latestReviews",
            "updated_at",
        ]

    def get_gallery_images(self, obj):
        request = self.context.get("request")
        urls = []
        for img in obj.images.all():
            if img.image:
                if request:
                    urls.append(request.build_absolute_uri(img.image.url))
                else:
                    urls.append(img.image.url)
        return urls

    def get_galleryImages(self, obj):
        return self.get_gallery_images(obj)

    def get_latest_reviews(self, obj):
        from reviews.serializers import ReviewSerializer
        reviews = obj.reviews.select_related("user").order_by("-created_at")[:5]
        return ReviewSerializer(reviews, many=True, context=self.context).data

    def get_latestReviews(self, obj):
        return self.get_latest_reviews(obj)

