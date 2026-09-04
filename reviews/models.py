from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """
    Model representing a customer rating and review for a specific product.
    Enforces 1 review per product per user with verified purchase tracking.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        db_index=True,
        help_text="Customer who authored this review",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
        db_index=True,
        help_text="Product being reviewed",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Star rating from 1 to 5",
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Headline or brief title for the review",
    )
    comment = models.TextField(
        help_text="Detailed feedback and thoughts on the product",
    )
    is_verified_purchase = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if the reviewer purchased this product in a completed/valid order",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_product_review",
            )
        ]
        indexes = [
            models.Index(fields=["product"], name="idx_review_product"),
            models.Index(fields=["user"], name="idx_review_user"),
            models.Index(fields=["created_at"], name="idx_review_created_at"),
        ]

    def __str__(self):
        return f"{self.user_name}'s {self.rating}★ review for {self.product.name}"


    @property
    def user_name(self) -> str:
        """Returns reviewer's full name if available, otherwise username."""
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        return full_name or self.user.username
