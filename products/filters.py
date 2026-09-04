from django.db.models import Q
from rest_framework import filters


class ProductFilterBackend(filters.BaseFilterBackend):
    """
    Custom filter backend handling search, category (id or slug), price ranges, featured, and stock.
    """
    def filter_queryset(self, request, queryset, view):
        params = request.query_params

        # 1. Search Query (?search= or ?q=)
        search = params.get("search") or params.get("q")
        if search:
            search = search.strip()
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(category__name__icontains=search) |
                Q(brand__icontains=search)
            )

        # 2. Category Filter (?category=id_or_slug)
        category_param = params.get("category")
        if category_param:
            category_param = category_param.strip()
            if category_param.isdigit():
                queryset = queryset.filter(
                    Q(category_id=int(category_param)) | Q(category__slug=category_param)
                )
            else:
                queryset = queryset.filter(category__slug=category_param)

        # 3. Price Filter (?min_price= & ?max_price=)
        min_price = params.get("min_price")
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass

        max_price = params.get("max_price")
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass

        # 4. Featured Filter (?is_featured=true / ?featured=true)
        featured = params.get("is_featured") or params.get("featured")
        if featured is not None:
            if featured.lower() in ["true", "1", "yes"]:
                queryset = queryset.filter(is_featured=True)
            elif featured.lower() in ["false", "0", "no"]:
                queryset = queryset.filter(is_featured=False)

        # 5. In-Stock Filter (?in_stock=true)
        in_stock = params.get("in_stock")
        if in_stock is not None:
            if in_stock.lower() in ["true", "1", "yes"]:
                queryset = queryset.filter(stock__gt=0)
            elif in_stock.lower() in ["false", "0", "no"]:
                queryset = queryset.filter(stock=0)

        # 6. Ordering (?ordering=)
        ordering = params.get("ordering")
        allowed_orderings = {
            "price": "price",
            "-price": "-price",
            "price_low_to_high": "price",
            "price_high_to_low": "-price",
            "newest": "-created_at",
            "-created_at": "-created_at",
            "created_at": "created_at",
            "name": "name",
            "-name": "-name",
            "rating": "-rating",
            "-rating": "-rating",
        }
        if ordering in allowed_orderings:
            queryset = queryset.order_by(allowed_orderings[ordering])

        return queryset
