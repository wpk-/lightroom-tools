#!/usr/bin/env python3
"""
Move exported photos into album folders.

Open Lightroom, select all your folders and albums. Go to the photos and
press Ctrl+A to select them all, then click File > Save to... to save
JPGs of all your photos to a given folder. Note that all files are
simply dumped into this one folder. No albums. Now use this script to
re-organise the photos into folders matching your Lightroom library.

Usage:
    make_albums.py FOLDER [--indexed | --natural] [-l PATH] [-r ALBUM]
    make_albums.py list albums [-l PATH]
    make_albums.py -h | --help
    make_albums.py --version

Options:
    -h --help               Show this screen.
    --version               Show version.
    --indexed               Ouput files are numbered: 1.aaa.jpg,
                            2.bbb.jpg, etc. This preserves the original
                            order of photos in the Lightroom album and
                            is the default.
    --natural               Original file names are maintained, except
                            to avoid name collisions, in which case a
                            counter is appended: aaa.jpg, bbb.jpg,
                            aaa-2.jpg, etc. Although this preserves file
                            names, it does not maintain the order of
                            photos in the albums.
    -l PATH --library=PATH  Path to the folder containing the Lightroom
                            library (Managed Catalog.wfindex).
    -r ALBUM --root=ALBUM   Specify the folder / album that you exported
                            from your library (via its album ID: run
                            "list albums" to get those), or specify
                            "all" to organise all.
                            If the selected album contains more albums
                            under it, they are all included, but parent
                            albums are not.

Copyright (c) 2019 Paul Koppen
Licenced under the MIT License
https://opensource.org/licenses/MIT
"""
# TODO: Support non-Windows platforms. Need users.
from collections import defaultdict
from operator import attrgetter
from os.path import join as joinpath
from typing import (Any, Dict, Optional, Type, Union)

from docopt import docopt

from lrlib import app
from lrlib.wfindex import Asset, Album, album_asset
from utils.naming import AssetNamer, IndexedNamer, NaturalNamer
from utils import dbtools, filetools


class App(app.Base):
    """The App provides programs.
    """

    def __init__(self, output_namer: Type[AssetNamer], **kwargs) -> None:
        """Creates an App.

        Args:
            output_namer: An AssetNamer to specify a file name
                convention for assets after they have been moved into
                folders.
            **kwargs: Other keyword arguments. Specifically:
                `catalog_path`: The path to the catalog folder.
        """
        super().__init__(**kwargs)
        self.output_namer = output_namer

    @classmethod
    def factory(cls, kwargs: Dict[str, Any]) -> 'App':
        """Creates an App from a dict of arguments.

        Args:
            kwargs: Keyword arguments to create the app.
                `catalog_path`: Optional. The path to the catalog folder.
                `output_namer`: Optional. An AssetNamer (subclass)
                    instance to define how moved files are (re)named.

        Returns:
            The App instance.
        """
        kwargs['catalog_path'] = kwargs.get('catalog_path', None) or \
                                 cls.select_catalog()
        kwargs['output_namer'] = kwargs.get('output_namer', IndexedNamer)
        return cls(**kwargs)

    def print_album_tree(self) -> None:
        """Prints all albums and their album IDs.
        """
        def print_album_with_id(album: Album, indent: str) -> None:
            print('{:s}{:s} {:s}'.format(album.albumId, indent, album.name))
            for a in album.children:
                print_album_with_id(a, indent + '  ')

        albums = self.session.query(Album).order_by(Album.nameLC)
        for root_album in dbtools.fetch_as_tree(albums, Album.parent):
            print_album_with_id(root_album, '')

    def organise(self, folder: str, root: Optional[str] = None) -> None:
        """Organise exported files into their album/folder hierarchy.

        Args:
            folder: The folder to which Lightroom photos were exported.
            root: The album or albums that were exported. This is
                specified as an album ID, or the special keyword `all`
                if all albums were exported. If omitted, the user is
                asked to select from the list.

        Notes:
            The output folder structure will be relative to the root. In
             other words, names of parent albums are not included.
        """
        parent_prop = Album.parent

        albums = dbtools.adjacency_list(self.session, Album, parent_prop, root)
        albums = self.session.query(albums).all()
        album_ids = set(map(attrgetter('albumId'), albums))

        album_path = {root: self.output_namer(folder)}
        for album in albums:
            path = joinpath(album_path[album.parentId].folder, album.name)
            album_path[album.albumId] = self.output_namer(path)

        # Find all pairs of file names, source -> destination.
        filename_mapping = defaultdict(list)
        input_path = NaturalNamer(folder)

        asset_query = (self.session
                       .query(Asset.assetId, Asset.filename, album_asset.c.albumId)
                       .join(album_asset)
                       .filter(album_asset.c.albumId.in_(album_ids))
                       .order_by(Asset.captureDate, Asset.filenameLC))

        for row in asset_query:
            filename_mapping[input_path(row)].append(
                    album_path[row.albumId](row))

        # Renaming files runs in parallel.
        print('Move files into album folders...')

        for failed in filetools.move_many_to_many(filename_mapping):
            print(f'File not found: {failed!r}')

        print('done.')


def main(args: Dict[str, Union[str, bool]]) -> None:
    """Run the program according to the specified command line options.

    Args:
        args: A dictionary of command line options as returned by
        `docopt`. See the docstring for all available options.
    """
    options = {
        'catalog_path': args['--library'],
        'output_namer': IndexedNamer,
    }

    if args['--natural']:
        options['output_namer'] = NaturalNamer

    with App.factory(options) as app:

        if args['list'] and args['albums']:
            app.print_album_tree()

        else:
            app.organise(args['FOLDER'], args['--root'])


if __name__ == '__main__':
    arguments = docopt(__doc__, version='Into Folders 1.0')
    main(arguments)
