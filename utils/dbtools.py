from collections import defaultdict
from os import getenv, listdir
from os.path import isfile, join as joinpath
from typing import List, Optional, Union

from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import Query, aliased
from sqlalchemy.orm.attributes import (set_committed_value,
                                       InstrumentedAttribute)


def adjacency_list(session,
                   model,
                   relationship: Optional[InstrumentedAttribute] = None,
                   root_value: Union[str, None] = None):
    """Returns a query for all records in an adjacency list.

    Args:
        session: The SQLAlchemy database session.
        model: The model from which to retrieve the adjacency list.
        relationship: The parent/child relationship that describes
            both fields (columns). Default: `<model>.parent`
        root_value: Parent property's value at the root nodes.
            Default is None, which commonly retrieves the whole
            structure.

    Returns:
        A Query that retrieves all model objects using a CTE.
    """
    if relationship is None:
        relationship = model.parent

    parent_field = relationship.expression.right.name
    child_field = relationship.expression.left.name

    hierarchy = (session.query(model)
                 .filter(getattr(model, parent_field) == root_value)
                 .cte(name='hierarchy', recursive=True))

    h = aliased(hierarchy, name='h')
    m = aliased(model, name='m')
    hierarchy = hierarchy.union_all(
        session.query(m)
        .filter(getattr(m, parent_field) == getattr(h.c, child_field))
    )

    return hierarchy


def fetch_as_tree(query: Query,
                  relationship: Optional[InstrumentedAttribute] = None,
                  root_value: Union[str, None] = None,
                  ) -> List[DeclarativeMeta]:
    """Builds the full tree for the given table (adjacency list).

    This method is efficient in the sense that it issues only one SELECT
    query to the database.

    Args:
        query: A query that selects all relevant model records, that
            is, all records that make up the adjacency list. For
            example: `session.query(Album).order_by(Album.nameLC)`.
        relationship: The parent/child relationship that describes
            both fields (columns). For example: `Album.parent`
            If not set, one record is fetched from the query to read
            its `parent` property.
        root_value: Parent property's value at the root nodes.
            Default is None, which commonly retrieves the whole
            structure.

    Returns:
        A list of root nodes with child nodes (the tree) pre-fetched
        recursively.
    """
    if relationship is None:
        # Fetch one record to discover the parent relationship.
        relationship = next(iter(query)).__class__.parent

    parent_field = relationship.expression.right.name
    child_field = relationship.expression.left.name
    back_populates = relationship.property.back_populates

    nodes = query.all()

    children = defaultdict(list)
    for node in nodes:
        children[getattr(node, parent_field)].append(node)

    for node in nodes:
        set_committed_value(node, back_populates,
                            children[getattr(node, child_field)])

    return children[root_value]


def user_catalogs() -> List[str]:
    """Searches for catalog folders (contain databases and files).

    Args:
        path: Path to the folder containing Managed Catalog.wfindex
            and other library files. If set, this value is returned
            immediately. Otherwise, the function will try to locate
            it and possibly ask the user to pick from a list.

    Returns:
        A list of discovered catalog folders. Usually one, but can be
        zero or more than one.
    """
    req = 'Managed Catalog.wfindex'

    # If you are running Lightroom on a non-Windows platform, please
    # let me know where the file Managed Catalog.wfindex is.
    base = joinpath(getenv('LOCALAPPDATA'),
                    'Adobe', 'Lightroom CC', 'Data')
    guesses = (joinpath(base, fld) for fld in listdir(base))
    return [path for path in guesses if isfile(joinpath(path, req))]
