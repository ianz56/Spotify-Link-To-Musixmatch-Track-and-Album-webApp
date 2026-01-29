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

    def __init__(self, key=None, session=None, key2=None):
        try:
            r = redis.from_url(os.environ.get("REDIS_URL"))
            key1 = r.get("live:1")
            key2_redis = r.get("live:2")

            if key1:
                self.key = key1.decode()
            else:
                self.key = key or self.DEFAULT_KEY

            if key2_redis:
                self.key2 = key2_redis.decode()
            else:
                self.key2 = key2 or self.DEFAULT_KEY2

            r.close()
        except Exception:
            # Fallback if Redis fails or keys are missing
            self.key = key or self.DEFAULT_KEY
            self.key2 = key2 or self.DEFAULT_KEY2

        self.session = session
        self.musixmatch = Asyncmxm.Musixmatch(self.key, requests_session=session)
        self.musixmatch2 = Asyncmxm.Musixmatch(self.key2, requests_session=session)

    def change_key(self, key):
        self.key = key

    async def track_get(self, isrc=None, commontrack_id=None, vanity_id=None) -> dict:
        try:
            response = await self.musixmatch.track_get(
                track_isrc=isrc,
                commontrack_id=commontrack_id,
                commontrack_vanity_id=vanity_id,
                part="track_lyrics_translation_status,publishing_info",
            )
            return response
        except Asyncmxm.exceptions.MXMException as e:
            return str(e)

    async def matcher_track_text(self, title, artist, album=None):
        try:
            response = await self.musixmatch2.matcher_track_get(
                q_track=title,
                q_artist=artist,
                q_album=album,
                part="track_lyrics_translation_status,publishing_info",
            )
            return response
        except Asyncmxm.exceptions.MXMException as e:
            return str(e)

    async def matcher_track(self, sp_id):
        try:
            response = await self.musixmatch2.matcher_track_get(
                q_track="null",
                track_spotify_id=sp_id,
                part="track_lyrics_translation_status,publishing_info",
            )
            return dict(response)
        except Asyncmxm.exceptions.MXMException as e:
            return str(e)

    async def Track_links(self, sp_data):
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
            if not isinstance(sp_data, dict):
                return sp_data

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

    async def get_album_tracks_by_first_track(self, sp_data):
        if not sp_data or not sp_data[0].get("track"):
            return None

        # Use the first track to find the album
        first_track = sp_data[0]
        mxm_track = await self.matcher_links(first_track)

        if isinstance(mxm_track, dict) and "album_id" in mxm_track:
            album_id = mxm_track["album_id"]
            # Fetch all tracks for this album
            try:
                album_tracks_response = await self.musixmatch.album_tracks_get(
                    album_id,
                    page_size=100,
                    part="track_lyrics_translation_status,publishing_info",
                )
                if (
                    album_tracks_response["message"]["header"]["status_code"] == 200
                    and "track_list" in album_tracks_response["message"]["body"]
                ):
                    return album_tracks_response["message"]["body"]["track_list"]
            except Exception as e:
                print(f"Error fetching album tracks: {e}")
                return None
        return None

    async def Tracks_Data(self, sp_data, split_check=False):
        links = []

        # Check if it looks like an album (more than 1 track)
        album_tracks_mxm = None
        if (
            len(sp_data) > 1
            and isinstance(sp_data[0], dict)
            and sp_data[0].get("track")
        ):
            # Heuristic: check if first and second track have same album name (if available)
            # Or just try to fetch album tracks and see if we can match them
            album_tracks_mxm = await self.get_album_tracks_by_first_track(sp_data)

        if album_tracks_mxm:
            # We have the album tracks from MXM. Now we need to match them to sp_data
            # sp_data is ordered. album_tracks_mxm might be ordered by track_index.
            # Let's try to match by ISRC first, then by title/fuzzy.

            # Create a map of MXM tracks for easier lookup
            mxm_map_by_isrc = {}
            mxm_map_by_title = {}  # (title_normalized, artist_normalized) -> track

            for item in album_tracks_mxm:
                t = item["track"]
                if t.get("track_isrc"):
                    mxm_map_by_isrc[t["track_isrc"]] = t

                # Normalize for fuzzy matching prep
                t_title = re.sub(r"[()-.]", "", t.get("track_name", "")).lower()
                # artist might be in t['artist_name']
                # But for now let's just use title if artist matches album artist roughly
                mxm_map_by_title[t_title] = t

            tracks = []

            # Since we are confident these tracks belong to the album, we can use them as matchers too.
            # We'll build the matchers list in parallel to avoid the second API loop.
            matchers = []

            for sp_track in sp_data:
                found_mxm = None
                sp_isrc = sp_track.get("isrc")

                # Try ISRC
                if sp_isrc in mxm_map_by_isrc:
                    found_mxm = mxm_map_by_isrc[sp_isrc]

                if not found_mxm:
                    # Try Title
                    sp_title = sp_track["track"]["name"]
                    sp_title_norm = re.sub(r"[()-.]", "", sp_title).lower()

                    # Direct match
                    if sp_title_norm in mxm_map_by_title:
                        found_mxm = mxm_map_by_title[sp_title_norm]
                    else:
                        # Fuzzy match against all mxm titles
                        best_score = 0
                        best_match = None
                        for mt_title, mt_track in mxm_map_by_title.items():
                            score = jellyfish.jaro_similarity(sp_title_norm, mt_title)
                            if score > 0.85 and score > best_score:
                                best_score = score
                                best_match = mt_track
                        if best_match:
                            found_mxm = best_match

                if found_mxm:
                    # Make a shallow copy to avoid mutating the original in lookup maps
                    new_mxm = dict(found_mxm)
                    new_mxm["isrc"] = sp_isrc or new_mxm.get("track_isrc")
                    new_mxm["image"] = sp_track.get("image")
                    new_mxm["beta"] = str(new_mxm["track_share_url"]).replace(
                        "www.", "com-beta.", 1
                    )
                    tracks.append(new_mxm)
                    matchers.append(dict(new_mxm))  # Use same data for matcher
                else:
                    # Fallback to individual fetch for this specific track
                    individual_res = await self.Track_links(sp_track)
                    if isinstance(individual_res, dict):
                        tracks.append(individual_res)
                    else:
                        tracks.append(individual_res)  # likely error string

                    # For matcher fallback, we need to call matcher logic individually too
                    # Or just use the individual_res if it's good?
                    # Original logic pairs tracks_get() result with tracks_matcher() result to compare.
                    # tracks_matcher() does more loose matching (by text).
                    # But Track_links (which is tracks_get fallback) already does text matching fallback!
                    # So individual_res is likely already the best match.
                    matchers.append(individual_res)

        else:
            # Safety check: ensure sp_data is non-empty before accessing sp_data[0]
            if not sp_data or not isinstance(sp_data, list) or len(sp_data) == 0:
                return []
            tracks = await self.tracks_get(sp_data)
            # Only run matchers loop if we took the old path
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
        coro = [self.Track_links(isrc) for isrc in data]
        tasks = [asyncio.create_task(c) for c in coro]
        tracks = await asyncio.gather(*tasks)
        return tracks

    async def tracks_matcher(self, data):
        coro = [self.matcher_links(isrc) for isrc in data]
        tasks = [asyncio.create_task(c) for c in coro]
        tracks = await asyncio.gather(*tasks)
        return tracks

    async def album_sp_id(self, link):
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
                    return {"album": album["message"]["body"]["album"]}
                elif match.group(2):
                    album = await self.musixmatch.album_get(match.group(2))
                    return {"album": album["message"]["body"]["album"]}
                else:
                    track = await self.musixmatch.track_get(
                        commontrack_vanity_id=match.group(3),
                        part="track_lyrics_translation_status,publishing_info",
                    )
                    track_data = track["message"]["body"]["track"]
                    album_id = track_data["album_id"]
                    album = await self.musixmatch.album_get(album_id)
                    return {
                        "album": album["message"]["body"]["album"],
                        "track": track_data,
                    }
                # print(album)
                # return {"album": album["message"]["body"]["album"]}
            except Asyncmxm.exceptions.MXMException as e:
                return {"error": str(e)}
        else:
            return {"error": "Unsupported link."}

    async def abstrack(self, id: int) -> tuple[dict, dict]:
        """Get the track and the album data from the abstrack."""
        try:
            track = await self.musixmatch.track_get(
                commontrack_id=id,
                part="track_lyrics_translation_status,publishing_info",
            )
            track = track["message"]["body"]["track"]
            album = await self.musixmatch.album_get(track["album_id"])
            album = album["message"]["body"]["album"]
            return track, album
        except Asyncmxm.exceptions.MXMException as e:
            return {"error": str(e)}, {"error": str(e)}
