from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from lrlib import utils, wfindex

DEBUG = True


Session = sessionmaker()


class Terminal:
    @staticmethod
    def select_item(items: List[str], prompt='Select') -> str:
        for i, catalog in enumerate(items, start=1):
            print('  [{:d}] {:s}'.format(i, catalog))
        choice = input('{:s} [1]: '.format(prompt))
        choice = int(choice or '1') - 1
        return items[choice]


class Base(Terminal):
    def __init__(self, catalog_path: str) -> None:
        self.catalog_path = catalog_path
        self.debug = DEBUG
        self.session = None

    def __enter__(self) -> 'Base':
        """Context manager for the database session.
        """
        sources = [
            (wfindex.Base, 'sqlite:///{:s}/Managed Catalog.wfindex'),
        ]

        binds = {base: create_engine(db_file.format(self.catalog_path),
                                     echo=self.debug)
                 for base, db_file in sources}
        # https://github.com/sqlalchemy/sqlalchemy/issues/4829
        binds.update({table: engine for base, engine in binds.items()
                      for table in base.metadata.tables.values()})
        Session.configure(binds=binds)

        self.session = Session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        """Closes the database session.
        """
        self.session.close()
        return None

    @classmethod
    def select_catalog(cls) -> str:
        """Queries the user to select the folder containing the catalog.

        Returns:
            The selected catalog path.
        """
        return cls.select_item(utils.discover_catalogs(),
                               'Select your catalog')
