from unittest.mock import Mock, patch

import pytest

from spotify import Spotify


@pytest.fixture
def mock_spotipy():
    with patch("spotify.spotipy.Spotify") as mock_sp_cls:
        mock_sp_instance = Mock()
        mock_sp_cls.return_value = mock_sp_instance
        yield mock_sp_instance


@pytest.fixture
def spotify_client(mock_spotipy):
    with patch("spotify.SpotifyClientCredentials"):
        # Mock env vars to avoid Redis auth
        with patch.dict(
            "os.environ",
            {"SPOTIPY_CLIENT_ID": "fake_id", "SPOTIPY_CLIENT_SECRET": "fake_secret"},
        ):
            return Spotify()


def test_get_isrc_single_track(spotify_client, mock_spotipy):
    # Setup mock return for track
    mock_track_data = {
        "external_ids": {"isrc": "US1234567890"},
        "album": {"images": [{"url": "http://img.com/1"}, {"url": "http://img.com/2"}]},
        "name": "Test Track",
        "artists": [{"name": "Test Artist"}],
    }
    mock_spotipy.track.return_value = mock_track_data

    # Call method
    link = "https://open.spotify.com/track/12345"
    result = spotify_client.get_isrc(link)

    assert len(result) == 1
    assert result[0]["isrc"] == "US1234567890"
    assert result[0]["image"] == "http://img.com/2"
    assert result[0]["track"] == mock_track_data


def test_get_isrc_album(spotify_client, mock_spotipy):
    # Setup mock return for album tracks and tracks
    mock_album_tracks = {"items": [{"id": "t1"}, {"id": "t2"}]}
    mock_spotipy.album_tracks.return_value = mock_album_tracks

    mock_tracks_data = {
        "tracks": [
            {
                "id": "t1",
                "external_ids": {"isrc": "ISRC1"},
                "album": {"images": [{}, {"url": "img1"}]},
            },
            {
                "id": "t2",
                "external_ids": {"isrc": "ISRC2"},
                "album": {"images": [{}, {"url": "img2"}]},
            },
        ]
    }
    mock_spotipy.tracks.return_value = mock_tracks_data

    link = "https://open.spotify.com/album/album123"
    result = spotify_client.get_isrc(link)

    assert len(result) == 2
    assert result[0]["isrc"] == "ISRC1"
    assert result[1]["isrc"] == "ISRC2"


def test_get_isrc_missing_external_ids(spotify_client, mock_spotipy):
    mock_track_data = {
        # No external_ids
        "album": {"images": [{}, {"url": "img"}]},
        "name": "No ISRC Track",
    }
    mock_spotipy.track.return_value = mock_track_data

    link = "https://open.spotify.com/track/missing"
    result = spotify_client.get_isrc(link)

    # Based on code, it returns "Error in get_isrc" string
    assert result == "Error in get_isrc"
