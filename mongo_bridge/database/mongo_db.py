import frappe
import time
from datetime import datetime
from frappe import _dict
from urllib.parse import quote_plus


class MongoDatabase:

    def __init__(self):
        self._client = None
        self._db = None
        self._pymongo = None
        self.logger = frappe.logger("mongodb_bridge")

    def _get_driver(self):
        if self._pymongo:
            return self._pymongo
        try:
            import pymongo
            self._pymongo = pymongo
            return pymongo
        except ImportError:
            raise frappe.ValidationError(
                "MongoDB driver missing.\n\n"
                "Install with:  bench pip install pymongo dnspython"
            )

    def build_uri(self):
        settings = frappe.get_single("MongoDB Settings")

        if settings.connection_uri:
            uri = settings.get_password("connection_uri")
            self.logger.debug("build_uri: using Connection URI field")
            return uri

        username = settings.username
        password = settings.get_password("password") if settings.password else None

        if password:
            password = quote_plus(password)

        host     = settings.host or "localhost"
        port     = int(settings.port or 27017)
        database = settings.database or frappe.local.site
        auth_src = settings.authentication_db or "admin"
        options  = (settings.options or "").strip()
        scheme   = "mongodb+srv" if settings.use_srv else "mongodb"
        creds    = f"{username}:{password}@" if (username and password) else ""

        # SRV URIs do not include a port
        if settings.use_srv:
            uri = f"{scheme}://{creds}{host}/{database}"
        else:
            uri = f"{scheme}://{creds}{host}:{port}/{database}"

        params = []

        if auth_src:
            params.append(f"authSource={auth_src}")

        replica_set = (settings.replica_set or "").strip()
        if replica_set:
            params.append(f"replicaSet={replica_set}")

        if options:
            params.append(options.lstrip("?&"))

        if params:
            uri += "?" + "&".join(params)

        self.logger.debug(f"build_uri: {scheme}://***@{host}/{database} | params: {params}")
        return uri

    def connect(self):
        settings = frappe.get_single("MongoDB Settings")

        if not settings.enable_mongodb:
            raise frappe.ValidationError("MongoDB is disabled in MongoDB Settings.")

        pymongo = self._get_driver()
        uri = self.build_uri()

        try:
            self._client = pymongo.MongoClient(
                uri,
                serverSelectionTimeoutMS=settings.connection_timeout or 5000,
            )
            db_name  = settings.database or frappe.local.site
            self._db = self._client[db_name]
            self._client.admin.command("ping")
            self.logger.info(f"MongoDB connected → {db_name}")
        except Exception as e:
            self.logger.error(str(e))
            raise frappe.ValidationError(f"MongoDB connection failed:\n\n{str(e)}")

    def disconnect(self):
        if self._client:
            self._client.close()
            self._client = None
            self._db     = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.disconnect()

    @property
    def db(self):
        if self._db is None:
            self.connect()
        return self._db

    def get_collection(self, collection: str):
        return self.db[collection]

    def get_list(
        self,
        collection: str,
        filters: dict = None,
        fields: list = None,
        limit: int = 0,
        skip: int = 0,
        sort=None,
        as_dict: bool = True,
    ) -> list:
        """
        Return multiple documents.

        mg.get_list("movies",
            filters={"year": {"$gte": 2020}},
            fields=["title", "year", "imdb"],
            sort=[("year", -1)],
            limit=20)
        """
        start = time.time()
        col   = self.get_collection(collection)

        projection = {f: 1 for f in fields} if fields else None
        cursor = col.find(filters or {}, projection)

        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)

        result = [_dict(doc) if as_dict else doc for doc in cursor]
        self._log_perf("get_list", collection, start, len(result))
        return result

    def get_value(
        self,
        collection: str,
        filters: dict,
        fieldname: str,
        default=None,
    ):
        """
        Return a single field value from the first matching doc.

        mg.get_value("movies", {"title": "Inception"}, "year")
        """
        doc = self.find_one(collection, filters, fields=[fieldname])
        if doc:
            return doc.get(fieldname, default)
        return default

    def find_one(
        self,
        collection: str,
        filters: dict = None,
        fields: list = None,
        sort=None,
    ) -> _dict | None:
        """
        Return first matching document or None.

        mg.find_one("movies", {"title": "Inception"})
        """
        start      = time.time()
        col        = self.get_collection(collection)
        projection = {f: 1 for f in fields} if fields else None
        kwargs     = {}
        if sort:
            kwargs["sort"] = sort
        doc = col.find_one(filters or {}, projection, **kwargs)
        self._log_perf("find_one", collection, start)
        return _dict(doc) if doc else None

    def exists(self, collection: str, filters: dict) -> bool:
        """
        Return True if at least one document matches.

        mg.exists("movies", {"title": "Inception"})
        """
        return self.find_one(collection, filters, fields=["_id"]) is not None

    def count(self, collection: str, filters: dict = None) -> int:
        """
        Count matching documents.

        mg.count("movies", {"year": 2024})
        """
        start  = time.time()
        result = self.get_collection(collection).count_documents(filters or {})
        self._log_perf("count", collection, start)
        return result

    def distinct(self, collection: str, field: str, filters: dict = None) -> list:
        """
        Return distinct values for a field.

        mg.distinct("movies", "genres")
        """
        start  = time.time()
        result = self.get_collection(collection).distinct(field, filters or {})
        self._log_perf("distinct", collection, start)
        return result

    def aggregate(self, collection: str, pipeline: list, as_dict: bool = True) -> list:
        """
        Run an aggregation pipeline.

        mg.aggregate("movies", [
            {"$match": {"year": 2024}},
            {"$group": {"_id": "$genres", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])
        """
        start  = time.time()
        cursor = self.get_collection(collection).aggregate(pipeline)
        result = [_dict(doc) if as_dict else doc for doc in cursor]
        self._log_perf("aggregate", collection, start, len(result))
        return result

    def insert(self, collection: str, doc: dict):
        """
        Insert a single document. Adds 'creation' timestamp automatically.

        Returns: inserted_id (ObjectId)
        """
        start = time.time()
        if isinstance(doc, dict):
            doc.setdefault("creation", datetime.now())
            doc.setdefault("modified", datetime.now())

        res = self.get_collection(collection).insert_one(doc)
        self._log_perf("insert", collection, start)
        return res.inserted_id

    def bulk_insert(self, collection: str, docs: list) -> list:
        """
        Insert many documents at once. Returns list of inserted_ids.

        mg.bulk_insert("movies", [{"title": "A"}, {"title": "B"}])
        """
        start = time.time()
        now   = datetime.now()
        for doc in docs:
            doc.setdefault("creation", now)
            doc.setdefault("modified", now)

        res = self.get_collection(collection).insert_many(docs)
        self._log_perf("bulk_insert", collection, start, len(docs))
        return res.inserted_ids

    def update(self, collection: str, filters: dict, values: dict) -> int:
        """
        Update all matching documents with $set. Returns modified_count.

        mg.update("movies", {"year": 2020}, {"reviewed": True})
        """
        start = time.time()
        values.setdefault("modified", datetime.now())
        res   = self.get_collection(collection).update_many(
            filters, {"$set": values}
        )
        self._log_perf("update", collection, start, res.modified_count)
        return res.modified_count

    def update_one(self, collection: str, filters: dict, values: dict) -> int:
        """
        Update first matching document only.
        """
        start = time.time()
        values.setdefault("modified", datetime.now())
        res   = self.get_collection(collection).update_one(
            filters, {"$set": values}
        )
        self._log_perf("update_one", collection, start)
        return res.modified_count

    def upsert(self, collection: str, filters: dict, values: dict) -> dict:
        """
        Update if exists, insert if not. Returns {'matched', 'modified', 'upserted_id'}.

        mg.upsert("config", {"key": "theme"}, {"key": "theme", "value": "dark"})
        """
        start = time.time()
        values["modified"] = datetime.now()
        res   = self.get_collection(collection).update_one(
            filters,
            {"$set": values, "$setOnInsert": {"creation": datetime.now()}},
            upsert=True,
        )
        self._log_perf("upsert", collection, start)
        return {
            "matched":     res.matched_count,
            "modified":    res.modified_count,
            "upserted_id": res.upserted_id,
        }

    def delete(self, collection: str, filters: dict) -> int:
        """
        Delete all matching documents. Returns deleted_count.

        mg.delete("movies", {"year": {"$lt": 1950}})
        """
        start = time.time()
        res   = self.get_collection(collection).delete_many(filters)
        self._log_perf("delete", collection, start, res.deleted_count)
        return res.deleted_count

    def delete_one(self, collection: str, filters: dict) -> int:
        """
        Delete first matching document only.
        """
        start = time.time()
        res   = self.get_collection(collection).delete_one(filters)
        self._log_perf("delete_one", collection, start)
        return res.deleted_count

    def create_index(self, collection: str, keys, unique: bool = False, **kwargs):
        """
        mg.create_index("movies", [("title", 1)], unique=True)
        mg.create_index("movies", [("year", -1), ("title", 1)])
        """
        return self.get_collection(collection).create_index(
            keys, unique=unique, **kwargs
        )

    def list_indexes(self, collection: str) -> list:
        return list(self.get_collection(collection).list_indexes())

    def get_status(self) -> dict:
        return self.db.command("serverStatus")

    def ping(self) -> bool:
        try:
            self._client.admin.command("ping")
            return True
        except Exception:
            return False

    def list_collections(self) -> list:
        return self.db.list_collection_names()

    def collection_stats(self, collection: str) -> dict:
        return self.db.command("collStats", collection)

    def _log_perf(self, method, collection, start, count=None):
        ms    = (time.time() - start) * 1000
        extra = f" | {count} docs" if count is not None else ""
        msg   = f"{method} | {collection} | {ms:.2f}ms{extra}"

        if ms > 200:
            self.logger.warning(f"SLOW QUERY | {msg}")
        elif ms > 50:
            self.logger.info(msg)
        else:
            self.logger.debug(msg)