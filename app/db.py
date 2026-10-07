import re
import logging
from urllib.parse import quote_plus
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, PyMongoError

from app.config import settings

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class MongoDBConnectionError(Exception):
    """Raised when connecting or communicating with MongoDB Atlas fails."""
    pass


def normalize_mongodb_uri(uri: str) -> str:
    """
    Normalizes MongoDB URI by URL-encoding special characters in username/password
    if they were provided unescaped (e.g. passwords containing #, @, <, >).
    """
    if not uri:
        return ""
    
    match = re.match(r"^(mongodb(?:\+srv)?://)([^:]+):(.+)@([^/]+)(/.*)?$", uri)
    if match:
        prefix, user, raw_password, host, rest = match.groups()
        if raw_password.startswith("<") and raw_password.endswith(">"):
            raw_password = raw_password[1:-1]
        
        encoded_user = quote_plus(user)
        encoded_pass = quote_plus(raw_password)
        rest = rest or ""
        return f"{prefix}{encoded_user}:{encoded_pass}@{host}{rest}"
    
    return uri


class MongoDBManager:
    """Manages the MongoDB Atlas client connection and database handles."""

    def __init__(
        self,
        uri: Optional[str] = None,
        db_name: Optional[str] = None,
        collection_name: Optional[str] = None,
        chunks_collection_name: Optional[str] = None
    ):
        raw_uri = uri or settings.mongodb_uri
        self._uri = normalize_mongodb_uri(raw_uri)
        self._db_name = db_name or settings.mongodb_db
        self._collection_name = collection_name or settings.mongodb_collection
        self._chunks_collection_name = chunks_collection_name or settings.mongodb_chunks_collection
        self._client: Optional[MongoClient] = None

    @property
    def client(self) -> MongoClient:
        if self._client is None:
            logger.info("Connecting to MongoDB Atlas")
            try:
                kwargs = {
                    "serverSelectionTimeoutMS": 3000,
                    "connectTimeoutMS": 3000
                }
                try:
                    import certifi
                    kwargs["tlsCAFile"] = certifi.where()
                except Exception:
                    pass

                self._client = MongoClient(
                    self._uri,
                    **kwargs
                )
            except Exception as e:
                logger.error("Failed to initialize MongoDB client")
                raise MongoDBConnectionError(f"Failed to initialize MongoDB client: {e}") from e
        return self._client

    @property
    def db(self) -> Database:
        return self.client[self._db_name]

    @property
    def documents_collection(self) -> Collection:
        return self.db[self._collection_name]

    @property
    def chunks_collection(self) -> Collection:
        return self.db[self._chunks_collection_name]

    @property
    def requirements_collection(self) -> Collection:
        return self.db[settings.mongodb_requirements_collection]

    @property
    def obligations_collection(self) -> Collection:
        return self.db[settings.mongodb_obligations_collection]

    @property
    def checklists_collection(self) -> Collection:
        return self.db[settings.mongodb_checklists_collection]

    @property
    def date_events_collection(self) -> Collection:
        return self.db[settings.mongodb_date_events_collection]

    @property
    def events_collection(self) -> Collection:
        return self.db[settings.mongodb_events_collection]

    @property
    def deadlines_collection(self) -> Collection:
        return self.db[settings.mongodb_deadlines_collection]

    @property
    def alerts_collection(self) -> Collection:
        return self.db[settings.mongodb_alerts_collection]

    @property
    def watchlists_collection(self) -> Collection:
        return self.db[settings.mongodb_watchlists_collection]

    @property
    def overlaps_collection(self) -> Collection:
        return self.db[settings.mongodb_overlaps_collection]

    @property
    def conflicts_collection(self) -> Collection:
        return self.db[settings.mongodb_conflicts_collection]

    def ping(self) -> bool:
        """Pings the MongoDB server to verify active connectivity."""
        try:
            self.client.admin.command("ping")
            logger.info("MongoDB connection successful")
            return True
        except (ConnectionFailure, PyMongoError, Exception) as e:
            logger.error(f"MongoDB ping failed: {e}")
            raise MongoDBConnectionError(f"Unable to connect to MongoDB Atlas: {e}") from e

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
            logger.info("MongoDB connection closed")


# Singleton instance
_db_manager = MongoDBManager()


def ping_mongodb() -> bool:
    """Check if MongoDB is reachable."""
    return _db_manager.ping()


def get_db() -> Database:
    """Returns the connected MongoDB database."""
    return _db_manager.db


def get_sync_db() -> Database:
    """Returns the connected MongoDB database (sync)."""
    return _db_manager.db


def get_collection(name: Optional[str] = None) -> Collection:
    """Returns a collection handle from the connected database."""
    if name:
        return _db_manager.db[name]
    return _db_manager.documents_collection


def get_chunks_collection() -> Collection:
    """Returns the chunks collection handle from the connected database."""
    return _db_manager.chunks_collection


def get_requirements_collection() -> Collection:
    """Returns the requirements collection handle from the connected database."""
    return _db_manager.requirements_collection


def get_obligations_collection() -> Collection:
    """Returns the obligations collection handle from the connected database."""
    return _db_manager.obligations_collection


def get_checklists_collection() -> Collection:
    """Returns the compliance checklists collection handle from the connected database."""
    return _db_manager.checklists_collection


def get_date_events_collection() -> Collection:
    """Returns the regulatory date events collection handle."""
    return _db_manager.date_events_collection


def get_events_collection() -> Collection:
    """Returns the regulatory events collection handle."""
    return _db_manager.events_collection


def get_deadlines_collection() -> Collection:
    """Returns the regulatory deadlines collection handle."""
    return _db_manager.deadlines_collection


def get_alerts_collection() -> Collection:
    """Returns the regulatory alerts collection handle."""
    return _db_manager.alerts_collection


def get_watchlists_collection() -> Collection:
    """Returns the watchlists collection handle."""
    return _db_manager.watchlists_collection


def get_overlaps_collection() -> Collection:
    """Returns the regulatory overlaps collection handle."""
    return _db_manager.overlaps_collection


def get_conflicts_collection() -> Collection:
    """Returns the regulatory conflicts collection handle."""
    return _db_manager.conflicts_collection


# Module-level lazy attribute access
def __getattr__(name: str):
    if name == "client":
        return _db_manager.client
    if name == "db":
        return _db_manager.db
    if name == "documents_collection":
        return _db_manager.documents_collection
    if name == "chunks_collection":
        return _db_manager.chunks_collection
    if name == "requirements_collection":
        return _db_manager.requirements_collection
    if name == "obligations_collection":
        return _db_manager.obligations_collection
    if name == "checklists_collection":
        return _db_manager.checklists_collection
    if name == "date_events_collection":
        return _db_manager.date_events_collection
    if name == "events_collection":
        return _db_manager.events_collection
    if name == "deadlines_collection":
        return _db_manager.deadlines_collection
    if name == "alerts_collection":
        return _db_manager.alerts_collection
    if name == "watchlists_collection":
        return _db_manager.watchlists_collection
    if name == "overlaps_collection":
        return _db_manager.overlaps_collection
    if name == "conflicts_collection":
        return _db_manager.conflicts_collection
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")