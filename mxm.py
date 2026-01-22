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
        self.key = key or self.DEFAULT_KEY
        self.key2 = key2 or self.DEFAULT_KEY2
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
            # print(self.key, " ", self.key2)
            r.close()

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
            )
            return response
        except Asyncmxm.exceptions.MXMException as e:
            return str(e)

    async def matcher_track_text(self, title, artist, album=None):
        try:
            response = await self.musixmatch2.matcher_track_get(
                q_track=title, q_artist=artist, q_album=album
            )
            return response
        except Asyncmxm.exceptions.MXMException as e:
            return str(e)

    async def matcher_track(self, sp_id):
        try:
            response = await self.musixmatch2.matcher_track_get(
                q_track="null", track_spotify_id=sp_id
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

    async def Tracks_Data(self, sp_data, split_check=False):
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
        """Get the track and the album data from the abstrack."""
        try:
            track = await self.musixmatch.track_get(commontrack_id=id)
            track = track["message"]["body"]["track"]
            album = await self.musixmatch.album_get(track["album_id"])
            album = album["message"]["body"]["album"]
            return track, album
        except Asyncmxm.exceptions.MXMException as e:
            return {"error": str(e)}, {"error": str(e)}
