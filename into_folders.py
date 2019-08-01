#!/usr/bin/env python3
"""
Organise the exported photos into folders matching your Lightroom albums.

Open Lightroom, select all your folders and albums. Go to the photos and
press Ctrl+A to select them all, then click File > Save to... to save
JPGs of all your photos to a given folder. Note that all files are
simply dumped into this one folder. No albums. Now use this script to
re-organise the photos into folders matching your Lightroom library.

Usage:
    into_folders.py FOLDER [--indexed | --natural] [-l FILE] [-r ALBUM]
    into_folders.py list albums [-l FILE]
    into_folders.py -h | --help
    into_folders.py --version

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
    -l FILE --library=FILE  Path to the Lightroom library
                            (Managed Catalog.wfindex).
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
# TODO: Support non-Windows platforms. Need users. (`ui_select_catalog`)
import logging

from collections import defaultdict
from itertools import count
from multiprocessing import cpu_count, Pool
from os import getenv, listdir, makedirs, remove
from os.path import isdir, isfile, join as joinpath, splitext, split as splitpath
from shutil import copy2, move as movefile
from typing import Any, Callable, Collection, Dict, Iterable, Iterator, Optional, Tuple, Union

from docopt import docopt
from peewee import CharField, Field, ForeignKeyField, IntegerField, Model, ModelSelect, SqliteDatabase, DateTimeField

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
logger.addHandler(sh)


# https://helpx.adobe.com/lightroom-classic/kb/video-support-lightroom.html
VIDEO_EXTS = {'.3gp', '.3gpp', '.avi', '.m2t', '.m2ts', '.m4v', '.mov', '.mpg',
              '.mp2', '.mp4', '.mpeg', '.mts', '.wmv'}


db = SqliteDatabase(None)


class BaseModel(Model):
    class Meta:
        database = db


class Album(BaseModel):
    docId = IntegerField(primary_key=True)
    albumId = CharField(32)
    name = CharField(1024)
    parent = ForeignKeyField('self', field=albumId, backref='children',
                             column_name='parentId', null=True)

    class Meta:
        table_name = 'albums'


class Asset(BaseModel):
    docId = IntegerField(primary_key=True)
    captureDate = DateTimeField()
    filename = CharField(1024)
    filenameLC = CharField(1024)
    assetId = CharField(32)

    class Meta:
        table_name = 'assets'


class AlbumAsset(BaseModel):
    docId = IntegerField(primary_key=True)
    asset = ForeignKeyField(Asset, field=Asset.assetId, backref='to_album',
                            column_name='assetId')
    album = ForeignKeyField(Album, field=Album.albumId, backref='to_asset',
                            column_name='albumId')
    sortOrder = CharField(32)

    class Meta:
        table_name = 'album_asset_v2'


def iter_assets(album: Album) -> Iterable[Asset]:
    """Returns a query for the ordered assets in album.

    Args:
        album: An album with zero or more assets.

    Returns:
        The assets (as a ModelSelect query).
    """
    return (Asset
            .select()
            .join(AlbumAsset)
            .where(AlbumAsset.album == album.albumId)
            .order_by(AlbumAsset.sortOrder,
                      Asset.captureDate, Asset.filenameLC))


def iter_albums(root: ModelSelect = None, order: Field = None
                ) -> Iterator[Tuple[Album, ...]]:
    """Depth-first iterator over the album hierarchy.

    Yields:
        A tuple `path` of Album instances. The tuple describes the full
        path, with the root folder in `path[0]` and the leaf album in
        `path[-1]`.
    """
    if root is None:
        root = Album.select().where(Album.parent.is_null())
    if order is None:
        order = root.model.name

    stack = list((album,) for album in root.order_by(-order))

    while True:
        try:
            path = stack.pop(-1)
        except IndexError:
            return

        yield path

        # Depth-first: append new items to the top of the stack.
        stack.extend(path + (album,)
                     for album in path[-1].children.order_by(-order))


def indexed_namer(base_path: str = '') -> Callable[[Asset], str]:
    """Returns a function that produces unique file names for assets.

    Args:
        base_path: Path for the generated file names. Can be empty.

    Returns:
        A function `[Asset] -> str`. Given an asset it will return a
        unique filename: `<base_path>/<index>.<filename>.jpg`.
    """
    def namer(asset: Asset) -> str:
        base_name, ext = splitext(str(asset.filename))
        new_ext = map_ext(ext)
        return joinpath(base_path, '{:d}.{:s}{:s}'.format(next(ix),
                                                          base_name, new_ext))

    ix = count(start=1)
    return namer


def natural_namer(base_path: str = '') -> Callable[[Asset], str]:
    """Returns a function that produces unique file names for assets.

    Args:
        base_path: Path for the generated file names. Can be empty.

    Returns:
        A function `[Asset] -> str`. Given an asset, it will return a
        unique filename: `<base_path>/<filename>-<counter>.jpg`.

        The counter is only appended starting at the second occurrence
        of a file with the same name. So the first is simply named:
        '<base_path>/<filename>.jpg'.
    """
    def namer(asset: Asset) -> str:
        asset_id = str(asset.assetId)
        filename_lc = str(asset.filenameLC)

        try:
            return joinpath(base_path, registry[filename_lc][asset_id])
        except KeyError:
            pass

        base_name, ext = splitext(str(asset.filename))
        new_ext = map_ext(ext)
        try:
            info = registry[filename_lc]
        except KeyError:
            info = registry[filename_lc] = {asset_id: base_name + new_ext}
        else:
            info[asset_id] = '{:s}-{:d}{:s}'.format(base_name,
                                                    len(info) + 1, new_ext)

        return joinpath(base_path, info[asset_id])

    # filenameLC -> (assetId -> unique filename)
    registry: Dict[str, Dict[str, str]] = {}
    return namer


def map_ext(ext: str) -> str:
    """Guess the file extension of exported assets.

    All photos are exported to .jpg, but not videos.

    Args:
        ext: Original asset file extension.

    Returns:
        The expected file extension after exporting from Lightroom.
    """
    return ext if ext.lower() in VIDEO_EXTS else '.jpg'


def move_to_many(src: str, dsts: Collection[str]) -> None:
    """Move one file to one or more destinations.

    Args:
        src: Source path, a string.
        dsts: Destination paths, a collection of one or more strings.
            For single destinations, `shutil.move` is used. For multiple
            destinations, `shutil.copy2` is used and the source file is
            deleted after all copies have been successful.
    """
    if len(dsts) > 1:
        move_fcn = copy2
    else:
        move_fcn = movefile

    for dst in dsts:
        logger.debug('"%s" -> "%s"', src, dst)
        try:
            move_fcn(src, dst)
        except FileNotFoundError as err:
            if isfile(src):
                # The target directory doesn't exist.
                makedirs(splitpath(dst)[0])
                move_fcn(src, dst)
            else:
                # The source file doesn't exist.
                raise err

    if len(dsts) > 1:
        remove(src)


def move_to_many_proc(args: Tuple[str, Collection[str]]) -> Union[None, str]:
    """Wrapper for move_to_many to be run in a multiprocessing pool.

    It invokes `move_to_many(*args)`, catching and returning `src` if it
    fails. The pool can then iterate over the results and pick up all
    failed files.

    Args:
        args: A tuple `(src, dsts)` as expected by `move_to_many`. `src`
            is the source file name. `dsts` is a collection of target
            file names.

    Returns:
        `None` if `move_to_many` was successful. `src` otherwise.
    """
    try:
        return move_to_many(*args)
    except FileNotFoundError:
        return args[0]


def ui_select_catalog(path: Optional[str] = None) -> str:
    """Returns the path to the catalog, possibly guided by the user.

    Args:
        path: Path to the catalog file. If set, this value is returned
            immediately. Otherwise, the function will try to locate the
            catalog. If multiple catalogs are found, the user is
            presented with the choices and the one selected is returned.

    Returns:
        Full path to the Lightroom catalog file (Managed Catalog.wfindex).
    """
    name = 'Managed Catalog.wfindex'

    if path is None:
        # If you are running Lightroom on a non-Windows platform, please
        # let me know where the file Managed Catalog.wfindex is.
        base = joinpath(getenv('LOCALAPPDATA'),
                        'Adobe', 'Lightroom CC', 'Data')
        guesses = (joinpath(base, fld, name) for fld in listdir(base))
        catalogs = [path for path in guesses if isfile(path)]

        if len(catalogs) == 1:
            return catalogs[0]
        elif len(catalogs) == 0:
            raise FileNotFoundError
        else:
            print('Found {:d} catalogs:'.format(len(catalogs)))
            for i, path in enumerate(catalogs, start=1):
                print('{:5d} {:s}'.format(i, path))
            n = input('Select your catalog: ')
            return catalogs[int(n) - 1]

    elif isdir(path):
        return joinpath(path, name)

    return path


def ui_select_root_album(album_id: Optional[str] = None) -> ModelSelect:
    """Select the exported album.

    Args:
        album_id: If specified, this album will serve as the root. The
            special keyword `all` can be used to select all albums whose
            parent ID is `NULL`. If not specified, the user is asked to
            select from a list.

    Returns:
        A query for the basis of the album hierarchy that is to be
        re-organised. When the user picks a specific album or folder,
        the returned query will select precisely that Album instance.
        Use `iter_albums` to recurse through this branch.
    """
    if album_id is None:
        album_ids = ['all']

        print('Folders and albums:')
        print('{:5d}. (all)'.format(0))

        for i, path in enumerate(iter_albums(), start=1):
            album = path[-1]
            album_ids.append(album.albumId)

            print('{:5d}. {:s}{:s}'.format(i, '  ' * len(path), album.name))

        n = input('Which album/folder did you export from Lightroom?'
                  ' (Default: 0 = all): ')
        album_id = album_ids[int(n or '0')]

    album_filter = (Album.parent.is_null()
                    if album_id == 'all' else Album.albumId == album_id)

    return Album.select().where(album_filter)


class App:
    """The App manages context for the DB and provides programs.
    """
    def __init__(self, catalog: Union[str, None], options: Dict[str, Any]
                 ) -> None:
        self.catalog = ui_select_catalog(catalog)
        logger.info('Using catalog file: "%s"', self.catalog)

        self.output_namer: Callable[[str], Callable[[Asset], str]] = \
            options.get('output_namer', indexed_namer)

    def __enter__(self) -> 'App':
        """Connects to the database."""
        db.init(self.catalog, pragmas={'foreign_keys': 1})
        db.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Disconnects from the database."""
        db.close()

    @staticmethod
    def list_albums() -> None:
        """Prints all albums and their ID."""
        for path in iter_albums():
            album = path[-1]
            indent = '  ' * len(path)
            print('{:s}{:s}{:s}'.format(album.albumId, indent, album.name))

    def organise(self, folder: str, root: Optional[str] = None) -> None:
        """Organise exported files into their album/folder hierarchy.

        Args:
            folder: The folder to which Lightroom photos were exported.
            root: The album or albums that were exported. This is
                specified as an album ID, or the special keyword `all`
                if all albums were exported. If omitted, the user is
                asked to select from the list.

                Note: The output folder structure will be relative to
                this root. In other words, names of parent albums are
                not included.
        """
        albums = iter_albums(ui_select_root_album(root))

        # Find all pairs of file names, source -> destination.
        print('Prepare operation...')

        filename_mapping = defaultdict(list)

        input_file = natural_namer(folder)
        output_namer = self.output_namer

        for path in albums:
            fld_out = joinpath(folder, *(album.name for album in path))
            output_file = output_namer(fld_out)

            for asset in iter_assets(path[-1]):
                filename_mapping[input_file(asset)].append(output_file(asset))

        # Rename the files. Runs in parallel.
        print('Move files into album folders...')

        pool = Pool()
        chunk_size = max(1, len(filename_mapping) // cpu_count())
        res = pool.imap_unordered(move_to_many_proc, filename_mapping.items(),
                                  chunksize=chunk_size)

        total = sum(map(len, filename_mapping.values()))
        failed = 0

        for src in filter(None, res):
            logger.warning('File not found: "%s" (to be renamed to %r)',
                           src, filename_mapping[src])
            failed += len(filename_mapping[src])

        print('Done. Moved {:d}/{:d} files ({:d} failed).'.format(
            total - failed, total, failed))


def main(args: Dict[str, Union[str, bool]]) -> None:
    """Run the program according to the specified command line options.

    Args:
        args: A dictionary of command line options as returned by
        `docopt`. See the docstring for all available options.
    """
    options = {
        'output_namer': indexed_namer,
    }

    if args['--natural']:
        options['output_namer'] = natural_namer

    with App(args['--library'], options) as app:

        if args['list'] and args['albums']:
            app.list_albums()

        else:
            app.organise(args['FOLDER'], args['--root'])


if __name__ == '__main__':
    arguments = docopt(__doc__, version='Into Folders 1.0')
    main(arguments)
