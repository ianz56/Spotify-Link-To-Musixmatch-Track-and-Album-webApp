from apple import AppleMusic
import json

def test():
    am = AppleMusic()
    links = [
        "https://music.apple.com/id/album/alamak-single/1842131300",
        "https://music.apple.com/id/song/alamak/1842131302"
    ]
    
    for link in links:
        print(f"\nTesting with link: {link}")
        data = am.get_apple_music_data(link)
        print(json.dumps(data, indent=2))

if __name__ == "__main__":
    test()
