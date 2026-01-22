import asyncio
import os
import re
from urllib.parse import unquote

import jellyfish
import redis
from flask_babel import _

import Asyncmxm


class MXM:
    DEFAULT_KEY = os.environ.get("MXM_API")
    DEFAULT_KEY2 = os.environ.get("MXM_API2")

    def __init__(self, key=None, session=None):
        """
        Initialize the MXM wrapper with API keys and Musixmatch client sessions.
        
        If `key` is omitted or falsy, the initializer will use configured defaults or attempt to retrieve live keys from Redis. Sets instance attributes `key`, `key2`, and `session`, and constructs two Asyncmxm.Musixmatch clients (one per key) that use the provided HTTP session.
        
        Parameters:
            key (str | None): Primary Musixmatch API key. If None, the class will fall back to environment defaults or Redis-stored keys.
            session: HTTP requests/session object to be passed to the underlying Musixmatch clients.
        """
        self.key = key or self.DEFAULT_KEY
        self.key2 = key or self.DEFAULT_KEY2
        if not self.key:
            r = redis.Redis(
                host=os.environ.get("REDIS_HOST"),
                port=os.environ.get("REDIS_PORT"),
                password=os.environ.get("REDIS_PASSWD"),
            )
            key1 = r.get("live:1")
            key2 = r.get("live:2")
            self.key = key1.decode()
            self.key2 = key2.decode()
            print(self.key, " ", self.key2)
            r.close()

        self.session = session
        self.musixmatch = Asyncmxm.Musixmatch(self.key, requests_session=session)
        self.musixmatch2 = Asyncmxm.Musixmatch(self.key2, requests_session=session)

    def change_key(self, key):
        """
        Set the active Musixmatch API key for this MXM instance.
        
        Parameters:
            key (str): The API key to assign as the instance's primary Musixmatch key.
        """
        self.key = key

    async def track_get(self, isrc=None, commontrack_id=None, vanity_id=None) -> dict:
        """
        Fetch track data from Musixmatch using an identifier.
        
        Parameters:
            isrc (str | None): International Standard Recording Code to look up.
            commontrack_id (int | None): Musixmatch commontrack numeric identifier.
            vanity_id (str | None): Musixmatch vanity/commontrack slug.
        
        Returns:
            dict: The Musixmatch API response as a dictionary, or an error string if the Musixmatch client raised an MXMException.
        """
        try:
            response = await self.musixmatch.track_get(
                track_isrc=isrc,
                commontrack_id=commontrack_id,
                commontrack_vanity_id=vanity_id,
            )
            return response
        except Asyncmxm.exceptions.MXMException as e:
            return str(e)

    async def matcher_track_text(self, title, artist, album=None):
        """
        Search Musixmatch for a track using title and artist, optionally narrowed by album.
        
        Parameters:
            title (str): Track title to search for.
            artist (str): Artist name to search for.
            album (str | None): Optional album name to narrow the search.
        
        Returns:
            dict: Musixmatch response object on success.
            str: Error message when a Musixmatch exception occurs.
        """
        try:
            response = await self.musixmatch2.matcher_track_get(
                q_track=title, q_artist=artist, q_album=album
            )
            return response
        except Asyncmxm.exceptions.MXMException as e:
            return str(e)

    async def matcher_track(self, sp_id):
        """
        Retrieve Musixmatch matcher data for a Spotify track ID.
        
        Parameters:
            sp_id (str): Spotify track identifier to use for the matcher lookup.
        
        Returns:
            dict: The Musixmatch matcher response converted to a dictionary on success; a string containing the exception message if a Musixmatch error occurs.
        """
        try:
            response = await self.musixmatch2.matcher_track_get(
                q_track="null", track_spotify_id=sp_id
            )
            return dict(response)
        except Asyncmxm.exceptions.MXMException as e:
            return str(e)

    async def Track_links(self, sp_data):
        """
        Map Spotify-like track data to a Musixmatch track record, using ISRC lookup with a text-search fallback.
        
        Parameters:
        	sp_data (dict | any): Spotify-style track object (preferred) or other payload; when a dict, it may contain "isrc", "track" (with "name" and "artists"), and "image".
        
        Returns:
        	dict: A Musixmatch-style track dictionary with added keys ("isrc", "image", "beta") when a match is found.
        	str: An error message or raw Musixmatch error string when lookup or text search fails.
        	any: The original sp_data when no search is attempted (fallback path).
        """
        if isinstance(sp_data, dict):
            track = await self.track_get(sp_data.get("isrc"))
            try:
                _id = track["message"]["body"]["track"]["commontrack_id"]
            except TypeError:
                # Fallback to search by title/artist if no ISRC or ISRC lookup failed
                if sp_data.get("track") and sp_data["track"].get("name"):
                    track_name = sp_data["track"]["name"]
                    artist_name = (
                        sp_data["track"]["artists"][0]["name"]
                        if sp_data["track"]["artists"]
                        else ""
                    )

                    found_track = await self.matcher_track_text(track_name, artist_name)

                    # Duck typing: Check if it behaves like a dict (has get method) and looks successful
                    if hasattr(found_track, "get") and found_track.get("message"):
                        try:
                            # Normalize the found track to look like a 'get' response
                            track_body = found_track["message"]["body"]["track"]
                            # We construct a track object similar to what track_get returns but with our data
                            # However, matcher_track_get returns a track object which is good.

                            # We need to maintain the structure expected by the caller or downstream
                            # Downstream expects 'track' to be a dict representing the track with isrc/image/beta keys added.
                            # But wait, Track_links is supposed to return the track dict object directly (not the full response).

                            # Actually, look at the success path:
                            # track = track["message"]["body"]["track"]
                            # track["isrc"] = ...
                            # return track

                            # So here we should prepare 'track' to be the dict from message body
                            track = track_body
                            # Use source ISRC if available, otherwise use the one from the found track
                            track["isrc"] = sp_data.get("isrc") or track.get(
                                "track_isrc"
                            )
                            track["image"] = sp_data.get("image")
                            track["beta"] = str(track["track_share_url"]).replace(
                                "www.", "com-beta.", 1
                            )
                            return dict(track)
                        except (TypeError, KeyError):
                            return "Track not found by text search."
                    else:
                        return str(found_track)
                return track

            track = track["message"]["body"]["track"]
            track["isrc"] = sp_data["isrc"]
            track["image"] = sp_data["image"]
            track["beta"] = str(track["track_share_url"]).replace(
                "www.", "com-beta.", 1
            )

            return dict(track)
        else:
            # Fallback to search by title/artist if no ISRC
            if sp_data.get("track") and sp_data["track"].get("name"):
                track_name = sp_data["track"]["name"]
                artist_name = (
                    sp_data["track"]["artists"][0]["name"]
                    if sp_data["track"]["artists"]
                    else ""
                )

                found_track = await self.matcher_track_text(track_name, artist_name)

                if isinstance(found_track, dict):
                    try:
                        track = found_track["message"]["body"]["track"]
                        track["isrc"] = sp_data.get("isrc")
                        track["image"] = sp_data.get("image")
                        track["beta"] = str(track["track_share_url"]).replace(
                            "www.", "com-beta.", 1
                        )
                        # Mark as found via text match but without ID (for later logic)
                        return dict(track)
                    except (TypeError, KeyError):
                        return "Track not found by text search."
                else:
                    return str(found_track)

            return sp_data

    async def matcher_links(self, sp_data):
        """
        Finds and returns a Musixmatch track matched to the provided Spotify-like data.
        
        Parameters:
            sp_data (dict): Spotify-like payload containing at least a "track" object.
                The "track" object may include "id" (Spotify track id), "name", and
                "artists" (list of artist objects with "name"). Top-level fields
                "isrc" and "image" are used to enrich the returned track.
        
        Returns:
            dict: Musixmatch track object enriched with `isrc`, `image`, and `beta` (track share URL rewritten for beta).
            str: An error message ("No matching data found.") or the raw matcher response when matching fails.
        """
        if not sp_data.get("track"):
            return "No matching data found."

        if not sp_data["track"].get("id"):
            # If no Spotify ID (e.g. Apple Music), use text search for matcher as well
            track_name = sp_data["track"]["name"]
            artist_name = (
                sp_data["track"]["artists"][0]["name"]
                if sp_data["track"]["artists"]
                else ""
            )
            track = await self.matcher_track_text(track_name, artist_name)
        else:
            id = sp_data["track"]["id"]
            track = await self.matcher_track(id)
        try:
            id = track["message"]["body"]["track"]["commontrack_id"]
        except TypeError:
            return track

        track = track["message"]["body"]["track"]
        track["isrc"] = sp_data["isrc"]
        track["image"] = sp_data["image"]
        track["beta"] = str(track["track_share_url"]).replace("www.", "beta.", 1)
        return dict(track)

    async def Tracks_Data(self, sp_data, split_check=False):
        """
        Builds a reconciled list of Musixmatch track results aligned to the provided Spotify-style input data.
        
        Processes each input item by fetching Musixmatch track data and matcher results, then applies duck-typed merging and heuristic checks to decide which source to keep, annotate, or mark with a note about possible ISRC/Spotify mismatches. When split_check is true, the function returns the raw fetched track items without attempting to match them to matcher results.
        
        Parameters:
            sp_data (list): List of Spotify-like track entries. Each element is typically a dict containing a "track" key with nested fields like "name", "album" (with "name"), "id", and "isrc". Elements may also be other types (e.g., strings) returned from upstream fetches.
            split_check (bool): If true, skip matcher reconciliation and append fetched tracks directly to the result list.
        
        Returns:
            list: A list where each element is either:
              - a dict: an enriched track or matcher object (contains Musixmatch fields and possible annotations such as "matcher_album" or "note"), or
              - a str: an error or informational message for that item (for example, a not-imported/404 message).
        """
        links = []
        tracks = await self.tracks_get(sp_data)

        if isinstance(sp_data[0], dict) and sp_data[0].get("track"):
            matchers = await self.tracks_matcher(sp_data)
        else:
            return tracks

        for i in range(len(tracks)):
            track = tracks[i]
            matcher = matchers[i]
            if split_check:
                links.append(track)
                continue

            # detecting what issues can facing the track
            # Use duck typing: check if objects have 'get' method (dict-like)
            track_is_dict = hasattr(track, "get")
            matcher_is_dict = hasattr(matcher, "get")
            if track_is_dict and matcher_is_dict:
                # the get call and the matcher call are the same and both have valid response
                if track["commontrack_id"] == matcher["commontrack_id"]:
                    track["matcher_album"] = [
                        matcher["album_id"],
                        matcher["album_name"],
                    ]
                    links.append(dict(track))
                    """ when we get different data, the sp id attached to the matcher so we try to detect if the matcher one is vailid or it just a ISRC error. I used the probability here to choose the most accurate data to the spotify data """
                else:
                    matcher_title = re.sub(r"[()-.]", "", matcher.get("track_name"))
                    matcher_album = re.sub(r"[()-.]", "", matcher.get("album_name"))
                    sp_title = re.sub(r"[()-.]", "", sp_data[i]["track"]["name"])
                    sp_album = re.sub(
                        r"[()-.]", "", sp_data[i]["track"]["album"]["name"]
                    )
                    track_title = re.sub(r"[()-.]", "", track.get("track_name"))
                    track_album = re.sub(r"[()-.]", "", track.get("album_name"))
                    if (
                        matcher.get("album_name")
                        == sp_data[i]["track"]["album"]["name"]
                        and matcher.get("track_name") == sp_data[i]["track"]["name"]
                        or jellyfish.jaro_similarity(
                            matcher_title.lower(), sp_title.lower()
                        )
                        * jellyfish.jaro_similarity(
                            matcher_album.lower(), sp_album.lower()
                        )
                        >= jellyfish.jaro_similarity(
                            track_title.lower(), sp_title.lower()
                        )
                        * jellyfish.jaro_similarity(
                            track_album.lower(), sp_album.lower()
                        )
                    ):
                        matcher["note"] = _(
                            'This track may having two pages with the same ISRC, the other <a class="card-link" href="%(track_url)s" target="_blank">page</a> from <a class="card-link" href="https://www.musixmatch.com/album/%(artist_id)s/%(album_id)s" target="_blank">album</a>.',
                            track_url=track["track_share_url"],
                            artist_id=track["artist_id"],
                            album_id=track["album_id"],
                        )
                        links.append(dict(matcher))
                    else:
                        track["note"] = _(
                            'This track may be facing an ISRC issue as the Spotify ID is connected to another <a class="card-link" href="%(track_url)s" target="_blank">page</a> from <a class="card-link" href="https://www.musixmatch.com/album/%(artist_id)s/%(album_id)s" target="_blank">album</a>.',
                            track_url=matcher["track_share_url"],
                            artist_id=matcher["artist_id"],
                            album_id=matcher["album_id"],
                        )
                        links.append(dict(track))
                continue

            elif isinstance(track, str) and isinstance(matcher, str):
                if re.search("404", track):
                    track = _(
                        "The track hasn't been imported yet. Please try again after 1-5 minutes. Sometimes it may take longer, up to 15 minutes, depending on the MXM API and their servers."
                    )
                    links.append(track)
                    continue
                else:
                    links.append(track)
            elif isinstance(track, str) and matcher_is_dict:
                if matcher.get("album_name") == sp_data[i]["track"]["album"]["name"]:
                    links.append(dict(matcher))
                    continue
                else:
                    links.append(dict(matcher))
            elif track_is_dict and isinstance(matcher, str):
                track["note"] = _("This track may missing its Spotify id")
                links.append(dict(track))
            else:
                # Ensure dict conversion for any fallback case
                if hasattr(track, "get"):
                    links.append(dict(track))
                else:
                    links.append(track)
        return links

    async def tracks_get(self, data):
        """
        Fetches Musixmatch track information for each entry in `data` by resolving them concurrently.
        
        Parameters:
            data (iterable): Iterable of track inputs (e.g., Spotify-like track dicts or identifiers) to be resolved via Track_links.
        
        Returns:
            list: A list of resolved track results; each item is typically a dict with track data or a string describing an error or lookup failure.
        """
        coro = [self.Track_links(isrc) for isrc in data]
        tasks = [asyncio.create_task(c) for c in coro]
        tracks = await asyncio.gather(*tasks)
        return tracks

    async def tracks_matcher(self, data):
        """
        Dispatches matcher_links for each element in `data` and returns the collected results in input order.
        
        Parameters:
            data (Iterable): An iterable of track-like items; each element is passed to `matcher_links` to perform a matching lookup.
        
        Returns:
            list: A list of matcher results corresponding to each input element, in the same order as `data`.
        """
        coro = [self.matcher_links(isrc) for isrc in data]
        tasks = [asyncio.create_task(c) for c in coro]
        tracks = await asyncio.gather(*tasks)
        return tracks

    async def album_sp_id(self, link):
        """
        Extract album information from a Musixmatch URL.
        
        Parses the provided Musixmatch link for a vanity album path, numeric album ID, or lyrics-based album reference and returns the corresponding album data fetched from Musixmatch. If the link is not a Musixmatch album/lyrics URL or if the Musixmatch client raises an MXMException, an error message is returned.
        
        Parameters:
            link (str): URL or path expected to reference a Musixmatch album or lyrics page.
        
        Returns:
            dict: On success, {"album": <album dict>} where <album dict> is the album object from the Musixmatch response.
                  On failure, {"error": "<error message>"} describing either an unsupported link or the underlying MXMException.
        """
        site = re.search(r"musixmatch.com", link)
        match = re.search(
            r"album/([^?]+/[^?]+)|album/(\d+)|lyrics/([^?]+/[^?]+)", unquote(link)
        )
        if match and site:
            try:
                if match.group(1):
                    album = await self.musixmatch.album_get(
                        album_vanity_id=match.group(1)
                    )
                elif match.group(2):
                    album = await self.musixmatch.album_get(match.group(2))
                else:
                    track = await self.musixmatch.track_get(
                        commontrack_vanity_id=match.group(3)
                    )
                    album_id = track["message"]["body"]["track"]["album_id"]
                    album = await self.musixmatch.album_get(album_id)
                print(album)
                return {"album": album["message"]["body"]["album"]}
            except Asyncmxm.exceptions.MXMException as e:
                return {"error": str(e)}
        else:
            return {"error": "Unsupported link."}

    async def abstrack(self, id: int) -> tuple[dict, dict]:
        """
        Retrieve the track and its album data for a Musixmatch commontrack ID.
        
        Parameters:
            id (int): Musixmatch commontrack ID to fetch.
        
        Returns:
            tuple[dict, dict]: A pair (track, album) where `track` is the track object and `album` is the album object extracted from the API response bodies. On Musixmatch errors returns ({"error": "<message>"}, {"error": "<message>"}).
        """
        try:
            track = await self.musixmatch.track_get(commontrack_id=id)
            track = track["message"]["body"]["track"]
            album = await self.musixmatch.album_get(track["album_id"])
            album = album["message"]["body"]["album"]
            return track, album
        except Asyncmxm.exceptions.MXMException as e:
            return {"error": str(e)}, {"error": str(e)}