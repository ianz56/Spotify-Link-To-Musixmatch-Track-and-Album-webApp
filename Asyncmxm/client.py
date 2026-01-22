""" A simple Async Python library for the Musixmatch Web API """


import asyncio
import json

import aiohttp

from Asyncmxm.exceptions import MXMException


class Musixmatch:
    """"""

    max_retries = 3
    default_retry_codes = (429, 500, 502, 503, 504)

    def __init__(
        self,
        API_key,
        limit=4,
        requests_session=None,
        retries=max_retries,
        requests_timeout=5,
        backoff_factor=0.3,
    ):
        """
        Initialize the Musixmatch client.
        
        Parameters:
            API_key (str): Musixmatch API key obtained from https://developer.musixmatch.com/signup.
            limit (int): Maximum concurrent TCP connections for the underlying HTTP session.
            requests_session (aiohttp.ClientSession | None): Existing aiohttp ClientSession to use; if None, a new session is created.
            retries (int): Maximum number of retry attempts for API requests.
            requests_timeout (float | int): Timeout in seconds for individual HTTP requests.
            backoff_factor (float): Multiplier used to compute sleep time between retry attempts.
        """

        self._url = "https://apic-desktop.musixmatch.com/ws/1.1/"
        self._key = API_key
        self.requests_timeout = requests_timeout
        self.backoff_factor = backoff_factor
        self.retries = retries
        self.limit = limit

        if isinstance(requests_session, aiohttp.ClientSession):
            self._session = requests_session
        else:
            self._build_session()

    def _build_session(self):
        """
        Create and attach an aiohttp ClientSession configured with a TCPConnector using the client's concurrency limits.
        
        The created session is stored on self._session and uses the current event loop.
        """
        connector = aiohttp.TCPConnector(limit=self.limit, limit_per_host=self.limit)
        self._session = aiohttp.ClientSession(
            connector=connector, loop=asyncio.get_event_loop()
        )

    '''
    async def __aexit__(self, exc_type, exc_value, exc_tb):
        """Make sure the connection gets closed"""
        await self._session.close()
    '''

    async def _api_call(self, method, api_method, params=None):
        """
        Send an HTTP request to the Musixmatch API endpoint and return the parsed JSON response.
        
        Parameters:
            method (str): HTTP method to use (e.g., "GET", "POST").
            api_method (str): API method path appended to the client's base URL.
            params (dict, optional): Query or body parameters to include; the client will add authentication and app identification.
        
        Returns:
            dict: Parsed JSON response payload from the API.
        
        Raises:
            MXMException: If the API responds with a non-200 status code; includes the API status and any hint.
            Exception: If the request fails after the configured number of retries.
        
        Behavior:
            Retries on network errors and timeouts up to self.max_retries, applying an incremental backoff between attempts.
        """
        url = self._url + api_method
        if params:
            params["usertoken"] = self._key
        else:
            params = {"usertoken": self._key}

        params["app_id"] = "web-desktop-app-v1.0"

        headers = {
            "Authority": "apic-desktop.musixmatch.com",
            "Cookie": "x-mxm-token-guid=",
        }

        retries = 0

        while retries < self.max_retries:
            try:
                # print(params)
                async with self._session.request(
                    method=method, url=str(url), params=params, headers=headers
                ) as response:
                    response.raise_for_status()
                    res = await response.text()
                    print(res)
                    res = json.loads(res)
                    status_code = res["message"]["header"]["status_code"]
                    if status_code == 200:
                        return res
                    else:
                        retries = self.max_retries
                        hint = res["message"]["header"].get("hint") or None
                        raise MXMException(status_code, hint)
            except (aiohttp.ClientError, asyncio.TimeoutError):
                retries += 1
                await asyncio.sleep(self.backoff_factor * retries)
                continue
        raise Exception("API request failed after retries")

    async def track_get(
        self,
        commontrack_id=None,
        track_id=None,
        track_isrc=None,
        commontrack_vanity_id=None,
        track_spotify_id=None,
        track_itunes_id=None,
    ):
        """
        Retrieve track information from Musixmatch using one of several track identifiers.
        
        Parameters:
            commontrack_id: Musixmatch commontrack identifier.
            track_id: Musixmatch track identifier.
            track_isrc: ISRC (International Standard Recording Code) for the track.
            commontrack_vanity_id: Musixmatch vanity id (e.g., "Imagine-Dragons/Demons").
            track_spotify_id: Spotify track identifier.
            track_itunes_id: Apple Music / iTunes track identifier.
        
        Returns:
            dict: Parsed Musixmatch API response payload for the requested track.
        """

        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "track.get", params)

    async def matcher_track_get(
        self,
        q_track=None,
        q_artist=None,
        q_album=None,
        commontrack_id=None,
        track_id=None,
        track_isrc=None,
        commontrack_vanity_id=None,
        track_spotify_id=None,
        track_itunes_id=None,
        **filters,
    ):
        """
        Match a song against the Musixmatch database.
        
        At least one of the query or identifier parameters must be provided (e.g., q_track, q_artist, q_album, commontrack_id, track_id, track_isrc, commontrack_vanity_id, track_spotify_id, or track_itunes_id).
        
        Parameters:
            q_track (str, optional): Text to match against song titles.
            q_artist (str, optional): Text to match against artist names.
            q_album (str, optional): Text to match against album titles.
            commontrack_id (int or str, optional): Musixmatch commontrack identifier.
            track_id (int or str, optional): Musixmatch track identifier.
            track_isrc (str, optional): ISRC code for the track.
            commontrack_vanity_id (str, optional): Musixmatch vanity identifier (e.g., "Imagine-Dragons/Demons").
            track_spotify_id (str, optional): Spotify track identifier.
            track_itunes_id (str, optional): Apple (iTunes) track identifier.
            **filters: Additional optional filtering parameters supported by the API (for example: f_has_lyrics, f_is_instrumental, f_has_subtitle, f_music_genre_id, f_subtitle_length, f_subtitle_length_max_deviation, f_lyrics_language, f_artist_id, f_artist_mbid).
        
        Returns:
            dict: Parsed API response payload from the matcher.track.get endpoint.
        """

        params = {
            k: v
            for k, v in locals().items()
            if v is not None and k != "self" and k != "filters"
        }
        params = {**params, **filters}
        return await self._api_call("get", "matcher.track.get", params)

    async def chart_artists_get(self, page, page_size, country="US"):
        """
        Retrieve the top artists chart for a specified country.
        
        Parameters:
            page (int): Page number for paginated results.
            page_size (int): Number of items per page (1 to 100).
            country (str): Two-letter country code (default "US").
        
        Returns:
            dict: Parsed API response payload containing the chart artists.
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "chart.artists.get", params)

    async def chart_tracks_get(
        self, chart_name, page=1, page_size=100, f_has_lyrics=1, country="US"
    ):
        """
        Retrieve top tracks for a specified chart and country.
        
        Parameters:
            chart_name (str): Chart identifier. Valid values include:
                - "top": editorial chart
                - "hot": most viewed lyrics in the last 2 hours
                - "mxmweekly": most viewed lyrics in the last 7 days
                - "mxmweekly_new": most viewed lyrics in the last 7 days limited to new releases only
            page (int): Page number for paginated results.
            page_size (int): Number of items per page (1 to 100).
            f_has_lyrics (int): Filter by presence of lyrics: 1 to return only tracks with lyrics, 0 to include all.
            country (str): ISO country code used to scope the chart (default "US").
        
        Returns:
            dict: Parsed API response payload containing the requested chart tracks data.
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "chart.tracks.get", params)

    async def track_search(self, page=1, page_size=100, **params):
        """
        Search for tracks in the Musixmatch database using query parameters and filters.
        
        Parameters:
            page (int): Page number for paginated results.
            page_size (int): Number of results per page (1–100).
            **params: Additional query parameters and filters supported by the track.search endpoint. Common keys include:
                q_track: Song title.
                q_artist: Song artist.
                q_lyrics: A word or phrase from the lyrics.
                q_track_artist: Any word in the song title or artist name.
                q_writer: Match by writer name.
                q: Any word in title, artist, or lyrics.
                f_artist_id: Filter results to the given artist id.
                f_music_genre_id: Filter by music genre id.
                f_lyrics_language: Filter by lyrics language code (e.g., "en", "it").
                f_has_lyrics: Set to 1 to return only tracks with lyrics.
                f_track_release_group_first_release_date_min: Minimum release date (YYYYMMDD).
                f_track_release_group_first_release_date_max: Maximum release date (YYYYMMDD).
                s_artist_rating: Sort by artist popularity ("asc" or "desc").
                s_track_rating: Sort by track popularity ("asc" or "desc").
                quorum_factor: Query matching threshold (0.1–0.9).
        
        Returns:
            dict: Parsed JSON response payload from the Musixmatch track.search endpoint.
        """
        locs = locals().copy()
        locs.pop("params")
        params = {**params, **locs}
        return await self._api_call("get", "track.search", params)

    async def track_lyrics_get(
        self, commontrack_id=None, track_id=None, track_spotify_id=None
    ):
        """
        Retrieve lyrics for a track from Musixmatch.
        
        Parameters:
            commontrack_id (int, optional): Musixmatch commontrack identifier.
            track_id (int, optional): Musixmatch track identifier.
            track_spotify_id (str, optional): Spotify track identifier.
        
        Returns:
            dict: Parsed Musixmatch API response containing the lyrics payload.
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "track.lyrics.get", params)

    async def track_lyrics_post(
        self, lyrics: str, commontrack_id=None, track_isrc=None
    ):
        """
        Submit lyrics for a track to the Musixmatch catalog.
        
        Parameters:
            lyrics (str): Lyrics text to submit.
            commontrack_id (int | str, optional): Musixmatch commontrack identifier for the track.
            track_isrc (str, optional): ISRC code identifying the track.
        
        Returns:
            dict: Parsed Musixmatch API response payload.
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("post", "track.lyrics.post", params)

    async def track_lyrics_mood_get(self, commontrack_id=None, track_isrc=None):
        """
        Retrieve mood metadata for a track's lyrics.
        
        Not available for the free plan.
        
        Parameters:
            commontrack_id (int | str): Musixmatch commontrack identifier for the track. At least one of `commontrack_id` or `track_isrc` must be provided.
            track_isrc (str): Track ISRC code. At least one of `commontrack_id` or `track_isrc` must be provided.
        
        Returns:
            dict: Parsed API response containing mood information for the lyrics (including mood tags and the underlying raw mood value).
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "track.lyrics.mood.get", params)

    async def track_snippet_get(
        self, commontrack_id=None, track_id=None, track_isrc=None, track_spotify_id=None
    ):
        """
        Retrieve a short lyrics snippet for a track.
        
        Parameters:
            commontrack_id (int | str, optional): Musixmatch common track identifier.
            track_id (int | str, optional): Musixmatch track identifier.
            track_isrc (str, optional): ISRC (International Standard Recording Code) for the track.
            track_spotify_id (str, optional): Spotify track identifier.
        
        Returns:
            dict: Parsed Musixmatch API response containing the snippet and related metadata.
        """

        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "track.snippet.get", params)

    async def track_subtitle_get(
        self,
        commontrack_id=None,
        track_id=None,
        subtitle_format=None,
        track_isrc=None,
        f_subtitle_length=None,
        f_subtitle_length_max_deviation=None,
    ):
        """
        Retrieve a track's subtitle in the requested format.
        
        Parameters:
            commontrack_id (int, optional): Musixmatch common track identifier.
            track_id (int, optional): Musixmatch track identifier.
            track_isrc (str, optional): ISRC identifier for the track.
            subtitle_format (str, optional): Subtitle format to request (e.g., "lrc", "dfxp", "stledu"). Defaults to "lrc" when omitted.
            f_subtitle_length (int|float, optional): Desired subtitle length in seconds.
            f_subtitle_length_max_deviation (int|float, optional): Maximum allowed deviation from `f_subtitle_length` in seconds.
        
        Returns:
            dict: Parsed API response containing subtitle content and associated metadata.
        """

        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "track.subtitle.get", params)

    async def track_richsync_get(
        self,
        commontrack_id=None,
        track_id=None,
        track_isrc=None,
        track_spotify_id=None,
        f_richsync_length=None,
        f_richsync_length_max_deviation=None,
    ):
        """
        Retrieve the rich sync (enhanced timing/metadata) for a track from Musixmatch.
        
        Parameters:
            commontrack_id (int | str, optional): Musixmatch commontrack identifier.
            track_id (int | str, optional): Musixmatch track identifier.
            track_isrc (str, optional): ISRC identifier for the track.
            track_spotify_id (str, optional): Spotify track identifier.
            f_richsync_length (int | float, optional): Desired rich sync length in seconds.
            f_richsync_length_max_deviation (int | float, optional): Maximum allowed deviation from `f_richsync_length` in seconds.
        
        Returns:
            dict: Parsed Musixmatch API response payload containing the rich sync data.
        """

        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "track.richsync.get", params)

    async def track_lyrics_translation_get(
        self,
        commontrack_id=None,
        track_id=None,
        track_isrc=None,
        track_spotify_id=None,
        selected_language=None,
        min_completed=None,
    ):
        """
        Retrieve translated lyrics for a track in a specified language.
        
        Parameters:
            commontrack_id (int | str, optional): Musixmatch common track identifier.
            track_id (int | str, optional): Musixmatch track identifier.
            track_isrc (str, optional): ISRC code for the track.
            track_spotify_id (str, optional): Spotify track identifier.
            selected_language (str, optional): Target translation language as an ISO 639-1 code (e.g., "en", "es").
            min_completed (float, optional): Minimum translation completion ratio between 0 and 1. Only translations with a completion ratio greater than or equal to this value are returned.
        
        Returns:
            dict: Parsed API response payload containing the translated lyrics and associated metadata.
        """

        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "track.lyrics.translation.get", params)

    async def track_subtitle_translation_get(
        self,
        commontrack_id=None,
        track_id=None,
        track_isrc=None,
        track_spotify_id=None,
        selected_language=None,
        min_completed=None,
        f_subtitle_length=None,
        f_subtitle_length_max_deviation=None,
    ):
        """
        Retrieve a translated subtitle for a track in a specified language.
        
        Parameters:
            commontrack_id (int, optional): Musixmatch commontrack identifier.
            track_id (int, optional): Musixmatch track identifier.
            track_isrc (str, optional): ISRC code for the track.
            track_spotify_id (str, optional): Spotify track identifier.
            selected_language (str, optional): Target language for the translation (ISO 639-1 code).
            min_completed (float, optional): Minimum translation completion ratio between 0 and 1; set to 1.0 to require fully translated subtitles.
            f_subtitle_length (int, optional): Filter for subtitle length (in units used by the API).
            f_subtitle_length_max_deviation (int, optional): Allowed deviation for subtitle length when filtering.
        
        Returns:
            dict: Parsed Musixmatch API response containing the translated subtitle data.
        """

        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "track.subtitle.translation.get", params)

    async def music_genres_get(self):
        """
        Retrieve the list of music genres available in the catalog.
        
        Returns:
            dict: Parsed Musixmatch API response containing the catalog's music genres.
        """
        return await self._api_call("get", "music.genres.get")

    async def matcher_lyrics_get(
        self,
        q_track=None,
        q_artist=None,
        q_album=None,
        commontrack_id=None,
        track_id=None,
        track_isrc=None,
        commontrack_vanity_id=None,
        track_spotify_id=None,
        track_itunes_id=None,
        **filters,
    ):
        """
        Retrieve lyrics for a track by title/artist or by identifiers.
        
        At least one of `q_track`, `q_artist`, or a track identifier (e.g., `commontrack_id`, `track_id`, `track_isrc`, `commontrack_vanity_id`, `track_spotify_id`, `track_itunes_id`) must be provided.
        
        Parameters:
            q_track (str, optional): Track title to match.
            q_artist (str, optional): Artist name to match.
            **filters: Additional Musixmatch filter parameters (for example `f_has_lyrics`, `f_subtitle_length`, `f_lyrics_language`, `f_artist_id`, etc.).
        
        Returns:
            dict: Parsed Musixmatch API response containing the matched lyrics payload.
        """

        params = {
            k: v
            for k, v in locals().items()
            if v is not None and k != "self" and k != "filters"
        }
        params = {**params, **filters}
        return await self._api_call("get", "matcher.lyrics.get", params)

    async def matcher_subtitle_get(
        self,
        q_track=None,
        q_artist=None,
        q_album=None,
        commontrack_id=None,
        track_id=None,
        track_isrc=None,
        commontrack_vanity_id=None,
        track_spotify_id=None,
        track_itunes_id=None,
        **filters,
    ):
        """
        Retrieve subtitles for a song matching title, artist, album, or specific track identifiers, with optional filtering by subtitle length, language, genre, and other attributes.
        
        At least one of q_track, q_artist, q_album, commontrack_id, track_id, track_isrc, commontrack_vanity_id, track_spotify_id, or track_itunes_id must be provided.
        
        Parameters:
            q_track (str): Track title to search for.
            q_artist (str): Artist name to search for.
            q_album (str): Album name to search for.
            commontrack_id (int): Musixmatch commontrack identifier.
            track_id (int): Musixmatch track identifier.
            track_isrc (str): ISRC identifier for the track.
            commontrack_vanity_id (str): Musixmatch vanity id (e.g., "Imagine-Dragons/Demons").
            track_spotify_id (str): Spotify track identifier.
            track_itunes_id (str): Apple/iTunes track identifier.
            f_subtitle_length (int): Desired subtitle length in seconds.
            f_subtitle_length_max_deviation (int): Maximum allowed deviation (seconds) from f_subtitle_length.
            f_has_lyrics (int): Filter by presence of lyrics (1 or 0).
            f_is_instrumental (int): Filter instrumental tracks (1 or 0).
            f_has_subtitle (int): Filter by presence of subtitles (1 or 0).
            f_music_genre_id (int): Filter by music genre identifier.
            f_lyrics_language (str): Filter tracks by lyrics language code (e.g., "en").
            f_artist_id (int): Filter by Musixmatch artist identifier.
            f_artist_mbid (str): Filter by MusicBrainz artist MBID.
            **filters: Additional Musixmatch API filter parameters.
        
        Returns:
            dict: Parsed Musixmatch API response payload.
        """

        params = {
            k: v
            for k, v in locals().items()
            if v is not None and k != "self" and k != "filters"
        }
        params = {**params, **filters}
        return await self._api_call("get", "matcher.subtitle.get", params)

    async def artist_get(self, artist_id):
        """
        Retrieve artist data from Musixmatch.
        
        Parameters:
            artist_id (int | str): Musixmatch artist identifier.
        
        Returns:
            response (dict): Parsed Musixmatch API response containing artist data.
        """
        return await self._api_call("get", "artist.get", locals())

    async def artist_search(self, q_artist, page=1, page_size=100, f_artist_id=None):
        """
        Search for artists matching the given query.
        
        Parameters:
            q_artist (str): Artist name or query to search for.
            page (int): Page number of results.
            page_size (int): Number of results per page; valid range is 1 to 100.
            f_artist_id (int | None): If provided, restrict results to this artist ID.
        
        Returns:
            dict: Parsed JSON response from the Musixmatch API containing the search results.
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "artist.search", params)

    async def artist_albums_get(
        self, artist_id, page=1, page_size=100, g_album_name=1, s_release_date="desc"
    ):
        """
        Retrieve an artist's album discography from Musixmatch.
        
        Parameters:
            artist_id (int | str): Musixmatch artist identifier.
            page (int): Page number for paginated results.
            page_size (int): Number of items per page (1 to 100).
            g_album_name (int): Whether to group results by album name (1 to enable, 0 to disable).
            s_release_date (str): Sort order for release date, either "asc" or "desc".
        
        Returns:
            dict: Parsed Musixmatch API response containing the artist's album data.
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "artist.albums.get", params)

    async def artist_related_get(
        self,
        artist_id,
        page=1,
        page_size=100,
    ):
        """
        Return related artists for a given artist.
        
        Parameters:
            artist_id (int | str): Musixmatch artist identifier.
            page (int): Page number for paginated results.
            page_size (int): Number of results per page; valid range is 1 to 100.
        
        Returns:
            response (dict): Parsed Musixmatch API response containing related artists data.
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "artist.related.get", params)

    async def album_get(self, album_id=None, album_vanity_id=None):
        """
        Retrieve an album by Musixmatch album ID or by its vanity ID.
        
        Parameters:
            album_id (int | str, optional): Musixmatch numeric album identifier.
            album_vanity_id (str, optional): Musixmatch vanity (public-facing) album identifier.
        
        Returns:
            dict: Parsed Musixmatch API response payload for the requested album.
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}
        return await self._api_call("get", "album.get", params)

    async def album_tracks_get(self, album_id, f_has_lyrics=0, page=1, page_size=100):
        """
        Retrieve the list of tracks for a Musixmatch album.
        
        Parameters:
            album_id (int): Musixmatch album identifier.
            f_has_lyrics (int): Set to 1 to return only tracks that have lyrics, 0 to include all (default 0).
            page (int): Page number for paginated results (default 1).
            page_size (int): Number of items per page; valid range is 1 to 100 (default 100).
        
        Returns:
            dict: Parsed Musixmatch API response containing the album tracks payload.
        """
        return await self._api_call("get", "album.tracks.get", locals())