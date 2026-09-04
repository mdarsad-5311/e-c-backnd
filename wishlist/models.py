from django.conf import settings
from django.db import models


class WishlistItem(models.Model):
    """
    Model representing a saved product in an authenticated user's wishlist.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
        help_text="User who saved this item"
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="wishlist_items",
        help_text="Saved product"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Wishlist Item"
        verbose_name_plural = "Wishlist Items"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_wishlist_product"
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"
