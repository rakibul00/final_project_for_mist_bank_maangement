from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter(name='sum')
def sum_field(queryset, field):
    """Return the sum of `field` values for objects in `queryset` as Decimal.

    Usage in template: {{ queryset|sum:"total_amount" }}
    Non-numeric or missing values are ignored.
    """
    total = Decimal('0.00')
    if not queryset:
        return total

    # Handle RelatedManager by getting the queryset
    if hasattr(queryset, 'all'):
        queryset = queryset.all()

    for obj in queryset:
        try:
            value = getattr(obj, field, 0)
            if value is None:
                continue
            if isinstance(value, Decimal):
                total += value
            else:
                total += Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            continue

    return total


@register.filter
def sub(value, arg):
    """Subtract arg from value."""
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except:
        return value