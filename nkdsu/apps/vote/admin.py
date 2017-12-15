from ..vote import models
from django.contrib import admin


class ShowAdmin(admin.ModelAdmin):
    list_display = ('showtime', 'end', 'voting_allowed')


class TwitterUserAdmin(admin.ModelAdmin):
    list_display = ('screen_name', 'is_abuser')
    list_filter = ('is_abuser',)


class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge')
    list_filter = ('user', 'badge')


class VoteAdmin(admin.ModelAdmin):
    list_display = ('twitter_user', 'date')
    list_filter = ('kind', 'twitter_user')


class TrackAdmin(admin.ModelAdmin):
    list_display = ('id3_title', 'id3_artist')


class PlayAdmin(admin.ModelAdmin):
    list_display = ('track', 'date')


class BlockAdmin(admin.ModelAdmin):
    list_display = ('track', 'reason', 'show')


class DiscardShortlistAdmin(admin.ModelAdmin):
    list_display = ('track', 'show')


class RequestAdmin(admin.ModelAdmin):
    list_display = ('created', 'successful')
    list_filter = ('successful',)


class NoteAdmin(admin.ModelAdmin):
    list_display = ('track', 'show', 'public', 'content')


for model, modeladmin in [
        (models.Show, ShowAdmin),
        (models.TwitterUser, TwitterUserAdmin),
        (models.UserBadge, UserBadgeAdmin),
        (models.Track, TrackAdmin),
        (models.Vote, VoteAdmin),
        (models.Play, PlayAdmin),
        (models.Block, BlockAdmin),
        (models.Shortlist, DiscardShortlistAdmin),
        (models.Discard, DiscardShortlistAdmin),
        (models.Request, RequestAdmin),
        (models.Note, NoteAdmin),
]:
    admin.site.register(model, modeladmin)
