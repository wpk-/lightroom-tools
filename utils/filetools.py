from concurrent.futures import ThreadPoolExecutor, as_completed
from genericpath import isfile
from logging import getLogger
from os import makedirs, remove
from os.path import split as splitpath
from shutil import copy2, move as movefile
from typing import Collection, Dict, List

logger = getLogger(__name__)


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
                makedirs(splitpath(dst)[0], exist_ok=True)
                move_fcn(src, dst)
            else:
                # The source file doesn't exist.
                raise err

    if len(dsts) > 1:
        remove(src)


def move_many_to_many(file_mapping: Dict[str, Collection[str]]) -> List[str]:
    """Apply `move_to_many` to all items in the file mapping.

    Args:
        file_mapping: A dictionary of file mappings from source file
            to a collection of one or more target file names / folders.
            `move_to_many` is (asynchronously) called for each item in
            the dictionary.

    Returns:
        A list of failed (source) file names. The move/copy failed with
        a `FileNotFoundError` because the source file couldn't be found.
    """
    failed = []

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(move_to_many, move_from, move_to)
                   for move_from, move_to in file_mapping.items()}

        for future in as_completed(futures):
            try:
                future.result()
            except FileNotFoundError as err:
                failed.append(err.filename)

    return failed
