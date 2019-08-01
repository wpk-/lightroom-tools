# lightroom-tools
A set of tools to make Lightroom even more awesomer.

## Usage:

Prerequisite: Export photos from Lightroom.

1. Start Lightroom
2. Select an album or a folder.
3. Select all photos inside it and export (File > Save to...).
4. Make sure to export to JPG.

Then: Organise the flat photo folder into albums.

```sh
into_folders.py <path>
```

where `<path>` is where you exported your photos to. You will be asked to select which folder / album you exported.

Now your photos are nicely organised into folders that follow the structure of your photo library in Lightroom.

That's all.
