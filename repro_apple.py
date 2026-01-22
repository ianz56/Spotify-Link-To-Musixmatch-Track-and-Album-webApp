import json

from apple import AppleMusic


def test():
    """
    Run a small reproduction that fetches and prints Apple Music data for two sample album links.
    
    Creates an AppleMusic instance, calls its get_apple_music_data method for two predefined Apple Music URLs, and prints each result as pretty-printed JSON to stdout.
    """
    am = AppleMusic()
    links = [
        "https://music.apple.com/album/1844274179",
        "https://music.apple.com/us/album/cinta-terindah-single/1844274179",
    ]

    for link in links:
        print(f"\nTesting with link: {link}")
        data = am.get_apple_music_data(link)
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    test()