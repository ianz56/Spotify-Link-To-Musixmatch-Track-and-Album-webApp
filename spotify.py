import logging
import re
from os import environ

import redis
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


class Spotify:
    def __init__(self, client_id=None, client_secret=None) -> None:
        """
        Create and configure a Spotify client instance.
        
        If `client_id` and `client_secret` are provided they are used; otherwise the constructor attempts to read them from the environment and, if still missing, calls `RRAuth()` to obtain credentials. When credentials are available, a Spotipy client is created and an HTTP session is initialized.
        
        Parameters:
            client_id (str, optional): Spotify client ID. If omitted, read from the SPOTIPY_CLIENT_ID environment variable or obtained via `RRAuth()`.
            client_secret (str, optional): Spotify client secret. If omitted, read from the SPOTIPY_CLIENT_SECRET environment variable or obtained via `RRAuth()`.
        """
        self.client_id = client_id if client_id else environ.get("SPOTIPY_CLIENT_ID")
        self.client_secret = (
            client_secret if client_secret else environ.get("SPOTIPY_CLIENT_SECRET")
        )
        if not (self.client_id and self.client_secret):
            self.RRAuth()
        else:
            cred = SpotifyClientCredentials(self.client_id, self.client_secret)
            self.sp = spotipy.Spotify(client_credentials_manager=cred, retries=3)
        self.session = requests.Session()
        # if client_id is not None:

    def RRAuth(self):
        """
        Retrieve the next Spotify client credentials from Redis, rotate the stored index, and initialize the Spotipy client on self.
        
        Connects to the Redis key "spotify", reads the credential list and current index, selects the credential at that index, updates the stored index to the next position (wrapping to the start), closes the Redis connection, and sets self.sp to a Spotipy client using the selected credentials.
        """
        r = redis.Redis(
            host=environ.get("REDIS_HOST"),
            port=environ.get("REDIS_PORT"),
            password=environ.get("REDIS_PASSWD"),
        )

        doc = r.json().get("spotify", "$")
        doc = doc[0]
        cred = doc["cred"][doc["rr"]]
        logging.info(f"Spotify Cred: {cred}")
        r.json().set("spotify", "$.rr", (doc["rr"] + 1) % len(doc["cred"]))
        r.close()
        cred = SpotifyClientCredentials(cred[0], cred[1])
        self.sp = spotipy.Spotify(client_credentials_manager=cred, retries=3)

    def get_track(self, link=None, track=None) -> dict:
        """
        Retrieve a Spotify track using either a Spotify URL/shortlink or a track ID.
        
        Parameters:
            link (str): A Spotify track URL or shortlink; if provided, the track ID will be extracted from it.
            track (str): A Spotify track ID to fetch when `link` is not provided.
        
        Returns:
            dict: The Spotify API track object for the requested track.
        """
        if link is not None:
            track = self.get_spotify_id(link)
        return self.sp.track(track)

    def get_album_tracks(self, id: str) -> dict:
        """
        Fetches the track listing for a Spotify album by its Spotify album ID.
        
        Parameters:
            id (str): Spotify album ID to retrieve tracks for.
        
        Returns:
            album_tracks (dict): The Spotify API response containing the album's tracks and paging metadata.
        """
        return self.sp.album_tracks(id)

    def get_tracks(self, ids) -> list:
        """
        Retrieve Spotify track objects for the given track identifiers.
        
        Parameters:
            ids (list[str] | str): One or more Spotify track IDs, either as a list of ID strings or a comma-separated string.
        
        Returns:
            list: A list of track objects as returned by the Spotify API.
        """
        return self.sp.tracks(ids)["tracks"]

    def get_isrc(self, link):
        """
        Return ISRC information for a Spotify track URL or for all tracks in a Spotify album URL.
        
        Parameters:
        	link (str): A Spotify track or album URL (supports shortened spotify.link redirects). For an album URL, all tracks' ISRCs are collected; for a track URL, the single track is processed.
        
        Returns:
        	list: On success, a list of dictionaries each with keys:
        		- "isrc" (str): the track's ISRC
        		- "image" (str|None): the album image URL when available
        		- "track" (dict): the full track object returned by the Spotify API
        		If a track is missing an ISRC, the list will include the string "The Track is missing its ISRC on Spotify." at that position.
        	str: Returns "Error in get_isrc" if an expected `external_ids` field is missing for a track.
        """
        if not (self.client_id and self.client_secret):
            self.RRAuth()
        isrcs = []
        track = None
        match = re.search(r"spotify.link/\w+", link)
        if match:
            link = self.session.get(link).url

        match = re.search(r"album/(\w+)", link)
        if match:
            tracks = self.get_album_tracks(match.group(1))
            link = None
            ids = [temp["id"] for temp in tracks["items"]]
            tracks = self.get_tracks(ids)

            for i in tracks:
                if "external_ids" in i:
                    try:
                        image = i["album"]["images"][1]["url"]
                    except (IndexError, KeyError, TypeError):
                        image = None

                    if i["external_ids"].get("isrc"):
                        isrcs.append(
                            {
                                "isrc": i["external_ids"]["isrc"],
                                "image": image,
                                "track": i,
                            }
                        )
                    else:
                        isrcs.append("The Track is missing its ISRC on Spotify.")
                else:
                    return "Error in get_isrc"

            return isrcs

        else:
            track = self.get_track(link, track)
            print(link)
            if "external_ids" in track:
                try:
                    img = track["album"]["images"][1]["url"]
                except (IndexError, KeyError, TypeError):
                    img = None
                isrcs.append(
                    {
                        "isrc": track["external_ids"]["isrc"],
                        "image": img,
                        "track": track,
                    }
                )
                return isrcs
            else:
                return "Error in get_isrc"

    def artist_albums(self, link, albums=[], offset=0) -> list:
        """
        Retrieve all albums, singles, and compilations for an artist.
        
        Parameters:
        	link (str): Spotify artist ID or URL identifying the artist.
        	albums (list): Internal accumulator for collected album items; callers should not provide this unless intentionally continuing a partial result.
        	offset (int): Pagination offset for fetching results; callers rarely need to set this.
        
        Returns:
        	list: A list of album objects (the items returned by the Spotify API's artist albums endpoint).
        """
        data = self.sp.artist_albums(
            link, limit=50, offset=offset, album_type="album,single,compilation"
        )
        offset = offset + 50
        albums.extend(data["items"])
        if data["next"]:
            return self.artist_albums(link, albums, offset)
        else:
            return albums

    def get_spotify_id(self, link):
        """
        Extract the Spotify track ID from a Spotify URL or string.
        
        Parameters:
            link (str): A Spotify URL or string that may contain a "track/<id>" or "artist/<id>" path.
        
        Returns:
            str: The extracted track ID if a "track/<id>" pattern is present, `None` otherwise.
        """
        match = re.search(r"track/(\w+)", link)
        if match:
            return match.group(1)
        elif re.search(r"artist/(\w+)", link):
            return re.search(r"track/(\w+)", link).group(1)

        else:
            return None

    def search_by_isrc(self, isrc):
        """
        Search Spotify for a track matching the given ISRC and return its data.
        
        Parameters:
            isrc (str): The ISRC code to search for.
        
        Returns:
            list: If a matching track is found, a list containing a single dict with keys:
                - "isrc": the track's ISRC string
                - "image": the track's album image URL (second image in the album's images)
                - "track": the full track metadata dict returned by Spotify
            Otherwise, a list containing the single string "No track found with this ISRC".
        """
        data = self.sp.search(f"isrc:{isrc}")
        if data["tracks"]["items"]:
            track = data["tracks"]["items"][0]
            if isrc == track["external_ids"]["isrc"]:
                img = track["album"]["images"][1]["url"]
                return [
                    {
                        "isrc": track["external_ids"]["isrc"],
                        "image": img,
                        "track": track,
                    }
                ]
        return ["No track found with this ISRC"]