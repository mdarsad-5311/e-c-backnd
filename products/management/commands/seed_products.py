import io
from decimal import Decimal
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from PIL import Image, ImageDraw

from categories.models import Category
from products.models import Product, ProductImage


def create_sample_image(text="Product Image", color=(40, 70, 150)):
    """Generate a small valid JPEG in memory for seeding product images"""
    img = Image.new("RGB", (400, 400), color=color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 380, 380], outline=(255, 255, 255), width=4)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    file_name = f"{slugify(text) or 'sample'}.jpg"
    return ContentFile(buffer.getvalue(), name=file_name)


class Command(BaseCommand):
    help = "Seeds initial sample categories, products, and images for development and testing."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting Product Catalog seeding..."))

        # 1. Categories
        categories_data = [
            {
                "name": "Electronics",
                "slug": "electronics",
                "icon": "Monitor",
                "description": "High-performance headphones, smart home tech, keyboards, and gadgets.",
            },
            {
                "name": "Fashion",
                "slug": "fashion",
                "icon": "Shirt",
                "description": "Trending streetwear, sneakers, and designer apparel.",
            },
            {
                "name": "Home Goods",
                "slug": "home-goods",
                "icon": "Home",
                "description": "Modern home appliances, smart oral care, and decor.",
            },
            {
                "name": "Deals",
                "slug": "deals",
                "icon": "Sparkles",
                "description": "Exclusive discounts, flash sales, and bundle offers.",
            },
            {
                "name": "New Arrivals",
                "slug": "new-arrivals",
                "icon": "Sparkles",
                "description": "Freshly dropped gear, new releases, and innovations.",
            },
        ]

        created_cats = {}
        for cat_info in categories_data:
            cat, created = Category.objects.get_or_create(
                slug=cat_info["slug"],
                defaults={
                    "name": cat_info["name"],
                    "icon": cat_info["icon"],
                    "description": cat_info["description"],
                    "is_active": True,
                },
            )
            created_cats[cat_info["slug"]] = cat
            status_text = "Created" if created else "Exists"
            self.stdout.write(f" - Category: {cat.name} ({status_text})")

        # 2. Products
        products_data = [
            {
                "category_slug": "electronics",
                "name": "Quantum Pro Noise Cancelling Headphones",
                "slug": "quantum-pro-noise-cancelling-headphones",
                "description": "Industry-leading active noise cancellation with high-resolution audio, custom 40mm titanium drivers, and up to 40 hours of battery life.",
                "price": Decimal("349.99"),
                "compare_at_price": Decimal("399.99"),
                "stock": 45,
                "brand": "Sony",
                "sku": "AUD-QPRO-001",
                "rating": Decimal("4.90"),
                "reviews_count": 318,
                "is_featured": True,
                "color": (25, 45, 90),
            },
            {
                "category_slug": "electronics",
                "name": "Aura Smart Home Speaker",
                "slug": "aura-smart-home-speaker",
                "description": "360-degree room-filling acoustic sound with smart voice assistant integration and multi-room synchronization.",
                "price": Decimal("199.99"),
                "compare_at_price": Decimal("249.99"),
                "stock": 30,
                "brand": "Aura",
                "sku": "SPK-AURA-002",
                "rating": Decimal("4.75"),
                "reviews_count": 142,
                "is_featured": True,
                "color": (40, 80, 120),
            },
            {
                "category_slug": "electronics",
                "name": "Apex Pro Mechanical Gaming Keyboard",
                "slug": "apex-pro-mechanical-gaming-keyboard",
                "description": "Ultra-fast magnetic switches with adjustable actuation distance, per-key RGB lighting, and aircraft-grade aluminum alloy frame.",
                "price": Decimal("189.99"),
                "compare_at_price": Decimal("219.99"),
                "stock": 25,
                "brand": "SteelSeries",
                "sku": "KBD-APEX-003",
                "rating": Decimal("4.85"),
                "reviews_count": 89,
                "is_featured": False,
                "color": (30, 30, 60),
            },
            {
                "category_slug": "fashion",
                "name": "Urban Techwear Oversized Hoodie",
                "slug": "urban-techwear-oversized-hoodie",
                "description": "Heavyweight 450 GSM French terry cotton with water-repellent coating and ergonomic storage pockets.",
                "price": Decimal("89.99"),
                "compare_at_price": Decimal("120.00"),
                "stock": 60,
                "brand": "Aesthetic Wear",
                "sku": "FSH-HOOD-004",
                "rating": Decimal("4.70"),
                "reviews_count": 64,
                "is_featured": True,
                "color": (70, 70, 75),
            },
            {
                "category_slug": "fashion",
                "name": "Minimalist Canvas Low-Top Sneakers",
                "slug": "minimalist-canvas-low-top-sneakers",
                "description": "Clean lines, vulcanized rubber sole, cushioned memory foam insole for all-day comfort.",
                "price": Decimal("75.00"),
                "compare_at_price": Decimal("95.00"),
                "stock": 40,
                "brand": "FootLab",
                "sku": "SNK-MINI-005",
                "rating": Decimal("4.60"),
                "reviews_count": 52,
                "is_featured": False,
                "color": (120, 100, 80),
            },
            {
                "category_slug": "home-goods",
                "name": "Ceramic Pour-Over Coffee Brewer Set",
                "slug": "ceramic-pour-over-coffee-brewer-set",
                "description": "Artisanal hand-crafted matte ceramic dripper with borosilicate heat-resistant glass carafe and stainless steel filter.",
                "price": Decimal("54.99"),
                "compare_at_price": Decimal("69.99"),
                "stock": 20,
                "brand": "BrewMaster",
                "sku": "HMG-BREW-006",
                "rating": Decimal("4.92"),
                "reviews_count": 110,
                "is_featured": True,
                "color": (140, 90, 60),
            },
            {
                "category_slug": "home-goods",
                "name": "Smart Ultrasonic Aromatherapy Diffuser",
                "slug": "smart-ultrasonic-aromatherapy-diffuser",
                "description": "Whisper-quiet ultrasonic mist generator with ambient LED lighting, auto shut-off, and scheduling app.",
                "price": Decimal("39.99"),
                "compare_at_price": Decimal("49.99"),
                "stock": 0,  # Out of stock to test stock filters!
                "brand": "ZenHome",
                "sku": "HMG-DIFF-007",
                "rating": Decimal("4.50"),
                "reviews_count": 37,
                "is_featured": False,
                "color": (100, 130, 110),
            },
        ]

        for p_info in products_data:
            cat = created_cats.get(p_info["category_slug"])
            product, created = Product.objects.get_or_create(
                slug=p_info["slug"],
                defaults={
                    "category": cat,
                    "name": p_info["name"],
                    "description": p_info["description"],
                    "price": p_info["price"],
                    "compare_at_price": p_info["compare_at_price"],
                    "stock": p_info["stock"],
                    "brand": p_info["brand"],
                    "sku": p_info["sku"],
                    "rating": p_info["rating"],
                    "reviews_count": p_info["reviews_count"],
                    "is_featured": p_info["is_featured"],
                    "is_active": True,
                },
            )

            status_text = "Created" if created else "Exists"
            self.stdout.write(f" - Product: {product.name} ({status_text})")

            # Seed sample image if none exists
            if not product.images.exists():
                img_file = create_sample_image(
                    text=product.name, color=p_info.get("color", (50, 70, 100))
                )
                ProductImage.objects.create(
                    product=product,
                    image=img_file,
                    alt_text=f"{product.name} thumbnail",
                    is_primary=True,
                    sort_order=0,
                )
                # Seed a second gallery image
                gallery_img_file = create_sample_image(
                    text=f"{product.name} detail", color=(80, 80, 80)
                )
                ProductImage.objects.create(
                    product=product,
                    image=gallery_img_file,
                    alt_text=f"{product.name} alternate view",
                    is_primary=False,
                    sort_order=1,
                )
                self.stdout.write(f"   -> Added 2 gallery images for {product.name}")

        self.stdout.write(self.style.SUCCESS("Successfully seeded product catalog!"))
