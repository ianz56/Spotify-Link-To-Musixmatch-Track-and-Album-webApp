import asyncio
import base64
import datetime
import hashlib
import hmac
import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

import aiohttp
from asgiref.wsgi import WsgiToAsgi
from flask import (
    Flask,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_babel import Babel
from flask_caching import Cache

from apple import AppleMusic
from mxm import MXM
from spotify import Spotify

secret_key_value = os.environ.get("secret_key")

if not secret_key_value:
    # Use a default key for development if not provided, or raise an error in production
    if os.environ.get("FLASK_ENV") == "production":
        raise ValueError("No secret_key set for Flask application in production")
    print("⚠️ 'secret_key' not found. Using default dev key.")
    secret_key_value = "default-dev-secret-key"

SECRET_KEY = secret_key_value.encode("utf-8")


def generate_token(payload):
    """
    Create a signed JWT-like token for the given JSON-serializable payload.
    
    The token consists of three URL-safe base64 segments (header, payload, signature) separated by dots and without padding. The header specifies HS256 and JWT; the signature is an HMAC-SHA256 using SECRET_KEY.
    
    Parameters:
        payload (object): A JSON-serializable object to include as the token payload.
    
    Returns:
        bytes: The complete token as bytes in the form b'header.payload.signature'.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = base64.urlsafe_b64encode(
        json.dumps(header).encode("utf-8")
    ).rstrip(b"=")
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).rstrip(b"=")

    signature = hmac.new(
        SECRET_KEY, encoded_header + b"." + encoded_payload, hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=")

    return encoded_header + b"." + encoded_payload + b"." + encoded_signature


def verify_token(token):
    """
    Validate a JWT-like token and return its decoded JSON payload if the token is well-formed and the signature matches.
    
    Parameters:
        token (str): Token string in the form "header.payload.signature".
    
    Returns:
        dict: Decoded JSON payload when the token is valid, or `None` if the token is malformed, the signature is invalid, or the payload is not valid JSON.
    """
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError:
        return None

    # header = base64.urlsafe_b64decode(encoded_header + "==").decode("utf-8")
    try:
        payload = base64.urlsafe_b64decode(encoded_payload + "==").decode("utf-8")
    except Exception:
        return None

    expected_signature = hmac.new(
        SECRET_KEY,
        (encoded_header + "." + encoded_payload).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_encoded_signature = base64.urlsafe_b64encode(expected_signature).rstrip(
        b"="
    )

    if expected_encoded_signature != encoded_signature.encode("utf-8"):
        return None

    try:
        payload = json.loads(payload)
    except json.JSONDecodeError:
        return None

    return payload


def jwt_ref(resp, payload):
    """
    Attach a refreshed API token cookie to the provided response with a 3-day expiration.
    
    Updates the given payload's `exp` field to a timestamp three days from now, generates a new token from that payload, and sets it as the `api_token` cookie on the response with the same expiration.
    
    Parameters:
        resp (flask.Response): The response object to modify by setting the cookie.
        payload (dict): The token payload to be encoded; its `exp` field will be mutated to the new expiration timestamp.
    
    Returns:
        flask.Response: The same response object with the `api_token` cookie set.
    """
    current_time = datetime.datetime.now()
    payload["exp"] = int((current_time + datetime.timedelta(days=3)).timestamp())
    new_token = generate_token(payload)
    expire_date = current_time + datetime.timedelta(days=3)
    resp.set_cookie("api_token", new_token.decode("utf-8"), expires=expire_date)
    return resp


app = Flask(__name__)

# Vercel Speed Insights Setup
VERCEL_SPEED_INSIGHTS_SCRIPT = """<script>
window.si = window.si || function () { (window.siq = window.siq || []).push(arguments); };
</script>
<script defer src="/_vercel/speed-insights/script.js"></script>"""


@app.after_request
def inject_vercel_speed_insights(response):
    """
    Injects the Vercel Speed Insights script into HTML responses by inserting the script before the closing </body> tag.
    
    Parameters:
        response (flask.Response): The HTTP response object to modify. Only responses with a content type containing "text/html" are modified.
    
    Returns:
        flask.Response: The original response object, possibly modified to include the Speed Insights script and an updated Content-Length header.
    
    Notes:
        - If the response body does not contain a closing </body> tag, no change is made.
        - Exceptions during injection are caught and suppressed; the original response is returned unchanged on error.
    """
    if response.content_type and "text/html" in response.content_type:
        try:
            response_text = response.get_data(as_text=True)
            # Insert Speed Insights script before closing body tag
            if "</body>" in response_text:
                response_text = response_text.replace(
                    "</body>", f"{VERCEL_SPEED_INSIGHTS_SCRIPT}\n</body>"
                )
                response.set_data(response_text)
                # Update content length since we modified the response
                response.headers["Content-Length"] = len(response.get_data())
        except Exception as e:
            print(f"⚠️ Failed to inject Vercel Speed Insights: {e}")
            pass  # Continue normally if injection fails
    return response


import redis

# Cache Configuration
redis_host = os.environ.get("REDIS_HOST")
redis_port = os.environ.get("REDIS_PORT")
redis_password = os.environ.get("REDIS_PASSWD")

use_redis = False
if redis_host and redis_port and redis_password:
    try:
        # Test connection with a short timeout
        r_test = redis.Redis(
            host=redis_host,
            port=int(redis_port),
            password=redis_password,
            socket_connect_timeout=1,
        )
        if r_test.ping():
            use_redis = True
            print("✅ Redis connection successful. Using RedisCache.")
            r_test.close()
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}. Falling back to SimpleCache.")

if use_redis:
    cache_config = {
        "CACHE_TYPE": "RedisCache",
        "CACHE_REDIS_HOST": redis_host,
        "CACHE_REDIS_PORT": int(redis_port),
        "CACHE_REDIS_PASSWORD": redis_password,
        "CACHE_DEFAULT_TIMEOUT": 3600,
    }
else:
    cache_config = {
        "CACHE_TYPE": "SimpleCache",  # Fallback to memory
        "CACHE_DEFAULT_TIMEOUT": 3600,
    }

app.config.from_mapping(cache_config)
# Store status in config for easy access
app.config["USING_REDIS"] = use_redis
cache = Cache(app)


SUPPORTED_LANGUAGES = ["en", "id", "su"]


def get_locale():
    # 1. Check if user has explicitly set a language cookie
    """
    Select the request locale using a language cookie or the client's Accept-Language header.
    
    Checks the "language" cookie and returns it when it is one of SUPPORTED_LANGUAGES; otherwise returns the best match from the request's Accept-Language header.
    
    Returns:
        str or None: The chosen locale string (one of SUPPORTED_LANGUAGES) or `None` if no suitable match is found.
    """
    lang = request.cookies.get("language")
    if lang in SUPPORTED_LANGUAGES:
        return lang
    # 2. Check browser settings
    return request.accept_languages.best_match(SUPPORTED_LANGUAGES)


def make_cache_key():
    """
    Builds a cache key combining the request's full path and current locale.
    
    Returns:
        cache_key (str): A string in the form "<full_path>:<locale>" suitable for use as a per-request cache key.
    """
    return f"{request.full_path}:{get_locale()}"


babel = Babel(app, locale_selector=get_locale)


@app.context_processor
def inject_get_locale():
    """
    Expose values for template context: the locale selector and whether Redis is used.
    
    Returns:
        dict: Mapping with keys:
            - "get_locale": the function that selects the current request locale.
            - "using_redis": `True` if the application is configured to use Redis for caching, `False` otherwise.
    """
    return dict(get_locale=get_locale, using_redis=app.config.get("USING_REDIS"))


sp = Spotify()
apple_music = AppleMusic()


@app.route("/set_language/<language>")
def set_language(language=None):
    """
    Set the user's preferred language via a cookie and redirect back to the referrer or the index.
    
    Parameters:
    	language (str | None): Language code to set; only values present in SUPPORTED_LANGUAGES are accepted.
    
    Returns:
    	response (flask.Response): A redirect response to the referrer or index. If `language` is valid, the response includes a `language` cookie set for 30 days.
    """
    response = make_response(redirect(request.referrer or url_for("index")))
    if language in SUPPORTED_LANGUAGES:
        response.set_cookie("language", language, max_age=60 * 60 * 24 * 30)
    return response


@app.route("/", methods=["GET"])
async def index():
    """
    Render the application's index page, handling optional music link lookups, caching, and API token lifecycle.
    
    Handles three main flows:
    - If an `api_key` cookie is present, exchanges it for a short-lived `api_token` cookie and returns a response rendering the index.
    - If a `link` query parameter is provided, attempts to resolve it to MXM track data (using cache when available) and renders the index with lookup results or errors.
    - Otherwise, renders the index and, if a valid `api_token` is present, refreshes that token on the response.
    
    Returns:
    	Flask response or template string: a response object when cookies are set or refreshed; otherwise the rendered index HTML string or, in some error cases, a direct string result from MXM.
    """
    if request.cookies.get("api_key"):
        payload = {
            "mxm-key": request.cookies.get("api_key"),
            "exp": int(
                (datetime.datetime.now() + datetime.timedelta(days=3)).timestamp()
            ),
        }
        token = generate_token(payload)

        resp = make_response(render_template("index.html"))
        expire_date = datetime.datetime.now() + datetime.timedelta(hours=1)
        resp.delete_cookie("api_key")
        resp.set_cookie("api_token", token, expires=expire_date)
        return resp

    link = request.args.get("link")
    refresh = request.args.get("refresh")
    key = None
    token = request.cookies.get("api_token")
    if link:
        if token:
            payload = verify_token(token)
            if payload:
                key = payload.get("mxm-key")

        # Manual Cache Check
        cache_key = f"search_data:{link}:{get_locale()}"
        cached_data = None
        if not refresh:
            cached_data = cache.get(cache_key)

        mxmLinks = None
        is_cached = False
        cached_timestamp = None

        if cached_data:
            if isinstance(cached_data, dict) and "data" in cached_data:
                mxmLinks = cached_data["data"]
                cached_timestamp = cached_data.get("timestamp")
                # Parse timestamp if it's a string
                if isinstance(cached_timestamp, str):
                    try:
                        cached_timestamp = datetime.datetime.fromisoformat(
                            cached_timestamp
                        )
                    except ValueError:
                        pass
            else:
                mxmLinks = cached_data
            is_cached = True
            print(f"CACHE HIT: {cache_key}")

        else:
            print(f"CACHE MISS: {cache_key}")
            async with aiohttp.ClientSession() as session:
                try:
                    mxm = MXM(key, session=session)
                    if len(link) < 12:
                        return render_template(
                            "index.html",
                            tracks_data=["Wrong Spotify Link Or Wrong ISRC"],
                        )
                    elif re.search(r"artist/(\w+)", link):
                        artist_albums = await asyncio.to_thread(
                            sp.artist_albums, link, []
                        )
                        return render_template("index.html", artist=artist_albums)
                    else:
                        sp_data = (
                            await asyncio.to_thread(sp.get_isrc, link)
                            if len(link) > 12
                            else [{"isrc": link, "image": None}]
                        )

                    mxmLinks = await mxm.Tracks_Data(sp_data)

                    # Cache the result if valid
                    if isinstance(mxmLinks, list):
                        cache_value = {
                            "data": mxmLinks,
                            "timestamp": datetime.datetime.now().isoformat(),
                        }
                        cache.set(cache_key, cache_value, timeout=3600)

                except Exception as e:
                    return render_template("index.html", tracks_data=[str(e)])

        if isinstance(mxmLinks, str):
            return mxmLinks

        return render_template(
            "index.html",
            tracks_data=mxmLinks,
            is_cached=is_cached,
            cached_timestamp=cached_timestamp,
        )

    # refresh the token every time the user enter the site
    if token:
        payload = verify_token(token)
        if payload:
            resp = make_response(render_template("index.html"))
            resp = jwt_ref(resp, payload)
            return resp

    return render_template("index.html")


@app.route("/split", methods=["GET"])
@cache.cached(timeout=3600, key_prefix=make_cache_key)
async def split():
    """
    Render the split comparison page for two Spotify track links.
    
    This handler accepts two Spotify track links from the request query parameters and, if both are provided, compares their Spotify-derived ISRC and MXM commontrack information (using an optional MXM key from the `api_token` cookie) to determine whether the tracks can be split. On success renders "split.html" with `split_result` (a dict containing `track1` and `track2`) and a human-readable `message`. If the links are missing, invalid, or an error occurs, renders "split.html" with an `error` message.
    
    Returns:
        A Flask response rendering "split.html". On success the template context includes `split_result` and `message`; on failure the context includes `error`.
    """
    link = request.args.get("link")
    link2 = request.args.get("link2")
    key = None
    if link and link2:
        token = request.cookies.get("api_token")
        if token:
            payload = verify_token(token)
            if payload:
                key = payload.get("mxm-key")

        async with aiohttp.ClientSession() as session:
            mxm = MXM(key, session=session)
            match = re.search(r"open.spotify.com", link) and re.search(r"track", link)
            match = (
                match
                and re.search(r"open.spotify.com", link2)
                and re.search(r"track", link2)
            )
            if match:
                sp_data1 = await asyncio.to_thread(sp.get_isrc, link)
                sp_data2 = await asyncio.to_thread(sp.get_isrc, link2)
                track1 = await mxm.Tracks_Data(sp_data1, True)
                track1 = track1[0]
                if isinstance(track1, str):
                    return render_template("split.html", error="track1: " + track1)
                track2 = await mxm.Tracks_Data(sp_data2, True)
                track2 = track2[0]
                if isinstance(track2, str):
                    return render_template("split.html", error="track2: " + track1)

                track1["track"] = sp_data1[0]["track"]
                track2["track"] = sp_data2[0]["track"]
                try:
                    if (
                        track1["isrc"] != track2["isrc"]
                        and track1["commontrack_id"] == track2["commontrack_id"]
                    ):
                        message = f"""Can be splitted </br>
                            you can c/p:</br>
                            :mxm: <a href="{track1["track_share_url"]}" target="_blank">MXM Page</a> </br>
                            :spotify: <a href="{link}" target="_blank">{track1["track"]["name"]}</a>,
                            :isrc: {track1["isrc"]} </br>
                            :spotify: <a href="{link2}" target="_blank">{track2["track"]["name"]}</a>,
                            :isrc: {track2["isrc"]}
                            """
                    elif (
                        track1["isrc"] == track2["isrc"]
                        and track1["commontrack_id"] == track2["commontrack_id"]
                    ):
                        message = "Can not be splitted as they have the Same ISRC"
                    else:
                        message = "They have different Pages"
                except:
                    return render_template("split.html", error="Something went wrong")

                return render_template(
                    "split.html",
                    split_result={"track1": track1, "track2": track2},
                    message=message,
                )
            else:
                return render_template("split.html", error="Wrong Spotify Link")

    else:
        return render_template("split.html")


@app.route("/spotify", methods=["GET"])
@cache.cached(timeout=3600, key_prefix=make_cache_key)
def isrc():
    """
    Render ISRC lookup page for a Spotify track/album link or a raw ISRC code.
    
    Parameters:
        None. Reads the optional `link` query parameter from the request:
            - If `link` is a Spotify track or album URL, the template receives `tracks_data` from `sp.get_isrc(link)`.
            - If `link` is a 12-character ISRC code, the template receives `tracks_data` from `sp.search_by_isrc(link)`.
            - If `link` is present but invalid, the template receives `tracks_data = ['Wrong Spotify Link']`.
            - If `link` is not provided, the template is rendered without `tracks_data`.
    
    Returns:
        Rendered 'isrc.html' template populated as described above.
    """
    link = request.args.get("link")
    if link:
        match = re.search(r"open.spotify.com", link) and re.search(r"track|album", link)
        if match:
            return render_template("isrc.html", tracks_data=sp.get_isrc(link))

        else:
            # the link is an isrc code
            if len(link) == 12:
                # search by isrc
                return render_template("isrc.html", tracks_data=sp.search_by_isrc(link))
            return render_template("isrc.html", tracks_data=["Wrong Spotify Link"])
    else:
        return render_template("isrc.html")


@app.route("/apple", methods=["GET"])
async def apple():
    """
    Handle the GET /apple route: fetch Apple Music metadata for an input link, convert it to MXM track data, and render the Apple page.
    
    When a "link" query parameter is provided, this handler:
    - Attempts to use a server-side MXM API key from a valid `api_token` cookie (if present).
    - Uses a locale-aware cache for the link; the "refresh" query parameter bypasses cached results.
    - Returns a rendered "apple.html" template populated with `tracks_data` (MXM-converted data). The template context also includes `is_cached` and `cached_timestamp` when cached data is used.
    - If MXM returns a plain string (error or redirect), that string is returned directly.
    
    When no "link" is provided and a valid `api_token` cookie exists, the handler renders "apple.html" and refreshes the API token cookie on the response.
    
    Returns:
        A Flask response that is either:
        - the rendered "apple.html" template with `tracks_data` and optional caching metadata,
        - a raw string returned by MXM when applicable,
        - or "apple.html" rendered with no track data.
    """
    link = request.args.get("link")
    refresh = request.args.get("refresh")
    key = None
    token = request.cookies.get("api_token")
    if link:
        if token:
            payload = verify_token(token)
            if payload:
                key = payload.get("mxm-key")

        cache_key = f"apple_search:{link}:{get_locale()}"

        cached_data = None
        if not refresh:
            cached_data = cache.get(cache_key)

        mxmLinks = None
        is_cached = False
        cached_timestamp = None

        if cached_data:
            if isinstance(cached_data, dict) and "data" in cached_data:
                mxmLinks = cached_data["data"]
                cached_timestamp = cached_data.get("timestamp")
                # Parse timestamp if it's a string
                if isinstance(cached_timestamp, str):
                    try:
                        cached_timestamp = datetime.datetime.fromisoformat(
                            cached_timestamp
                        )
                    except ValueError:
                        pass
            else:
                mxmLinks = cached_data
            is_cached = True
        else:
            async with aiohttp.ClientSession() as session:
                mxm = MXM(key, session=session)
                # Fetch Apple Music data (run in thread to avoid blocking)
                tracks_data = await asyncio.to_thread(
                    apple_music.get_apple_music_data, link
                )

                if isinstance(tracks_data, list) and isinstance(tracks_data[0], str):
                    # Error or message
                    return render_template("apple.html", tracks_data=tracks_data)

                mxmLinks = await mxm.Tracks_Data(tracks_data)

                if isinstance(mxmLinks, list):
                    cache_value = {
                        "data": mxmLinks,
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                    cache.set(cache_key, cache_value, timeout=3600)

        if isinstance(mxmLinks, str):
            return mxmLinks

        return render_template(
            "apple.html",
            tracks_data=mxmLinks,
            is_cached=is_cached,
            cached_timestamp=cached_timestamp,
        )

    # refresh the token every time the user enter the site
    if token:
        payload = verify_token(token)
        if payload:
            resp = make_response(render_template("apple.html"))
            resp = jwt_ref(resp, payload)
            return resp

    return render_template("apple.html")


@app.route("/api", methods=["GET"])
async def setAPI():
    """
    Handle the API key management page: validate, generate, refresh, or delete an MXM API token and render the API UI.
    
    Validates an explicit `key` by calling MXM.Tracks_Data; on success generates an `api_token` cookie containing the MXM key and returns a response rendering "api.html" with a success message. If an existing valid `api_token` cookie is present, refreshes that token, returns a response rendering "api.html" with the censored key, and sets the refreshed cookie. If `delete_key` is provided, clears the `api_token` cookie and returns the API page. If validation fails, returns the API page with an error message; if no action is taken, returns the API page with `key=None`.
    
    Returns:
        A Flask response or rendered template: a response that may set or delete the `api_token` cookie and renders "api.html" with the appropriate key, status, or error message.
    """
    key = request.args.get("key")
    delete = request.args.get("delete_key")

    # Get the existing token from the cookie
    token = request.cookies.get("api_token")
    if token:
        payload = verify_token(token)
        if payload:
            key = payload.get("mxm-key")
            censored_key = "*" * len(key) if key else None

            # refresh the token each time the user enter the "/api"
            resp = make_response(render_template("api.html", key=censored_key))
            resp = jwt_ref(resp, payload)
            return resp

    if key:
        # check the key
        async with aiohttp.ClientSession() as session:
            mxm = MXM(key, session=session)
            sp_data = [{"isrc": "DGA072332812", "image": None}]

            # Call the Tracks_Data method with the appropriate parameters
            mxmLinks = await mxm.Tracks_Data(sp_data)
            print(mxmLinks)

        if isinstance(mxmLinks[0], str):
            return render_template("api.html", error="Please Enter A Valid Key")

        payload = {
            "mxm-key": key,
            "exp": int(
                (datetime.datetime.now() + datetime.timedelta(hours=1)).timestamp()
            ),
        }
        token = generate_token(payload)

        resp = make_response(render_template("api.html", key="Token Generated"))
        expire_date = datetime.datetime.now() + datetime.timedelta(hours=1)
        resp.set_cookie("api_token", token.decode("utf-8"), expires=expire_date)
        return resp

    elif delete:
        resp = make_response(render_template("api.html"))
        resp.delete_cookie("api_token")
        return resp

    else:
        return render_template("api.html", key=None)


@app.route("/mxm", methods=["GET"])
async def mxm_to_sp():
    """
    Render the MXM-to-Spotify lookup page, optionally resolving an MXM link into Spotify album data.
    
    When the `link` query parameter is provided:
    - Attempts to read `api_token` cookie and extract an `mxm-key` for authenticated MXM requests.
    - Returns cached album data for the key `mxm_search:{link}:{locale}` unless the `refresh` query parameter is present.
    - If not cached or `refresh` is set, calls MXM.album_sp_id(link) to fetch album data, caches successful results for 3600 seconds, and provides the fetched data to the template.
    
    Template context (passed to mxm.html):
    - album: The album object from MXM response (or `None` if unavailable).
    - error: Error payload from MXM response (or `None`).
    - is_cached: `True` if the response came from cache, `False` otherwise.
    - cached_timestamp: A datetime indicating when cached data was stored, or `None`.
    
    If no `link` query parameter is provided, renders mxm.html without album data.
    
    Returns:
        Flask response: Rendered mxm.html with the context described above.
    """
    link = request.args.get("link")
    refresh = request.args.get("refresh")
    key = None

    if link:
        token = request.cookies.get("api_token")
        if token:
            payload = verify_token(token)
            if payload:
                key = payload.get("mxm-key")

        cache_key = f"mxm_search:{link}:{get_locale()}"
        cached_data = None
        if not refresh:
            cached_data = cache.get(cache_key)

        album = None
        is_cached = False
        cached_timestamp = None

        if cached_data:
            if isinstance(cached_data, dict) and "data" in cached_data:
                album = cached_data["data"]
                cached_timestamp = cached_data.get("timestamp")
                if isinstance(cached_timestamp, str):
                    try:
                        cached_timestamp = datetime.datetime.fromisoformat(
                            cached_timestamp
                        )
                    except ValueError:
                        pass
            else:
                album = cached_data
            is_cached = True
        else:
            async with aiohttp.ClientSession() as session:
                mxm = MXM(key, session=session)
                album = await mxm.album_sp_id(link)

                if album and not album.get("error"):
                    cache_value = {
                        "data": album,
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                    cache.set(cache_key, cache_value, timeout=3600)

        return render_template(
            "mxm.html",
            album=album.get("album"),
            error=album.get("error"),
            is_cached=is_cached,
            cached_timestamp=cached_timestamp,
        )
    else:
        return render_template("mxm.html")


@app.route("/abstrack", methods=["GET"])
@cache.cached(timeout=3600, key_prefix=make_cache_key)
async def abstrack() -> str:
    """
    Render the abstrack page populated with MXM abstract track and album data.
    
    If the request includes a numeric `id` query parameter, the handler validates the id, optionally extracts an `mxm-key` from the `api_token` cookie, fetches the corresponding track and album via MXM.abstrack, and renders "abstrack.html" with `track`, `album`, and `error` (taken from `track.get("error")`) as context. If `id` is missing, renders "abstrack.html" without track or album. If `id` is non-numeric, renders the template with an "Invalid input!" error.
    
    Returns:
        str: The rendered HTML page.
    """
    id = request.args.get("id")
    key = None
    if id:
        token = request.cookies.get("api_token")
        if token:
            payload = verify_token(token)
            if payload:
                key = payload.get("mxm-key")
        if not re.match("^[0-9]+$", id):
            return render_template("abstrack.html", error="Invalid input!")

        async with aiohttp.ClientSession() as session:
            mxm = MXM(key, session=session)
            track, album = await mxm.abstrack(id)

        return render_template(
            "abstrack.html", track=track, album=album, error=track.get("error")
        )
    else:
        return render_template("abstrack.html")


@app.route("/BingSiteAuth.xml")
def bing_site_auth():
    """
    Serve the BingSiteAuth.xml file from the application's static folder for Bing site verification.
    
    Returns:
        werkzeug.wrappers.Response: A response serving the BingSiteAuth.xml file (XML content).
    """
    return send_from_directory(app.static_folder, "BingSiteAuth.xml")


@app.route("/favicon.ico")
def favicon():
    """
    Serve the site's favicon from the static assets directory.
    
    Returns:
        A Flask response sending the `favicon.ico` file from the app's static assets with MIME type `image/vnd.microsoft.icon`.
    """
    return send_from_directory(
        os.path.join(app.static_folder, "assets"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/robots.txt")
def robots():
    """
    Generate a robots.txt response that allows all crawlers and provides the sitemap URL.
    
    The response body contains the following directives:
    - `User-agent: *`
    - `Allow: /`
    - `Sitemap: <absolute sitemap URL>`
    
    Returns:
        Response: A Flask `Response` whose body is the robots.txt text and whose
        `Content-Type` header is set to `text/plain`.
    """
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {url_for('sitemap', _external=True)}",
    ]
    response = make_response("\n".join(lines))
    response.headers["Content-Type"] = "text/plain"
    return response


@app.route("/sitemap.xml")
def sitemap():
    """
    Generate an XML sitemap listing selected site endpoints with weekly change frequency.
    
    The response body is a sitemap XML containing absolute URLs for the pages: index, isrc, mxm_to_sp, abstrack, split, and setAPI. The response includes a Content-Type header of "application/xml".
    
    Returns:
        flask.Response: HTTP response containing the sitemap XML.
    """
    sitemap_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    # List of endpoints to include in sitemap
    pages = ["index", "isrc", "mxm_to_sp", "abstrack", "split", "setAPI"]

    for page in pages:
        sitemap_xml.append("  <url>")
        sitemap_xml.append(f"    <loc>{url_for(page, _external=True)}</loc>")
        sitemap_xml.append("    <changefreq>weekly</changefreq>")
        sitemap_xml.append("  </url>")

    sitemap_xml.append("</urlset>")

    response = make_response("\n".join(sitemap_xml))
    response.headers["Content-Type"] = "application/xml"
    return response


asgi_app = WsgiToAsgi(app)
if __name__ == "__main__":
    import asyncio

    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    asyncio.run(serve(asgi_app, Config()))
    # app.run(debug=True)