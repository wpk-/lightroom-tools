from collections import defaultdict
from itertools import count
from os.path import join as joinpath, splitext
from typing import Callable, Dict

from lrlib.wfindex import Asset


# https://helpx.adobe.com/lightroom-classic/kb/video-support-lightroom.html
VIDEO_EXTS = {'.3gp', '.3gpp', '.avi', '.m2t', '.m2ts', '.m4v', '.mov', '.mpg',
              '.mp2', '.mp4', '.mpeg', '.mts', '.wmv'}


def map_ext(ext: str) -> str:
    """Guess the file extension of exported assets.

    All photos are exported to .jpg, but not videos.

    Args:
        ext: Original asset file extension.

    Returns:
        The expected file extension after exporting from Lightroom.
    """
    return ext if ext.lower() in VIDEO_EXTS else '.jpg'


class AssetNamer(Callable[[Asset], str]):
    """A callable class to provide non-conflicting file names for assets.

    Attributes:
        folder: The base folder, prepended to all generated file names.
    """
    def __init__(self, folder: str) -> None:
        """Creates the asset namer.

        Args:
            folder: Base folder to be prepended to file names.
        """
        self.folder = folder

    def __call__(self, asset: Asset) -> str:
        """Returns the non-conflicting file name for a given asset.

        Args:
            asset: Asset for which to find a suitable file name.

        Returns:
            The non-conflicting file name, which is based on the asset's
            original file name, but possibly extended to avoid conflicts
            with other identically named assets.
        """
        pass


class IndexedNamer(AssetNamer):
    """Produces unique file names for assets by prefixing a counter.

    The output pattern is `<folder>/<index>.<filename>.jpg`.

    Attributes:
        folder: The base folder, prepended to all generated file names.
    """

    def __init__(self, folder: str) -> None:
        """Creates the asset namer.

        Args:
            folder: Base folder to be prepended to file names.
        """
        super().__init__(folder)
        self.index = count(start=1)

    def __call__(self, asset: Asset) -> str:
        """Returns the non-conflicting file name for a given asset.

        Args:
            asset: Asset for which to find a suitable file name.

        Returns:
            The non-conflicting file name, formed as
            `<self.folder>/<index>.<asset.filename>.jpg` where index is
            increased by 1 for every call to this function.
        """
        base_name, ext = splitext(str(asset.filename))
        return joinpath(self.folder, '{:d}.{:s}{:s}'.format(next(self.index),
                                                            base_name,
                                                            map_ext(ext)))


class NaturalNamer(AssetNamer):
    """Produces unique file names by appending a counter starting from 2.

    The output pattern is `<folder>/<filename>.jpg` for the first file
    and `<folder>/<filename>-<index>.jpg` for subsequent assets with the
    same original file name. The index starts counting from 2.

    Attributes:
        folder: The base folder, prepended to all generated file names.
    """
    def __init__(self, folder: str) -> None:
        """Creates the asset namer.

        Args:
            folder:
        """
        super().__init__(folder)
        self.index: Dict[str, count] = defaultdict(lambda: count(start=1))
        self.registry: Dict[str, str] = {}

    def __call__(self, asset: Asset) -> str:
        """Returns the non-conflicting file name for a given asset.

        Args:
            asset: Asset for which to find a suitable file name.

        Returns:
            The non-conflicting file name, formed as
            `<self.folder>/<asset.filename>-<index>.jpg`. The index is
            only appended starting at the second occurrence of a file
            with the same name. So the first is simply named:
            `<self.folder>/<asset.filename>.jpg`.
        """
        try:
            filename = self.registry[asset.assetId]
        except KeyError:
            filename = self.registry[asset.assetId] =\
                       self._make_filename(asset.filename)
        return filename

    def _make_filename(self, filename: str) -> str:
        """Avoids naming conflicts between matching file names.

        Args:
            filename: Original asset file name.

        Returns:
            Mapped file name that avoids conflict with other assets of
            the same original file name.
        """
        base_name, ext = splitext(filename)
        new_ext = map_ext(ext)
        ix = next(self.index[filename])
        if ix == 1:
            filename = base_name + new_ext
        else:
            filename = '{:s}-{:d}.{:s}'.format(base_name, ix, new_ext)
        return joinpath(self.folder, filename)
