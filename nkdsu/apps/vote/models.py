# -*- coding: utf-8 -*-

import datetime
import re
import json

from cache_utils.decorators import cached

from django.db import models
from django.utils import timezone
from django.template.defaultfilters import slugify
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse

from nkdsu.apps.vote.utils import (
    length_str, split_id3_title, vote_tweet_intent_url, reading_tw_api,
    memoize, split_query_into_keywords
)


class Show(models.Model):
    """
    A broadcast of the show and, by extention, the week leading up to it.
    """

    showtime = models.DateTimeField()
    end = models.DateTimeField()

    def __str__(self):
        return '<Show for %r>' % (self.showtime.date())

    def __repr__(self):
        return str(self)

    def clean(self):
        pass  # XXX refuse to create overlapping shows

    @classmethod
    def current(cls):
        """
        Get (or create, if necessary) the show that will next end.
        """

        return cls.at(timezone.now())

    @classmethod
    def _at(cls, time, create=True):
        """
        Get (or create, if necessary) the show for `time`. Use .at() instead.
        """

        shows_after_time = cls.objects.filter(end__gt=time)
        if shows_after_time.exists():
            show = shows_after_time.order_by('showtime')[0]
        elif create:
            # We have to switch to naive and back to make relativedelta
            # look for the local showtime. If we did not, showtime would be
            # calculated against UTC.
            naive_time = timezone.make_naive(time,
                                             timezone.get_current_timezone())
            naive_end = naive_time + settings.SHOW_END

            # Work around an unfortunate shortcoming of dateutil where
            # specifying a time on a weekday won't increment the weekday even
            # if our initial time is after that time.
            while naive_end < naive_time:
                naive_time += datetime.timedelta(hours=1)
                naive_end = naive_time + settings.SHOW_END

            naive_showtime = naive_end - settings.SHOWTIME

            our_end = timezone.make_aware(naive_end,
                                          timezone.get_current_timezone())
            our_showtime = timezone.make_aware(naive_showtime,
                                               timezone.get_current_timezone())
            show = cls()
            show.end = our_end
            show.showtime = our_showtime
            show.save()
        else:
            show = None

        return show

    @classmethod
    def at(cls, time):
        """
        Get the show for the date specified, creating every intervening show
        in the process if necessary.
        """

        if Show.objects.all().exists():
            last_show = cls.objects.all().order_by('-end')[0]
        else:
            return cls._at(time)  # this is the first show!

        if time <= last_show.end:
            return cls._at(time)

        show = last_show

        while show.end < time:
            show = show.next(create=True)

        return show

    @classmethod
    def broadcasting_any(cls, time=None):
        """
        Return True if a show is broadcasting.
        """

        return cls.at(time).broadcasting(time)

    @memoize
    def broadcasting(self, time=None):
        """
        Return True if the time specified is during this week's show.
        """

        if time is None:
            time = timezone.now()

        return (time >= self.showtime) and (time < self.end)

    @memoize
    def next(self, create=False):
        """
        Return the next Show.
        """

        return Show._at(self.end + datetime.timedelta(microseconds=1), create)

    @memoize
    def prev(self):
        """
        Return the previous Show.
        """

        qs = Show.objects.filter(end__lt=self.end)

        if qs.exists():
            return qs.order_by('-showtime')[0]
        else:
            return None

    def has_ended(self):
        return timezone.now() > self.end

    def _date_kwargs(self, attr='date'):
        """
        The kwargs you would hand to a queryset to find objects applicable to
        this show.
        """

        kw = {'%s__lte' % attr: self.end}

        if self.prev() is not None:
            kw['%s__gt' % attr] = self.prev().end

        return kw

    @memoize
    def votes(self):
        return Vote.objects.filter(**self._date_kwargs())

    @memoize
    def plays(self):
        return Play.objects.filter(**self._date_kwargs()).order_by('date')

    @memoize
    def playlist(self):
        return (p.track for p in self.plays())

    @memoize
    def tracks_sorted_by_votes(self, exclude_abusers=False):
        """
        Return a list of tracks that have been voted for this week, in order of
        when they were last voted for, starting from the most recent.
        """

        tracks_and_dates = {}

        for vote in self.votes():
            for track in vote.tracks.all():
                date = tracks_and_dates.get(track)
                if date is None or date < vote.date:
                    tracks_and_dates[track] = vote.date

        return sorted(tracks_and_dates.iterkeys(),
                      key=lambda t: tracks_and_dates[t],
                      reverse=True)

    @memoize
    def revealed(self, show_hidden=False):
        """
        Return a all public (unhidden, non-inudesu) tracks revealed in the
        library this week.
        """

        return Track.objects.filter(hidden=False, inudesu=False,
                                    **self._date_kwargs('revealed'))

    def get_absolute_url(self):
        return reverse('vote:show', kwargs={
            'date': self.showtime.date().strftime('%Y-%m-%d')
        })

    def get_added_url(self):
        return reverse('vote:added', kwargs={
            'date': self.showtime.date().strftime('%Y-%m-%d')
        })


class TwitterUser(models.Model):
    # Twitter stuff
    screen_name = models.CharField(max_length=100)
    user_id = models.BigIntegerField(unique=True)
    user_image = models.URLField()
    name = models.CharField(max_length=20)

    # nkdsu stuff
    is_abuser = models.BooleanField(default=False)
    updated = models.DateTimeField()

    def __unicode__(self):
        return unicode(self.screen_name)

    def __repr__(self):
        return self.screen_name

    def twitter_url(self):
        return 'https://twitter.com/%s' % self.screen_name

    def get_absolute_url(self):
        return reverse('vote:user', kwargs={'screen_name': self.screen_name})

    @memoize
    def votes(self):
        return self.vote_set.order_by('-date')

    @memoize
    def _batting_average(self, cutoff=None, minimum_weight=1):
        @cached(60*60)
        def ba(pk, cutoff):
            score = 0
            weight = 0

            for vote in self.vote_set.filter(date__gt=cutoff):
                success = vote.success()
                if success is not None:
                    score += success * vote.weight()
                    weight += vote.weight()

            return (score, weight)

        score, weight = ba(self.pk, cutoff)

        if weight >= minimum_weight:
            return score / weight
        else:
            # there were no worthwhile votes
            return None

        return score

    def batting_average(self, minimum_weight=1):
        """
        Return a user's batting average for the past six months.
        """

        return self._batting_average(
            cutoff=Show.at(timezone.now() - datetime.timedelta(days=31*6)).end,
            minimum_weight=minimum_weight
        )

    def all_time_batting_average(self, minimum_weight=1):
        return self._batting_average(minimum_weight=minimum_weight)

    def update_from_api(self):
        """
        Update this user's database object based on the Twitter API.
        """

        api_user = reading_tw_api.get_user(user_id=self.user_id)

        self.name = api_user.name
        self.screen_name = api_user.screen_name
        self.user_image = api_user.profile_image_url
        self.save()


class TrackManager(models.Manager):
    def public(self):
        return self.filter(hidden=False, inudesu=False)

    def search(self, query):
        keywords = split_query_into_keywords(query)

        if len(keywords) == 0:
            return []

        qs = self.public()

        for keyword in keywords:
            qs = qs.exclude(~models.Q(id3_title__icontains=keyword) &
                            ~models.Q(id3_artist__icontains=keyword))

        return qs


class Track(models.Model):
    objects = TrackManager()

    # derived from iTunes
    id = models.CharField(max_length=16, primary_key=True)
    id3_title = models.CharField(max_length=500)
    id3_artist = models.CharField(max_length=500)
    id3_album = models.CharField(max_length=500, blank=True)
    msec = models.IntegerField(blank=True, null=True)
    added = models.DateTimeField()

    # nkdsu-specific
    revealed = models.DateTimeField(blank=True, null=True)
    hidden = models.BooleanField()
    inudesu = models.BooleanField()

    def __unicode__(self):
        """
        The string that, for instance, would be tweeted
        """

        if self.role:
            return u'‘%s’ (%s) - %s' % (self.title, self.role, self.id3_artist)
        else:
            return u'‘%s’ - %s' % (self.title, self.id3_artist)

    def __eq__(self, other):
        return type(self) == type(other) and self.id == other.id

    def clean(self):
        # XXX require that if a track is not hidden, it has a revealed date
        # and vice-versa
        pass

    @property
    def is_new(self):
        current = Show.current()
        prev = current.prev()

        if prev is not None and self.revealed > prev.end:
            return True
        else:
            return False

    def length_str(self):
        return length_str(self.msec)

    @memoize
    def last_play(self):
        qs = self.play_set
        if qs.exists():
            return self.play_set.order_by('-date')[0]
        else:
            return None

    @memoize
    def plays(self):
        return self.play_set.order_by('date')

    @memoize
    def weeks_since_play(self):
        """
        Get the number of shows that have ended since this track's most recent
        Play.
        """

        if self.last_play() is None:
            return None

        count = 0
        show = Show.current()
        while show != self.last_play().show():
            count += 1
            show = show.prev()

        return count

    def blocks_for(self, show):
        """
        Get any block from the week specified applying to this Track in the
        specified show.
        """

        # XXX

    @property
    def title(self):
        return self.split_id3_title()[0]

    @property
    def role(self):
        return self.split_id3_title()[1]

    @property
    def artist(self):
        return self.id3_artist

    @memoize
    def split_id3_title(self):
        return split_id3_title(self.id3_title)

    def artist_has_page(self):
        """
        Return True if this artist has an artist page worth showing.
        """

        return Track.objects.filter(
            id3_artist=self.id3_artist, hidden=False, inudesu=False).exists()

    def eligible(self):
        """
        Returns True if this track can be requested.
        """

        return not self.ineligible()

    @memoize
    def ineligible(self):
        """
        Return a string describing why a track is ineligible, or False if it
        is not
        """

        # XXX gonna break, but shouldn't be difficult to fix

        show = Show.current()
        block_qs = show.block_set.filter(track=self)

        if self.inudesu:
            reason = 'inu desu'

        elif self.hidden:
            reason = 'hidden'

        elif self.play_set.filter(**show._date_kwargs()).exists():
            reason = 'played this week'

        elif self.play_set.filter(**show.prev()._date_kwargs()).exists():
            reason = 'played last week'

        elif block_qs.exists():
            reason = block_qs.get().reason

        else:
            reason = False

        return reason

    @memoize
    def votes_for(self, show):
        """
        Return votes for this track for a given show.
        """

        return self.vote_set.filter(**show._date_kwargs())

    def shortlist(self):
        """
        Shortlist this track for this week.
        """

        # XXX

    def discard(self):
        """
        Discard this track for this week.
        """

        # XXX

    def slug(self):
        return slugify(self.title)

    def get_absolute_url(self):
        return reverse('vote:track', kwargs={'slug': self.slug(),
                                             'pk': self.pk})

    def get_public_url(self):
        return 'http://nkd.su' + self.get_absolute_url()

    def get_report_url(self):
        return reverse('vote:report', kwargs={'pk': self.pk})

    def get_vote_url(self):
        """
        Return the Twitter intent url for voting for this track alone.
        """

        return vote_tweet_intent_url([self])

    def api_dict(self, verbose=False):
        the_track = {
            'id': self.id,
            'title': self.derived_title(),
            'role': self.derived_role(),
            'artist': self.id3_artist,
            'length': self.msec,
            'inu desu': self.inudesu,
            'url': self.url(),
        }

        if verbose:
            the_track.update({
                'plays': [p.datetime for p in Play.objects.filter(track=self)]
            })

        return the_track


MANUAL_VOTE_KINDS = (
    ('email', 'email'),
    ('text', 'text'),
    ('tweet', 'tweet'),
)


class Vote(models.Model):
    # universal
    tracks = models.ManyToManyField(Track)
    date = models.DateTimeField()
    text = models.TextField(blank=True)

    # twitter only
    twitter_user = models.ForeignKey(TwitterUser, blank=True)
    tweet_id = models.BigIntegerField()

    # manual only
    name = models.CharField(max_length=40)
    kind = models.CharField(max_length=10, choices=MANUAL_VOTE_KINDS)

    @property
    def is_manaul(self):
        return not self.kind

    def __unicode__(self):
        tracks = u', '.join([t.title for t in self.tracks.all()])

        if self.twitter_user:
            return u'{user} at {date} for {tracks}'.format(
                user=self.twitter_user,
                date=self.date,
                tracks=tracks,
            )
        else:
            raise NotImplementedError  # XXX

    def derive_tracks_from_url_list(self, url_list):
        """
        Take a list of URLs and return a list of Tracks that should be
        considered voted for based on that list.
        """

        # XXX should work fine, but needs to be updated to use reverse() or
        # self.get_absolute_url

        tracks = []
        for url in url_list:
            chunks = url.strip('/').split('/')
            track_id = chunks[-1]
            slug = chunks[-2]
            try:
                track = Track.objects.get(id=track_id)
            except Track.DoesNotExist:
                pass
            else:
                if track.slug() == slug:
                    tracks.append(track)

        return tracks

    @memoize
    def content(self):
        """
        Return the non-mention, non-url content of the text.
        """

        content = self.text

        if content.startswith('@'):
            content = content.split(' ', 1)[1]

        content = content.strip('- ')

        for word in content.split():
            if re.match(r'https?://[^\s]+', word):
                content = content.replace(word, '').strip()
            elif len(word) == 16 and re.match('[0-9A-F]{16}', word):
                # for the sake of old pre-url votes
                content = content.replace(word, '').strip()

        return content

    def relevant_prior_voted_tracks(self):
        """
        Return the tracks that this vote's issuer has already voted for this
        show.
        """

        # XXX

    def clean(self):
        # XXX require that manual votes have a type and twitter votes have
        # a user

        # XXX Be xor-y (that is, don't allow twitter votes to have manual vote
        # properties and vice-versa)

        if not self.tracks:
            raise ValidationError('no tracks in vote')

    def save(self):
        # XXX remove any tracks this person has already voted for this week
        return super(Vote, self).save()

    @memoize
    def success(self):
        """
        Return how successful this vote is, as a float between 0 and 1, or None
        if we don't know yet.
        """

        if not self.show().has_ended():
            return None

        successes = 0
        for track in self.tracks.all():
            if track in self.show().playlist():
                successes += 1

        return successes / self.weight()

    @memoize
    def weight(self):
        """
        Return how much we should take this vote into account when calculating
        a user's batting average.
        """

        return float(self.tracks.all().count())

    @memoize
    def show(self):
        return Show.at(self.date)

    def api_dict(self):
        the_vote = {
            'user_name': self.name,
            'user_screen_name': self.screen_name,
            'user_image': self.user_image,
            'user_id': self.user_id,
            'tweet_id': self.tweet_id,
            'comment': self.content() if self.content() != '' else None,
            'time': self.date,
            'track_ids': [t.id for t in self.get_tracks()],
            'tracks': [t.api_dict() for t in self.get_tracks()]
        }

        return the_vote

    def twitter_url(self):
        return 'http://twitter.com/%s/status/%s/' % (
            self.twitter_user.screen_name,
            self.tweet_id,
        )


class Play(models.Model):
    date = models.DateTimeField()
    track = models.ForeignKey(Track)
    tweet_id = models.IntegerField(blank=True, null=True)

    def __unicode__(self):
        return u'%s at %s' % (self.track, self.date)

    def clean(self):
        if (not Show.was_broadcasting(self.date)):
            raise ValidationError('It is not currently showtime.')

        # XXX raise ValidationError('This has been played today already.')

        self.track.hidden = False  # If something's been played, it's public.
        self.track.save()

    @memoize
    def show(self):
        return Show.at(self.date)


class Block(models.Model):
    """
    A particular track that we are not going to allow to be voted for on
    particular show.
    """

    track = models.ForeignKey(Track)
    reason = models.CharField(max_length=256)
    show = models.ForeignKey(Show)

    # XXX unique_together show and track

    def clean(self):
        if self.track.ineligible():
            raise ValidationError('track is already blocked')


class Shortlist(models.Model):
    show = models.ForeignKey(Show)
    track = models.ForeignKey(Track)
    index = models.IntegerField(default=0)

    # XXX unique_together show and track
    # XXX unique_together show and index

    def save(self):
        pass  # XXX set our index appropriately
        super(Shortlist, self).save()


class Discard(models.Model):
    """
    A track that we're not going to play, but that we don't want to make public
    that we're not going to play.
    """

    show = models.ForeignKey(Show)
    track = models.ForeignKey(Track)
    # XXX unique_together show and track


class Request(models.Model):
    """
    A request for a database addition. Stored for the benefit of enjoying
    hilarious spam.
    """

    created = models.DateTimeField(auto_now_add=True)
    successful = models.BooleanField()
    blob = models.TextField()

    def serialise(self, struct):
        self.blob = json.dumps(struct)

    def struct(self):
        return json.loads(self.blob)
