from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from .models import Show, Track
from .utils import indefinitely


def get_sections(request):
    active_section = None
    most_recent_track = Track.objects.public().latest('revealed')

    if (
        hasattr(request, 'resolver_match') and
        hasattr(request.resolver_match, 'func')
    ):
        for cell in request.resolver_match.func.__closure__:
            thing = cell.cell_contents
            if hasattr(thing, 'section'):
                active_section = thing.section
                break

    return [{
        'name': section[0],
        'url': section[1],
        'active': section[0] == active_section
    } for section in [
        (_('home'), reverse('vote:index')),
        (_('archive'), reverse('vote:archive')),
        (_('new tracks'), most_recent_track.show_revealed().get_revealed_url()),
        (_('roulette'), reverse('vote:roulette', kwargs={'mode': 'hipster'})),
        (_('stats'), reverse('vote:stats')),
        (_('etc'), 'http://nekodesu.co.uk/'),
    ]]


def get_parent(request):
    if request.META.get('HTTP_X_PJAX', False):
        return 'pjax.html'
    else:
        return 'base.html'


def nkdsu_context_processor(request):
    """
    Add common stuff to context.
    """

    current_show = Show.current()

    return {
        'current_show': current_show,
        'vote_show': current_show,
        'sections': get_sections(request),
        'indefinitely': indefinitely,
        'parent': get_parent(request),
    }
