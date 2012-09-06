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
