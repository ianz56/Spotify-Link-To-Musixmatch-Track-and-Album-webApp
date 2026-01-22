from unittest.mock import Mock

import pytest

from apple import AppleMusic


@pytest.fixture
def apple_music():
    """
    Create and return a new AppleMusic client instance.
    
    Returns:
        AppleMusic: A fresh AppleMusic client.
    """
    return AppleMusic()


def test_get_apple_music_data_success(apple_music, mocker):
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200

    # Sample HTML with JSON-LD
    html_content = """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@graph": [
                {
                    "@type": "MusicRecording",
                    "name": "Test Song",
                    "isrc": "US1234567890",
                    "image": "http://example.com/image.jpg",
                    "byArtist": [
                        {
                            "@type": "MusicGroup",
                            "name": "Test Artist"
                        }
                    ],
                    "inAlbum": {
                        "name": "Test Album"
                    }
                }
            ]
        }
        </script>
    </head>
    <body></body>
    </html>
    """
    mock_response.text = html_content

    # Mock session.get
    mocker.patch.object(apple_music.session, "get", return_value=mock_response)

    result = apple_music.get_apple_music_data("http://apple.music/test")

    assert len(result) == 1
    track = result[0]
    assert track["isrc"] == "US1234567890"
    assert track["track"]["name"] == "Test Song"
    assert track["track"]["artists"][0]["name"] == "Test Artist"
    assert track["track"]["album"]["name"] == "Test Album"


def test_get_apple_music_data_opengraph_fallback(apple_music, mocker):
    mock_response = Mock()
    mock_response.status_code = 200

    html_content = """
    <html>
    <head>
        <meta property="og:title" content="Fallback Song by Fallback Artist" />
        <meta property="og:image" content="http://example.com/og_image.jpg" />
    </head>
    <body></body>
    </html>
    """
    mock_response.text = html_content

    mocker.patch.object(apple_music.session, "get", return_value=mock_response)

    result = apple_music.get_apple_music_data("http://apple.music/fallback")

    assert len(result) == 1
    track = result[0]
    assert track["isrc"] is None
    assert track["track"]["name"] == "Fallback Song"
    assert track["track"]["artists"][0]["name"] == "Fallback Artist"
    assert track["image"] == "http://example.com/og_image.jpg"


def test_get_apple_music_data_error(apple_music, mocker):
    mock_response = Mock()
    mock_response.status_code = 404

    mocker.patch.object(apple_music.session, "get", return_value=mock_response)

    result = apple_music.get_apple_music_data("http://apple.music/error")

    assert len(result) == 1
    assert "Error" in result[0]