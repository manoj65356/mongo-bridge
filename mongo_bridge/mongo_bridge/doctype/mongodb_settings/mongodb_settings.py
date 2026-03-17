# Copyright (c) 2026, Active Minutes and contributors
# For license information, please see license.txt

import frappe
from mongo_bridge.database.mongo_db import MongoDatabase
from frappe.model.document import Document


class MongoDBSettings(Document):
	def validate(self):

		if self.enable_mongodb and not self.is_remote and not self.host:

			try:
				import pymongo
			except ImportError:
				frappe.throw(
					"MongoDB enabled but pymongo is not installed. Run: bench pip install pymongo"
				)

@frappe.whitelist()
def test_connection():
    try:

        mg = MongoDatabase()
        mg.connect()

        return {
            "status": "success",
            "message": "MongoDB connection successful"
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }