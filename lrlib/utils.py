from os import getenv, listdir
from os.path import isfile, join as joinpath
from typing import List


def discover_catalogs() -> List[str]:
    """Discover all catalog folders.

    Returns:
        A list of discovered catalog folders.
    """
    # If you are running Lightroom on a non-Windows platform, please
    # let me know where the file Managed Catalog.wfindex is.
    req = 'Managed Catalog.wfindex'
    base = joinpath(getenv('LOCALAPPDATA'), 'Adobe', 'Lightroom CC', 'Data')
    guesses = (joinpath(base, fld) for fld in listdir(base))
    return [path for path in guesses if isfile(joinpath(path, req))]
