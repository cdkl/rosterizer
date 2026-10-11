"""Template filters used by the v2 roster templates."""

from django import template

register = template.Library()


@register.filter
def pct(value):
    """Render a 0..1 score as a whole-number percentage for a CSS width."""
    try:
        return f'{round(float(value) * 100)}%'
    except (TypeError, ValueError):
        return '0%'


@register.filter
def score_class(value):
    """Colour band for a 0..1 score: green at 0.9+, amber at 0.7+, else red."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 'bg-danger'
    if number >= 0.9:
        return 'bg-success'
    if number >= 0.7:
        return 'bg-warning'
    return 'bg-danger'


@register.filter
def pref_label(value):
    """Preference fit (1.0, 0.5, 0.0) to a short display label."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return '\u2014'
    if number >= 0.99:
        return '1st'
    if number >= 0.49:
        return '2nd'
    return '\u2014'