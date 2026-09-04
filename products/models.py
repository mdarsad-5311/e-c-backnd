from django.db import models
from django.utils.text import slugify


class Product(models.Model):
    """
    Model representing an item in the e-commerce catalog.
    """
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.CASCADE,
        related_name="products",
        db_index=True,
        help_text="Primary category for this product"
    )
    name = models.CharField(max_length=255, help_text="Product title / name")
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True, help_text="URL-friendly identifier")
    description = models.TextField(blank=True, default="", help_text="Detailed product description")
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True, help_text="Selling price")
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Original or compare-at price before discount"
    )
    stock = models.PositiveIntegerField(default=0, help_text="Available stock quantity")
    brand = models.CharField(max_length=100, blank=True, default="", help_text="Product brand / manufacturer")
    sku = models.CharField(max_length=100, blank=True, default="", help_text="Stock Keeping Unit")
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, help_text="Average rating score (0.00 - 5.00)")
    reviews_count = models.PositiveIntegerField(default=0, help_text="Total number of customer reviews")
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text="Average customer rating (0.00 - 5.00)"
    )
    review_count = models.PositiveIntegerField(
        default=0,
        help_text="Total count of customer reviews"
    )
    is_active = models.BooleanField(default=True, db_index=True, help_text="Whether product is active and visible")

    is_featured = models.BooleanField(default=False, db_index=True, help_text="Whether product is featured on home/promos")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return self.name

    @property
    def title(self):
        """Frontend alias for name"""
        return self.name

    @property
    def is_in_stock(self):
        return self.stock > 0

    @property
    def primary_image(self):
        """Returns the primary ProductImage or the first available image"""
        primary = self.images.filter(is_primary=True).first()
        if not primary:
            primary = self.images.first()
        return primary

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or "product"
        base_slug = self.slug
        slug = base_slug
        counter = 1
        while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        self.slug = slug
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    """
    Model representing gallery images associated with a product.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        help_text="Product this image belongs to"
    )
    image = models.ImageField(upload_to="products/", help_text="Uploaded product image file")
    alt_text = models.CharField(max_length=255, blank=True, default="", help_text="Descriptive alt text for accessibility and SEO")
    is_primary = models.BooleanField(default=False, help_text="Flag indicating whether this is the main product thumbnail")
    sort_order = models.PositiveIntegerField(default=0, help_text="Order in which images appear in gallery")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"Image for {self.product.name} (Primary: {self.is_primary})"

    def save(self, *args, **kwargs):
        # If this is the only image for the product, automatically set as primary
        if not self.pk and not ProductImage.objects.filter(product=self.product).exists():
            self.is_primary = True

        # If marked as primary, unset is_primary on other images of this product
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)

        super().save(*args, **kwargs)
