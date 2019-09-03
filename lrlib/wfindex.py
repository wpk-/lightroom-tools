import enum

from sqlalchemy import Table, Column, Integer, ForeignKey, String, Index, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref


Base = declarative_base()


album_asset = Table(
    'album_asset_v2',
    Base.metadata,
    Column('docId', Integer, primary_key=True),
    Column('assetId', ForeignKey('assets.assetId'), nullable=False),
    Column('albumId', ForeignKey('albums.albumId'), nullable=False),
    Column('sortOrder', String(32)),
    Index('album_asset_v2_albumId', 'albumId'),
    Index('album_asset_v2_assetId', 'assetId'),
    Index('album_asset_v2_assetIdalbumId', 'assetId', 'albumId', unique=True),
    Index('album_asset_v2_hotmess', 'albumId', 'assetId', unique=True),
    Index('album_asset_v2_index', 'albumId', 'sortOrder', 'assetId', unique=True),
)


class AlbumType(enum.Enum):
    collection = 'collection'
    collection_set = 'collection_set'


class Album(Base):
    __tablename__ = 'albums'

    docId = Column(Integer, primary_key=True)
    albumId = Column(String(32), unique=True)
    name = Column(String)
    nameLC = Column(String)
    parentId = Column(String(32), ForeignKey(albumId), nullable=True)
    subtype = Column(Enum(AlbumType))

    assets = relationship('Asset', secondary=album_asset,
                          back_populates='albums')
    parent = relationship('Album', remote_side=albumId,
                          backref=backref('children', order_by=nameLC))

    def __repr__(self) -> str:
        return '<Album(docId=%r, albumId=%r, name=%r, ...)>' % (
            self.docId, self.albumId, self.name)


Index('albums_albumIddocId', Album.albumId, Album.docId)
Index('albums_name', Album.nameLC)
Index('albums_parent_id', Album.parentId)
Index('albums_subtype', Album.subtype)


class Asset(Base):
    __tablename__ = 'assets'

    docId = Column(Integer, primary_key=True)
    captureDate = Column(String)
    filename = Column(String)
    filenameLC = Column(String)
    assetId = Column(String(32), unique=True)

    albums = relationship('Album', secondary=album_asset,
                          back_populates='assets')

    def __repr__(self) -> str:
        return '<Asset(docId=%r, assetId=%r, filename=%r, ...)>' % (
            self.docId, self.assetId, self.filename)


Index('assets_assetIddocId', Asset.assetId, Asset.docId)
Index('assets_captureDatefilename', Asset.captureDate, Asset.filenameLC)


class Person(Base):
    __tablename__ = 'persons'

    docId = Column(Integer, primary_key=True)
    personId = Column(String(32), unique=True)
    name = Column(String)
    hidden = Column(Boolean)
    parentId = Column(String(32), ForeignKey(personId), nullable=True)

    parent = relationship('Person', remote_side=personId,
                          backref=backref('children', order_by=name))

    def __repr__(self) -> str:
        return '<Person(docId=%r, personId=%r, name=%r, ...)>' % (
            self.docId, self.personId, self.name)


Index(Person.personId)
Index(Person.personId, Person.parentId)
