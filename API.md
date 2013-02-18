## Endpoints

The root of the API is [nkd.su/api/][api_root]. The following endpoints are
available:

### [`/week/<dd>-<mm>-<yyyy>/`][eg_week]

Information from a particular week. The week returned will be the week that was
in progress at midnight on the morning of the day specified.

Includes:

- `votes`: a list of votes placed
- `playlist`: a list of tracks played and the times at which they were played
- `added`: a list of all the tracks added to the library this week
- `start`: the date and time at which this week started
- `finish`: the date and time at which this week ended 
- `showtime`: the date and time at which this week's show began

### [`/week/`][eg_latest_week]

A redirect to the week containing the most recent complete show.

### [`/`][api_root]

Information about the week in progress.

### [`/track/<track_id>/`][eg_track]

Information about a particular track, including metadata and a list of every
play on record.

Note that the `plays` list is only included for tracks in calls to
`/track/<track_id>`; tracks returned as part of other endpojnts will not have
`plays` listed.

### [`/search/?q=query[&page=page]`][eg_search]

Return a list of `track` objects matching `q`, using the same machinery as the
search box on the website. Accepts the optional argument `page`.

Along with `results`, the response also includes `result_count` (the total
number of results), and `page_count` (the total number of available pages for
that query). Results are limited to 100 results per page, and the default page
number is 1. There is no page 0.

Note that, like the website, there is no specific order to the results and the
order is subject to change between queries. If your user is providing broad
enough searches to match more than 100 tracks, you may want to encourage them
to be more specific.

## More things

If you're going to create tweets for voters, make sure that '@nkdsu' appears at
the start of the vote tweet. Right now, URLs are constructed in a particular
way and can fall anywhere within a vote tweet, but this is subject to change.
To be safe, keep the URLs before any text and use the `url` value provided in
track objects.

If there is something else you want added or changed, or if you find something
that's broken, [let me know][new_issue]. If you just have a question,
[tweet][pester] at me.

[new_issue]: https://github.com/colons/nkdsu/issues/new
[api_root]: http://nkd.su/api/
[eg_track]: http://nkd.su/api/track/7C4D7B4B394E0E59/
[eg_latest_week]: http://nkd.su/api/week/
[eg_week]: http://nkd.su/api/week/05-01-2013/
[eg_search]: http://nkd.su/api/search/?q=character%20song&page=2
[pester]: https://twitter.com/intent/tweet?text=%40mftb