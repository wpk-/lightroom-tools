# lightroom-tools
A set of tools to make Lightroom even more awesomer.

## Usage

Prerequisite: Export photos from Lightroom.

1. Start Lightroom
2. Select all folders and albums.
3. Select all the shown photos and export (File > Save to...).
4. Make sure to export to JPG.

Then: Organise the flat photo folder into albums.

```sh
make_albums.py <path>
```

where `<path>` is where you exported your photos to. Now your photos are nicely
organised into folders that follow the structure of your photo library.

That's it. You're done.

#### Advanced

OK, if you want to export only one album or folder, you can do that too. Then
run:
 
```sh
make_albums.py list albums
```

This will print your Lightroom album hierarchy. Find the exported album/folder
and copy its album ID. Then

```sh
make_albums.py <path> -r <album ID>
```

## Lightroom info

### Kinds of stored photos

***original***: Raw photo or JPG whatever you uploaded. Changes to the photo
    are stored in XMP, which cannot be read by external programs. So other
    image editors and viewers will show the original while Adobe programs will
    show the edited photo.

***proxy***: A reduced version of the original, stored in RAW format but
    without file extension. With the changes stored in XMP, like the originals,
    only Adobe programs will show the edited version. The proxy file path can
    be found in *Managed Catalog.wfindex/assetPathsAndInfo*.

***preview***: Small 320px or 640px photos with all edits applied. Their path
    can be found in *previews.db/RenditionPath*.

***export***: Created by selecting photos and then *File > Save to...* The user
    selects the format (original or JPG) and size (original, small or custom).
    Exported files are all saved into the same folder. To organise them by the
    Lightroom structure of albums, use `into_folders.py`.
