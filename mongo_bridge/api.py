import frappe
from mongo_bridge.utils import get_mg


@frappe.whitelist()
def get_mongo_status():
    try:
        settings = frappe.get_single("MongoDB Settings")

        if not settings.enable_mongodb:
            return {"ok": False, "disabled": True}

        mg = get_mg()
        s  = mg.db.command("serverStatus")

        return {
            "ok":                    True,
            "disabled":              False,
            "uptime":                s.get("uptime", 0),
            "version":               s.get("version", ""),
            "process":               s.get("process", ""),
            "pid":                   s.get("pid", ""),
            "host":                  s.get("host", ""),
            "mem_resident":          s.get("mem", {}).get("resident", 0),
            "mem_virtual":           s.get("mem", {}).get("virtual",  0),
            "connections_current":   s.get("connections", {}).get("current",   0),
            "connections_available": s.get("connections", {}).get("available", 0),
            "connections_total":     s.get("connections", {}).get("totalCreated", 0),
            "ops_insert":            s.get("opcounters", {}).get("insert",  0),
            "ops_query":             s.get("opcounters", {}).get("query",   0),
            "ops_update":            s.get("opcounters", {}).get("update",  0),
            "ops_delete":            s.get("opcounters", {}).get("delete",  0),
            "ops_getmore":           s.get("opcounters", {}).get("getmore", 0),
            "ops_command":           s.get("opcounters", {}).get("command", 0),
            "net_bytes_in":          s.get("network", {}).get("bytesIn",     0),
            "net_bytes_out":         s.get("network", {}).get("bytesOut",    0),
            "net_num_requests":      s.get("network", {}).get("numRequests", 0),
            "storage_engine":        s.get("storageEngine", {}).get("name", ""),
            "page_faults":           s.get("extra_info",    {}).get("page_faults", 0),
        }

    except Exception as e:
        frappe.log_error(str(e), "MongoDB Monitor")
        return {"ok": False, "disabled": False, "error": str(e)}


@frappe.whitelist()
def get_collections_stats():
    try:
        mg   = get_mg()
        db   = mg.db
        cols = db.list_collection_names()
        out  = []
        for name in cols:
            stats = db.command("collStats", name)
            out.append({
                "name":  name,
                "count": stats.get("count", 0),
                "size":  stats.get("size",  0),
            })
        return sorted(out, key=lambda x: x["count"], reverse=True)
    except Exception as e:
        frappe.log_error(str(e), "MongoDB Monitor")
        return []


@frappe.whitelist()
def test_connection():
    try:
        from mongo_bridge.database.mongo_db import MongoDatabase
        mg     = MongoDatabase()
        mg.connect()
        status = mg.get_status()
        mg.disconnect()
        return {
            "ok":      True,
            "version": status.get("version", ""),
            "host":    status.get("host", ""),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@frappe.whitelist()
def get_mongo_logs(lines=50):
    import os
    log_path = os.path.join(
        frappe.utils.get_bench_path(), "logs", "mongodb_bridge.log"
    )
    if not os.path.exists(log_path):
        return {"lines": [], "exists": False}

    with open(log_path, "r") as f:
        all_lines = f.readlines()

    return {
        "exists": True,
        "lines": all_lines[-int(lines):]
    }