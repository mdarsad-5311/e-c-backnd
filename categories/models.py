from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """
    Model representing a product category in the e-commerce catalog.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Unique category name")
    slug = models.SlugField(max_length=120, unique=True, blank=True, db_index=True, help_text="URL-friendly identifier")
    description = models.TextField(blank=True, default="", help_text="Category description")
    image = models.ImageField(upload_to="categories/", blank=True, null=True, help_text="Category banner or representative image")
    icon = models.CharField(max_length=50, blank=True, default="", help_text="Icon identifier for frontend rendering")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Whether category is active and visible")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or "category"
        base_slug = self.slug
        slug = base_slug
        counter = 1
        while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        self.slug = slug
        super().save(*args, **kwargs)
