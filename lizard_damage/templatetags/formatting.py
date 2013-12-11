from django import template

register = template.Library()


def split_len(seq, length):
    """splits a string into length sized strings, beginning at the end"""
    result = [seq[max(i - length, 0):i] for i in range(len(seq), 0, -length)]
    result.reverse()
    return result


@register.filter()
def euroformat(value):
    value_str = '%0.0f' % value
    return '&euro; %s,-' % ('.'.join(split_len(value_str, 3)))


@register.filter
def haformat(value):
    """
    Hectare format, do not mix up with the "Jack Ha" Format.
    """
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
    if not value:
        return '-'
    if value < 1 * 3600 * 24:
        return '%0.f uur' % (value / 3600.0)
    else:
        return '%0.f dag(en)' % (value / 24.0 / 3600.0)


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
