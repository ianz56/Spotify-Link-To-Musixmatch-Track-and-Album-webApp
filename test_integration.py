import asyncio
import json

import aiohttp
from dotenv import load_dotenv

from apple import AppleMusic
from mxm import MXM

load_dotenv()


async def test():
    am = AppleMusic()
    # Use the link provided by the user
    link = "https://music.apple.com/id/song/alamak/1842131302"
    print(f"Testing with link: {link}")

    # 1. Get data from Apple Music
    apple_data = am.get_apple_music_data(link)
    print("Apple Music Data:")
    print(json.dumps(apple_data, indent=2))

    if isinstance(apple_data, list) and isinstance(apple_data[0], str):
        print("Scraping failed.")
        return

    # 2. Pass to MXM
    async with aiohttp.ClientSession() as session:
        # Note: MXM class requires API keys. They should be in env or passed.
        # Assuming they are in env or handled by MXM default init logic.
        mxm = MXM(session=session)

        print("\nFetching match from Musixmatch...")
        mxmLinks = await mxm.Tracks_Data(apple_data)

        print("MXM Result:")
        print(json.dumps(mxmLinks, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test())
