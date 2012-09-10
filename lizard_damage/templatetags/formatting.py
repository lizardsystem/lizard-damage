from django import template

register = template.Library()

@register.filter()
def euroformat(value):
    if value > 10000000:
        return '&euro; %0.0f miljoen' % (value/1000000.0)
    if value > 1000000:
        return '&euro; %0.1f miljoen' % (value/1000000.0)
    if value > 10000:
        return '&euro; %0.0f duizend' % (value/1000.0)
    if value > 1000:
        return '&euro; %0.1f duizend' % (value/1000.0)

    return '&euro; %0.0f' % (value)


@register.filter
def haformat(value):
    """
    Hectare format, do not mix up with the "Jack Ha" Format.
    """
    if value > 1:
        return '%0.0f ha' % value
    if value == 0.0:
        return '0 ha'
    return '%0.1f ha' % value


@register.filter
def hoursformat(value):
    if value:
        return '%0.f uur' % (value / 3600.0)
    else:
        return '-'


@register.filter
def daysformat(value):
    if value:
        return '%0.f dag(en)' % (value / 3600.0 / 24.0)
    else:
        return '-'


@register.filter
def monthformat(value):
    month_dict = {
        1: 'januari',
        2: 'februari',
        3: 'maart',
        4: 'april',
        5: 'mei',
        6: 'juni',
        7: 'juli',
        8: 'augustus',
        9: 'september',
        10: 'oktober',
        11: 'november',
        12: 'december'}
    return month_dict.get(value, value)
