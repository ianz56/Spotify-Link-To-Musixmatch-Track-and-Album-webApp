import asyncio
import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import time

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
from flask_babel import gettext as _
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
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError:
        return None

    try:
        # Add padding if needed
        payload_padding = len(encoded_payload) % 4
        if payload_padding:
            encoded_payload += "=" * (4 - payload_padding)
        payload = base64.urlsafe_b64decode(encoded_payload).decode("utf-8")
    except Exception:
        return None

    expected_signature = hmac.new(
        SECRET_KEY,
        (encoded_header + "." + encoded_payload.rstrip("=")).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_encoded_signature = base64.urlsafe_b64encode(expected_signature).rstrip(
        b"="
    )

    # Use constant time comparison
    if not hmac.compare_digest(
        expected_encoded_signature, encoded_signature.encode("utf-8")
    ):
        return None

    try:
        payload = json.loads(payload)
        # Check expiration
        exp = payload.get("exp")
        if not isinstance(exp, int) or exp < time.time():
            return None
    except json.JSONDecodeError:
        return None

    return payload


def jwt_ref(resp, payload):
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
    Inject Vercel Speed Insights script into HTML responses.
    This tracks Web Vitals for performance monitoring on Vercel.
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
    lang = request.cookies.get("language")
    if lang in SUPPORTED_LANGUAGES:
        return lang
    # 2. Check browser settings
    return request.accept_languages.best_match(SUPPORTED_LANGUAGES)


def make_cache_key():
    """Custom cache key that includes the current locale and request path."""
    return f"{request.full_path}:{get_locale()}"


babel = Babel(app, locale_selector=get_locale)


@app.context_processor
def inject_get_locale():
    return dict(get_locale=get_locale, using_redis=app.config.get("USING_REDIS"))


sp = Spotify()
apple_music = AppleMusic()


@app.route("/set_language/<language>")
def set_language(language=None):
    response = make_response(redirect(request.referrer or url_for("index")))
    if language in SUPPORTED_LANGUAGES:
        response.set_cookie("language", language, max_age=60 * 60 * 24 * 30)
    return response


@app.route("/", methods=["GET"])
async def index():
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
        resp.set_cookie(
            "api_token",
            token.decode("utf-8"),
            expires=expire_date,
            httponly=True,
            secure=True,
            samesite="Lax",
        )
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
                            tracks_data=[_("Wrong Spotify Link Or Wrong ISRC")],
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
                    app.logger.exception(e)
                    return render_template(
                        "index.html",
                        tracks_data=[
                            _("An unexpected error occurred, please try again")
                        ],
                    )

        if isinstance(mxmLinks, str):
            app.logger.error(f"Error fetching tracks: {mxmLinks}")
            return render_template(
                "index.html",
                tracks_data=[_("An unexpected error occurred, please try again")],
            )

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
                    return render_template("split.html", error="track2: " + track2)

                track1["track"] = sp_data1[0]["track"]
                track2["track"] = sp_data2[0]["track"]
                try:
                    if (
                        track1["isrc"] != track2["isrc"]
                        and track1["commontrack_id"] == track2["commontrack_id"]
                    ):
                        message = f"""{_("Can be splitted")}</br>
                            {_("you can copy and paste this:")}</br>
                            <div id="copy-target" class="copy-target">
                            :mxm: <a href="{track1["track_share_url"]}" target="_blank">MXM Page</a> </br>
                            :spotify: <a href="{link}" target="_blank">{track1["track"]["name"]}</a>,
                            :isrc: {track1["isrc"]} </br>
                            :spotify: <a href="{link2}" target="_blank">{track2["track"]["name"]}</a>,
                            :isrc: {track2["isrc"]}
                            </div>
                            <br>
                            <button onclick="copyToClipboard()" class="btn-copy">{_("Copy Template")}</button>
                            <script>
                            function copyToClipboard() {{
                                const range = document.createRange();
                                range.selectNode(document.getElementById("copy-target"));
                                window.getSelection().removeAllRanges();
                                window.getSelection().addRange(range);
                                document.execCommand("copy");
                                window.getSelection().removeAllRanges();
                                alert({json.dumps(_('Copied to clipboard!'))});
                            }}
                            </script>
                            """
                    elif (
                        track1["isrc"] == track2["isrc"]
                        and track1["commontrack_id"] == track2["commontrack_id"]
                    ):
                        message = _("Can not be splitted as they have the Same ISRC")
                    else:
                        message = _("They have different Pages")
                except:
                    return render_template(
                        "split.html", error=_("Something went wrong")
                    )

                return render_template(
                    "split.html",
                    split_result={"track1": track1, "track2": track2},
                    message=message,
                )
            else:
                return render_template("split.html", error=_("Wrong Spotify Link"))

    else:
        return render_template("split.html")


@app.route("/spotify", methods=["GET"])
@cache.cached(timeout=3600, key_prefix=make_cache_key)
def isrc():
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
            return render_template("isrc.html", tracks_data=[_("Wrong Spotify Link")])
    else:
        return render_template("isrc.html")


@app.route("/apple", methods=["GET"])
async def apple():
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

                if (
                    isinstance(tracks_data, list)
                    and tracks_data
                    and isinstance(tracks_data[0], str)
                ):
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
            # print(mxmLinks)

        if isinstance(mxmLinks[0], str):
            return render_template("api.html", error=_("Please Enter A Valid Key"))

        payload = {
            "mxm-key": key,
            "exp": int(
                (datetime.datetime.now() + datetime.timedelta(hours=1)).timestamp()
            ),
        }
        token = generate_token(payload)

        resp = make_response(render_template("api.html", key="Token Generated"))
        expire_date = datetime.datetime.now() + datetime.timedelta(hours=1)
        resp.set_cookie(
            "api_token",
            token.decode("utf-8"),
            expires=expire_date,
            httponly=True,
            secure=True,
            samesite="Lax",
        )
        return resp

    elif delete:
        resp = make_response(render_template("api.html"))
        resp.delete_cookie("api_token")
        return resp

    else:
        return render_template("api.html", key=None)


@app.route("/mxm", methods=["GET"])
async def mxm_to_sp():
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
            track=album.get("track"),
            error=album.get("error"),
            is_cached=is_cached,
            cached_timestamp=cached_timestamp,
        )
    else:
        return render_template("mxm.html")


@app.route("/abstrack", methods=["GET"])
@cache.cached(timeout=3600, key_prefix=make_cache_key)
async def abstrack() -> str:
    """Get the track data from the abstract track"""
    id = request.args.get("id")
    key = None
    if id:
        token = request.cookies.get("api_token")
        if token:
            payload = verify_token(token)
            if payload:
                key = payload.get("mxm-key")
        if not re.match("^[0-9]+$", id):
            return render_template("abstrack.html", error=_("Invalid input!"))

        async with aiohttp.ClientSession() as session:
            mxm = MXM(key, session=session)
            track, album = await mxm.abstrack(id)

        return render_template(
            "abstrack.html", track=track, album=album, error=track.get("error")
        )
    else:
        return render_template("abstrack.html")


@app.route("/credits")
def credits():
    return render_template("credits.html")


@app.route("/BingSiteAuth.xml")
def bing_site_auth():
    return send_from_directory(app.static_folder, "BingSiteAuth.xml")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.static_folder, "assets"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/robots.txt")
def robots():
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
    sitemap_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    # List of endpoints to include in sitemap
    pages = [
        "index",
        "isrc",
        "mxm_to_sp",
        "abstrack",
        "split",
        "setAPI",
        "apple",
        "credits",
    ]

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
