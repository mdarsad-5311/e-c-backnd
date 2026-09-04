from decimal import Decimal
from django.db import transaction
from django.db.models import Avg, Count
from products.models import Product


def recalculate_product_ratings(product_id: int) -> None:
    """
    Transaction-safely recalculates and updates average_rating, review_count,
    rating, and reviews_count on the target Product.
    """
    from .models import Review

    with transaction.atomic():
        stats = Review.objects.filter(product_id=product_id).aggregate(
            avg_rating=Avg("rating"),
            count=Count("id"),
        )
        avg = stats["avg_rating"]
        count = stats["count"] or 0

        if avg is not None:
            avg_val = Decimal(str(round(avg, 2)))
        else:
            avg_val = Decimal("0.00")

        Product.objects.filter(id=product_id).update(
            average_rating=avg_val,
            review_count=count,
            rating=avg_val,
            reviews_count=count,
        )
