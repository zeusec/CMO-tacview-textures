# CMO Tacview Textures Downloader

A tool to download Sentinel-2 texture tiles and SRTM30 elevation data for use with [Tacview](https://www.tacview.net/) and [Command: Modern Operations](https://command.matrixgames.com/). This downloads ALL textures and terrain data, totaling ~26 GB of space. If you stop, it will resume where you left off on the next start assuming downloaded files are still present. Once finished you must move the files yourself to proper location.

>
> — [Matrix Games Downloads Page](https://command.matrixgames.com/?page_id=1876)

This tool downloads from WarfareSims servers. Be respectful of bandwidth limits. If you receive a "bandwidth exceeded" message, try again later. This is intentionally throttled to not hammer the providers servers, while you can modify the parameters I recommend leaving the defaults.

## Features

- **Resumable Downloads**: Skips files that already exist locally
- **Rate Limiting**: Configurable delay between requests
- **Retry Logic**: Automatic retries with exponential backoff on network errors
- **Progress Tracking**: Progress bar with estimated time left
- **Graceful Interruption**: Press `Ctrl+C` to stop cleanly, and start again to resume later

## Requirements

- Python 3.7+
- `requests` library
- **Tacview v1.8.3+** (required for WebP texture format)
- **Tacview v1.8.1+** (minimum for SRTM30 elevation data)
- ~26 GB of free space for textures + terrain data

## Installation

```bash
git clone https://github.com/zeusec/CMO-tacview-textures.git
cd CMO-tacview-textures
pip install requests
```

## Usage

Basic usage (downloads both textures and elevation data):

```bash
python main.py
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `-w`, `--workers` | 4 | Max concurrent downloads |
| `--delay` | 0.5 | Delay in seconds between requests per worker |
| `--retries` | 3 | Number of retry attempts per file on error |
| `--textures-dir` | `textures` | Destination directory for texture files |
| `--elevation-dir` | `elevation` | Destination directory for elevation files |


## Installing Downloaded Files in CMO

After downloading, copy the files to the appropriate Tacview directories:

| Asset Type | Source | Destination |
|------------|--------|-------------|
| Textures (`.webp`) | `./textures/` | `[CMO]\Resources\Tacview\Data\Terrain\Textures` |
| Elevation (`.srtm`) | `./elevation/` | `[CMO]\Resources\Tacview\Data\Terrain\SRTM30` |

Replace `[CMO]` with your Command: Modern Operations installation directory.

## Data Sources

- **Textures**: Sentinel-2 imagery tiles in WebP format
- **Elevation**: SRTM30Plus bathymetry/terrain data

## License Notice

> Usage of these textures is permitted **only for use with CMO**. Do not use them in consort with any other product.
>
> — [Matrix Games Downloads Page](https://command.matrixgames.com/?page_id=1876)

## Credits

- Texture and elevation data provided by [WarfareSims/Matrix Games](https://command.matrixgames.com/?page_id=1876)
- Tacview by [Raia Software Inc](https://www.tacview.net/)
