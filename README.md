# Spotify-Link-To-Musixmatch-Track-link-and-Album-link-webApp
<p align="center">
    A Web Application that connects Musixmatch with Spotify
    <br />

## Domains
- [Vercel](https://spotify-link-to-musixmatch-track-and-album-w-ian-perds-projects.vercel.app/)
- [Domain](https://spotmxm.journey.web.id/)

## Built With
- ![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
- ![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)
- ![Jinja](https://img.shields.io/badge/jinja-white.svg?style=for-the-badge&logo=jinja&logoColor=black)
- ![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
- ![Babel](https://img.shields.io/badge/babel-%23F0772B.svg?style=for-the-badge&logo=babel&logoColor=white)

## Features 
- Get links to Musixmatch from Spotify Link
- Get links to Musixmatch from Apple Music Link
- Get the Musixmatch track page from the ISRC code
- Get ISRC codes and available markets for Spotify tracks or Album
- Get the Spotify link from the ISRC code
- Get Connected Sources for a Musixmatch Track or Album link
- Check If 2 tracks share the same page in Musixmatch can be split or not
- Ability to use private API for Musixmatch
- Handle normal Spotify links and the short one

## Development

### Prerequisites
Install the development dependencies:
```bash
pip install -r requirements-dev.txt
```

### Code Quality
This project uses `ruff` for linting/formatting and `pre-commit` hooks.
To install the hooks:
```bash
pre-commit install
```
To run manually:
```bash
pre-commit run --all-files
```

### Testing
To run the test suite:
```bash
python -m pytest tests/
```
