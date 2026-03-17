<div align="center">
  <img src="https://github.com/manoj65356/mongo-bridge/blob/develop/mongo_bridge/public/images/logo.png" alt="Mongo Bridge" width="80">
  <h2>Mongo Bridge</h2>
  <p>A Frappe custom app that integrates MongoDB into your Frappe / ERPNext instance —<br>full database API, per-request connection management, and a live monitoring dashboard.</p>
  <p>
    <a href="https://github.com/manoj65356/mongo-bridge/blob/develop/license.txt">
      <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
    </a>
    <a href="https://github.com/frappe/frappe">
      <img src="https://img.shields.io/badge/Frappe-v14%20%7C%20v15-blue" alt="Frappe">
    </a>
    <img src="https://img.shields.io/badge/MongoDB-5.0%2B-green?logo=mongodb&logoColor=white" alt="MongoDB">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python">
  </p>
  <img src="https://github.com/manoj65356/mongo-bridge/blob/develop/mongo_bridge/public/images/screenshot.png" alt="MongoDB Monitor Dashboard" width="900">
</div>

---

## Table of contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Database API reference](#database-api-reference)
- [Monitor dashboard](#monitor-dashboard)
- [CLI commands](#cli-commands)
- [Troubleshooting](#troubleshooting)

---

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| Frappe Framework | v14 above | |
| Python | 3.10+ | |
| pymongo | 4.x | `bench pip install pymongo` |
| dnspython | 2.x | Required for `mongodb+srv://` (Atlas) |
| MongoDB | 5.0+ | Local or Atlas |

Install Python dependencies:

```bash
bench pip install pymongo dnspython
```

---

## Installation

```bash
# 1. Get the app
cd /home/frappe/frappe-bench
bench get-app https://github.com/manoj65356/mongo-bridge.git

# 2. Install on your site
bench --site your-site.localhost install-app mongo_bridge

# 3. Build static assets (for the logo)
bench build --app mongo_bridge

# 4. Restart
bench restart
```

---

## Configuration

Open **MongoDB Settings** in your Frappe desk:

```
http://your-site/app/mongodb-settings/MongoDB Settings
```

Or navigate directly from the Mongo Bridge app in the Apps screen.

### Field reference

| Field | Type | Description | Example |
|---|---|---|---|
| Enable MongoDB | Check | Master on/off switch | ✓ |
| Mongo Host | Data | Hostname or Atlas cluster URL | `cluster.xhvr1jr.mongodb.net` |
| Mongo Port | Int | Port — ignored when Use SRV is on | `27017` |
| Database Name | Data | Database to connect to | `sample_mflix` |
| Authentication DB | Data | Auth source database | `admin` |
| Username | Data | MongoDB username | `myuser` |
| Password | Password | Stored encrypted, decrypted at runtime | `••••••••` |
| Is Remote | Check | Toggle for remote vs local server | ✓ |
| SSL Enabled | Check | Enable TLS/SSL | ✓ |
| Use SRV (Atlas) | Check | Use `mongodb+srv://` scheme | ✓ |
| Connection URI | **Password** | Full URI — stored encrypted, overrides all other fields when set | `mongodb+srv://user:pass@host/db` |
| Connection Timeout | Int | Server selection timeout in ms | `5000` |
| Replica Set | Data | Replica set name — required for Atlas and local replica sets | `atlas-shard-0` / `rs0` |
| Options | Data | Extra URI query params appended last | `retryWrites=true&w=majority` |

### Replica Set — why it matters

Without `Replica Set` filled in, pymongo connects in standalone mode even when the server is part of a replica set or sharded Atlas cluster. This silently breaks three things:

- **Read preference** (`secondaryPreferred`, `nearest`) is ignored — all reads go to the primary
- **Automatic failover** does not happen if the primary goes down
- **Atlas topology** is not fully discovered — the driver does not learn about other shards

For Atlas, find the replica set name in the Atlas UI under **Cluster → Connect → Drivers** — it is usually `atlas-shard-0`. For a local replica set started with `rs.initiate()`, the default name is `rs0`.

### Connection URI field

`Connection URI` is a `Password` field — the value is stored encrypted and decrypted at runtime using `get_password()`. Use this when you want to paste a full connection string directly, for example copied from the Atlas Connect dialog. When set, it overrides every other field — host, port, username, password, replica set, and options — completely.

### URI build order

When Connection URI is **not** set, `build_uri()` assembles the query string in this fixed order:

```
scheme://user:pass@host:port/database?authSource=...&replicaSet=...&<options>
```

Any leading `?` or `&` accidentally typed in the Options field is stripped automatically.

### Test the connection

Click the **Test Connection** button in MongoDB Settings to verify before saving.

---

## Usage

### `frappe.mg` — works exactly like `frappe.db`

`init_mongodb()` runs automatically on every request via `before_request` in `hooks.py`. It sets `frappe.mg` — available everywhere in Frappe with **no import needed**, exactly like `frappe.db`.

```
frappe.db.get_value(...)   →   frappe.mg.get_value("collection", ...)
frappe.db.get_list(...)    →   frappe.mg.get_list("collection", ...)
frappe.db.exists(...)      →   frappe.mg.exists("collection", {...})
frappe.db.insert(...)      →   frappe.mg.insert("collection", {...})
```

### In any Frappe Python file — no import needed

```python
# In a DocType controller
class SalesOrder(Document):
    def after_insert(self):
        frappe.mg.insert("order_events", {
            "order_id": self.name,
            "event":    "created",
            "customer": self.customer,
        })

    def on_submit(self):
        doc = frappe.mg.find_one("order_events", {"order_id": self.name})

    def on_cancel(self):
        frappe.mg.delete("order_events", {"order_id": self.name})
```

```python
# In a whitelisted API
@frappe.whitelist()
def get_movies():
    return frappe.mg.get_list("movies",
        filters={"year": {"$gte": 2020}},
        limit=10
    )
```

```python
# In a scheduled job
def sync_data():
    count = frappe.mg.count("events", {"synced": False})
    frappe.mg.update("events", {"synced": False}, {"synced": True})
```

> **Guard when MongoDB may be disabled:**
> ```python
> if frappe.mg:
>     frappe.mg.insert("logs", {"event": "something"})
> ```

### In bench console

`before_request` does not run in the console, so initialise once manually:

```bash
bench --site your-site.localhost console
```

```python
from mongo_bridge.utils import init_mongodb
init_mongodb()

# Now use frappe.mg exactly as you would anywhere else
frappe.mg.ping()
frappe.mg.list_collections()
frappe.mg.get_list("movies", limit=5)
frappe.mg.count("movies", {"year": 2024})
frappe.mg.find_one("movies", {"title": "Inception"})
```

---

## Database API reference

All methods are on `frappe.mg` — no import needed.

---

### READ methods

#### `get_list(collection, filters, fields, limit, skip, sort, as_dict)`

Returns a list of documents matching filters.

```python
movies = frappe.mg.get_list(
    "movies",
    filters={"year": {"$gte": 2020}},
    fields=["title", "year"],
    sort=[("year", -1)],
    limit=20,
    skip=0,
)
# Returns: [{"title": "...", "year": 2024, "_id": ObjectId(...)}, ...]
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `collection` | str | required | Collection name |
| `filters` | dict | `{}` | MongoDB filter query |
| `fields` | list | `None` | Fields to include (projection) |
| `limit` | int | `0` | Max results (0 = no limit) |
| `skip` | int | `0` | Number of docs to skip (for pagination) |
| `sort` | list | `None` | e.g. `[("year", -1)]` |
| `as_dict` | bool | `True` | Return `frappe._dict` objects |

---

#### `find_one(collection, filters, fields, sort)`

Returns the first matching document or `None`.

```python
movie = frappe.mg.find_one("movies", {"title": "Inception"})

if movie:
    print(movie.year)   # dot-access because it's frappe._dict
```

---

#### `get_value(collection, filters, fieldname, default)`

Returns a single field value from the first matching document.

```python
year = frappe.mg.get_value("movies", {"title": "Inception"}, "year")
# Returns: 2010

missing = frappe.mg.get_value("movies", {"title": "Fake"}, "year", default=0)
# Returns: 0
```

---

#### `exists(collection, filters)`

Returns `True` if at least one document matches.

```python
if frappe.mg.exists("movies", {"title": "Inception"}):
    frappe.msgprint("Found it!")
```

---

#### `count(collection, filters)`

Returns the count of matching documents.

```python
total_2024 = frappe.mg.count("movies", {"year": 2024})
all_docs    = frappe.mg.count("movies")
```

---

#### `distinct(collection, field, filters)`

Returns a list of distinct values for a field.

```python
all_genres  = frappe.mg.distinct("movies", "genres")
# Returns: ["Action", "Comedy", "Drama", ...]

genres_2024 = frappe.mg.distinct("movies", "genres", {"year": 2024})
```

---

#### `aggregate(collection, pipeline, as_dict)`

Runs a MongoDB aggregation pipeline.

```python
results = frappe.mg.aggregate("movies", [
    {"$unwind": "$genres"},
    {"$group": {"_id": "$genres", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
    {"$limit": 10},
])
# Returns: [{"_id": "Drama", "count": 2452}, ...]
```

---

### WRITE methods

#### `insert(collection, doc)`

Inserts a single document. Automatically adds `creation` and `modified` timestamps.

```python
inserted_id = frappe.mg.insert("movies", {
    "title": "My New Film",
    "year":  2025,
    "genres": ["Drama"],
})
# Returns: ObjectId("...")
```

---

#### `bulk_insert(collection, docs)`

Inserts many documents at once. Returns a list of inserted IDs.

```python
ids = frappe.mg.bulk_insert("movies", [
    {"title": "Film A", "year": 2025},
    {"title": "Film B", "year": 2025},
])
```

---

#### `update(collection, filters, values)`

Updates **all** matching documents using `$set`. Returns modified count.

```python
count = frappe.mg.update(
    "movies",
    {"year": {"$lt": 1950}},
    {"era": "classic"}
)
```

---

#### `update_one(collection, filters, values)`

Updates only the **first** matching document.

```python
frappe.mg.update_one("movies", {"title": "Inception"}, {"reviewed": True})
```

---

#### `upsert(collection, filters, values)`

Updates if the document exists, inserts if it does not.

```python
result = frappe.mg.upsert(
    "app_config",
    {"key": "theme"},
    {"key": "theme", "value": "dark"}
)
# result = {"matched": 1, "modified": 1, "upserted_id": None}
```

---

#### `delete(collection, filters)`

Deletes **all** matching documents. Returns deleted count.

```python
deleted = frappe.mg.delete("movies", {"year": {"$lt": 1900}})
```

---

#### `delete_one(collection, filters)`

Deletes only the **first** matching document.

```python
frappe.mg.delete_one("movies", {"title": "Draft Film"})
```

---

### Index methods

```python
# Single field
frappe.mg.create_index("movies", [("title", 1)])

# Compound
frappe.mg.create_index("movies", [("year", -1), ("title", 1)])

# Unique
frappe.mg.create_index("users", [("email", 1)], unique=True)

# Text search
frappe.mg.create_index("movies", [("title", "text"), ("plot", "text")])

# List indexes
frappe.mg.list_indexes("movies")
```

---

### Health methods

| Method | Returns | Description |
|---|---|---|
| `frappe.mg.ping()` | `bool` | True if server is reachable |
| `frappe.mg.get_status()` | `dict` | Full MongoDB `serverStatus` |
| `frappe.mg.list_collections()` | `list` | Collection names in current database |
| `frappe.mg.collection_stats(name)` | `dict` | Count, size, index info for one collection |
| `frappe.mg.disconnect()` | — | Close the connection |

---

### MongoDB filter syntax quick reference

```python
# Equality
{"field": "value"}

# Comparison
{"year": {"$gt": 2000}}          # greater than
{"year": {"$gte": 2000}}         # greater than or equal
{"year": {"$lt": 2020}}          # less than
{"year": {"$lte": 2020}}         # less than or equal
{"year": {"$ne": 2000}}          # not equal

# Multiple conditions (AND)
{"year": {"$gte": 2000, "$lte": 2020}}

# OR
{"$or": [{"year": 2020}, {"year": 2021}]}

# IN / NOT IN
{"year": {"$in": [2020, 2021, 2022]}}
{"year": {"$nin": [2020, 2021]}}

# Exists
{"poster": {"$exists": True}}

# Array contains
{"genres": "Drama"}
{"genres": {"$all": ["Drama", "Crime"]}}

# Regex
{"title": {"$regex": "^The", "$options": "i"}}

# Nested field
{"imdb.rating": {"$gte": 8.0}}
```

---

## Monitor dashboard

Navigate to `/mongo-monitor` on your site. The dashboard auto-refreshes every 30 seconds.

### Panels explained

| Panel | What it shows | Why it matters |
|---|---|---|
| **Uptime** | Time since server last started | Unexpected low uptime = recent crash or restart |
| **Active connections** | Current open connections + available pool | High active connections = possible connection leak |
| **Resident memory** | RAM in MB used by mongod | Rising memory = data growing into RAM, index pressure |
| **Version** | MongoDB server version + storage engine | WiredTiger is standard; MMAPv1 is legacy |
| **Collections** | Count of collections in the connected database | |
| **Total ops** | Cumulative insert/query/update/delete/getmore since server start | Baseline for query volume |
| **Server info** | Process name, PID, host, virtual memory, page faults | Page faults rising = working set exceeds RAM |
| **Operations breakdown** | Per-operation type bar chart | Unusually high inserts or deletes may need attention |
| **Collections table** | Per-collection document count and storage size | Identify large collections |
| **Connection pool gauge** | Visual active vs available connection bars | Ensure you have headroom |
| **Network I/O** | Bytes in, bytes out, total requests | Useful for bandwidth monitoring |

---

## CLI commands

```bash
# Real-time health check in the terminal
bench mongo-stats --site your-site.localhost
```

Output:

```
--- MongoDB Monitor [your-site.localhost] ---
Uptime:      3d 15h
Version:     8.0.20
Connections: 3 active
Memory:      256MB Resident
```

---

## Troubleshooting

**`pymongo` or `dnspython` not found**
```bash
bench pip install pymongo dnspython
bench restart
```

**Logo not appearing in Apps screen**
```bash
# Confirm file exists at:
apps/mongo_bridge/mongo_bridge/public/images/logo.png

# Then rebuild assets:
bench build --app mongo_bridge
bench clear-cache
```

**`frappe.mg` is None**

This usually means `enable_mongodb` is unchecked in MongoDB Settings, or the connection failed silently. Check:
```bash
bench --site your-site.localhost console
```
```python
from mongo_bridge.utils import init_mongodb
init_mongodb()
frappe.mg.ping()   # Should return True
```

**Read preference or failover not working**

You are missing the `Replica Set` field. Without it pymongo operates in standalone mode regardless of the actual server topology. Set it to `atlas-shard-0` for Atlas or `rs0` for a local replica set, save, then run `bench restart`.

**Connection URI field value not being picked up**

The field is `Password` type — resave the document so it gets encrypted properly. Then verify:
```bash
bench --site your-site.localhost console
```
```python
s = frappe.get_single("MongoDB Settings")
bool(s.connection_uri)            # True = field has a value
s.get_password("connection_uri")  # Should return the plain URI
```

**`serverSelectionTimeoutError` on Atlas**

Ensure `dnspython` is installed, `Use SRV (Atlas)` is checked, and the connecting server IP is whitelisted in Atlas → Network Access → IP Access List.

**Replica set name for Atlas**

In the Atlas UI go to your cluster → **Connect** → **Connect your application** → copy the connection string. The replica set name appears as `?replicaSet=atlas-shard-0` at the end. Copy just `atlas-shard-0` into the Replica Set field.

**Slow queries in logs**

Queries taking more than 200 ms are logged as `SLOW QUERY`. Add an index on the field you are filtering by:
```python
frappe.mg.create_index("your_collection", [("the_slow_field", 1)])
```