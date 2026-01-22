import requests
from bs4 import BeautifulSoup
import re
import json

class AppleMusic:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }

    def get_apple_music_data(self, link):
        try:
            response = self.session.get(link, headers=self.headers)
            if response.status_code != 200:
                return [f"Error: Could not fetch Apple Music page. Status code: {response.status_code}"]
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to find JSON-LD
            scripts = soup.find_all('script', type='application/ld+json')
            data = None
            
            for script in scripts:
                try:
                    loaded_data = json.loads(script.string)
                    # Check if it contains music data
                    if isinstance(loaded_data, dict) and '@graph' in loaded_data:
                         # Browse the graph
                         for item in loaded_data['@graph']:
                             if item.get('@type') in ['MusicRecording', 'MusicAlbum', 'MusicPlaylist']:
                                 data = item
                                 break
                    elif isinstance(loaded_data, dict) and loaded_data.get('@type') in ['MusicRecording', 'MusicAlbum', 'MusicPlaylist']:
                        data = loaded_data
                        break
                    elif isinstance(loaded_data, list):
                        for item in loaded_data:
                            if item.get('@type') in ['MusicRecording', 'MusicAlbum', 'MusicPlaylist']:
                                data = item
                                break
                    if data: break
                except:
                    continue
            
            results = []
            
            if data:
                print(f"DEBUG: Found data type: {data.get('@type')}") # Debug print
                if data.get('@type') == 'MusicRecording':
                    results.append(self._parse_track(data))
                elif data.get('@type') in ['MusicAlbum', 'MusicPlaylist']:
                     # If it's an album, check if the link is for a specific song (song ID in URL)
                     # Apple Music links: .../album/album-name/id?i=song-id
                     match_song_id = re.search(r'\?i=(\d+)', link)
                     target_song_id = match_song_id.group(1) if match_song_id else None
                     
                     tracks = data.get('tracks', [])
                     if not tracks and 'track' in data:
                         tracks = data['track']
                         
                     if isinstance(tracks, list):
                        found_target = False
                        for t in tracks:
                            # If we are looking for a specific song
                            # Note: JSON-LD might not expose the 'i' param ID directly in a simple way matchable to URL
                            # But usually the URL in 'url' field matches the song link
                            
                            is_target = False
                            if target_song_id:
                                if t.get('url') and target_song_id in t.get('url'):
                                    is_target = True
                            else:
                                is_target = True # Get all if no song ID specified? Or maybe limit?

                            if is_target:
                                results.append(self._parse_track(t, album_data=data))
                                found_target = True
                        
                        if target_song_id and not found_target:
                            # Maybe the JSON-LD structure is different or doesn't have the ID in URL
                            pass

            if not results:
                # Fallback: OpenGraph
                og_title = soup.find("meta", property="og:title")
                og_image = soup.find("meta", property="og:image")
                
                if og_title:
                    content = og_title["content"]
                    # Format usually "Song Name by Artist" or "Album by Artist"
                    if " by " in content:
                        parts = content.split(" by ")
                        name = parts[0]
                        artist = parts[1]
                    else:
                        name = content
                        artist = "Unknown"
                        
                    results.append({
                        "isrc": None, # Cannot get ISRC reliably from OG
                        "image": og_image["content"] if og_image else None,
                        "track": {
                            "name": name,
                            "album": { "name": name }, # Guessing album name is same as title if not found
                            "artists": [{"name": artist}],
                            "id": None
                        }
                    })

            return results if results else ["Error: No track data found on Apple Music page."]

        except Exception as e:
            print(f"Error parsing Apple Music: {e}")
            return [f"Error: {str(e)}"]

    def _parse_track(self, track_data, album_data=None):
        isrc = track_data.get('isrc')
        name = track_data.get('name')
        image = track_data.get('image')
        
        # Album name
        album_name = None
        if album_data:
            album_name = album_data.get('name')
        elif track_data.get('inAlbum'):
            if isinstance(track_data['inAlbum'], dict):
                album_name = track_data['inAlbum'].get('name')
            elif isinstance(track_data['inAlbum'], list): # unlikely but possible
                 album_name = track_data['inAlbum'][0].get('name')
        
        # Artist
        artist_name = "Unknown"
        by_artist = track_data.get('byArtist')
        if not by_artist and album_data:
            by_artist = album_data.get('byArtist')
            
        if by_artist:
            if isinstance(by_artist, list):
                artist_name = by_artist[0].get('name')
            elif isinstance(by_artist, dict):
                artist_name = by_artist.get('name')

        return {
            "isrc": isrc,
            "image": image,
            "track": {
                "name": name,
                "album": { "name": album_name if album_name else name },
                "artists": [{"name": artist_name}],
                "id": None
            }
        }
