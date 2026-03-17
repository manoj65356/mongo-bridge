import frappe
import mongo_bridge
from mongo_bridge.database.mongo_db import MongoDatabase


def init_mongodb():
    try:
        settings = frappe.get_single("MongoDB Settings")
    except Exception:
        return
 
    if not settings.enable_mongodb:
        return
 
    if mongo_bridge.mg is not None:
        try:
            mongo_bridge.mg.ping()
            frappe.mg = mongo_bridge.mg
            return
        except Exception:
            pass
 
    try:
        instance = MongoDatabase()
        instance.connect()
        mongo_bridge.mg = instance
        frappe.mg       = instance
    except Exception as e:
        frappe.logger("mongodb_bridge").error(f"init_mongodb failed: {e}")
        mongo_bridge.mg = None
        frappe.mg       = None
 
 
def get_mg() -> MongoDatabase:
    mg = getattr(frappe, "mg", None)
    if mg is None:
        init_mongodb()
        mg = getattr(frappe, "mg", None)
    if mg is None:
        raise frappe.ValidationError(
            "MongoDB is not initialised. "
            "Check that MongoDB is enabled in MongoDB Settings and the server is reachable."
        )
    return mg


def mg_get_list(collection, **kwargs):
    return get_mg().get_list(collection, **kwargs)

def mg_find_one(collection, filters=None, **kwargs):
    return get_mg().find_one(collection, filters, **kwargs)

def mg_get_value(collection, filters, fieldname, default=None):
    return get_mg().get_value(collection, filters, fieldname, default)

def mg_insert(collection, doc):
    return get_mg().insert(collection, doc)

def mg_update(collection, filters, values):
    return get_mg().update(collection, filters, values)

def mg_upsert(collection, filters, values):
    return get_mg().upsert(collection, filters, values)

def mg_delete(collection, filters):
    return get_mg().delete(collection, filters)

def mg_count(collection, filters=None):
    return get_mg().count(collection, filters)

def mg_aggregate(collection, pipeline):
    return get_mg().aggregate(collection, pipeline)

def mg_exists(collection, filters):
    return get_mg().exists(collection, filters)