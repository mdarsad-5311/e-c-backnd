from django.conf import settings
from django.db import models


class Address(models.Model):
    """
    Model representing a shipping / billing address for an authenticated user.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
        help_text="User who owns this address"
    )
    full_name = models.CharField(max_length=255, help_text="Recipient full name")
    phone_number = models.CharField(max_length=30, blank=True, default="", help_text="Contact phone number")
    street_address = models.CharField(max_length=255, help_text="Street address / line 1")
    city = models.CharField(max_length=100, help_text="City")
    state = models.CharField(max_length=100, blank=True, default="", help_text="State / Province / Region")
    postal_code = models.CharField(max_length=30, help_text="Postal / ZIP code")
    country = models.CharField(max_length=100, help_text="Country")
    is_default = models.BooleanField(default=False, help_text="Whether this is the default shipping address")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

    def __str__(self):
        return f"{self.full_name} - {self.street_address}, {self.city} ({self.user.username})"

    def save(self, *args, **kwargs):
        # If this is the user's first address, automatically make it default
        if not self.pk and not Address.objects.filter(user=self.user).exists():
            self.is_default = True

        # If marked as default, unset is_default on any existing addresses of this user
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)
