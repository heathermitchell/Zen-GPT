from flask import Flask, request, jsonify
from flask_cors import CORS
from notion_client import Client
import os
import time
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")    
PAGE_ID = os.getenv("NOTION_PAGE_ID")

notion = Client(auth=NOTION_TOKEN)
app = Flask(__name__)
CORS(app)

# --- Helpers ---
def safe_notion_call(func, retries=1, delay=2):
    try:
        return func()
    except Exception as e:
        if retries > 0:
            time.sleep(delay)
            return safe_notion_call(func, retries - 1, delay)
        else:
            raise e

# --- Routes ---
@app.route("/create_table", methods=["POST"])
def create_table():
    data = request.get_json(force=True) or {}
    table_name = data.get("table")
    fields = data.get("fields")

    if not table_name or not fields:
        return jsonify({"error": "Missing table name or fields"}), 400

    try:
        properties = {}
        for name, ftype in fields.items():
            if ftype == "title":
                properties[name] = {"title": {}}
            elif ftype == "rich_text":
                properties[name] = {"rich_text": {}}
            elif ftype == "select":
                properties[name] = {"select": {}}
            else:
                properties[name] = {"rich_text": {}}  # default fallback

        if not any("title" in prop for prop in properties.values()):
            properties["Name"] = {"title": {}}

        def create_db():
            return notion.databases.create(
                parent={"type": "page_id", "page_id": PAGE_ID},
                title=[{"type": "text", "text": {"content": table_name}}],
                properties=properties
            )

        db = safe_notion_call(create_db)
        print(f"Database created: {db['id']}")
        return jsonify({"message": "OK", "database_id": db["id"]}), 200

    except Exception as e:
        print(f"Create error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/insert", methods=["POST"])
def insert_row():
    data = request.get_json(force=True)
    db_id = data.get("database_id")
    values = data.get("values")

    if not db_id or not values:
        return jsonify({"error": "Missing database_id or values"}), 400

    try:
        properties = {}
        for k, v in values.items():
            if k.lower() == "tree":
                properties[k] = {"title": [{"text": {"content": v}}]}
            elif k.lower() == "status":
                properties[k] = {"select": {"name": v}}
            else:
                properties[k] = {"rich_text": [{"text": {"content": v}}]}

        def insert_page():
            return notion.pages.create(
                parent={"database_id": db_id},
                properties=properties
            )

        page = safe_notion_call(insert_page)
        print(f"Page created: {page['id']}")
        return jsonify({"message": "OK", "page_id": page["id"]}), 200

    except Exception as e:
        print(f"Insert error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/update_table", methods=["PATCH"])
def update_table():
    data = request.get_json(force=True)
    db_id = data.get("database_id")
    new_fields = data.get("fields")

    if not db_id or not new_fields:
        return jsonify({"error": "Missing database_id or fields"}), 400

    try:
        update_payload = {"properties": {}}

        for name, ftype in new_fields.items():
            if ftype == "title":
                update_payload["properties"][name] = {"title": {}}
            elif ftype == "rich_text":
                update_payload["properties"][name] = {"rich_text": {}}
            elif ftype == "select":
                update_payload["properties"][name] = {"select": {"options": []}}
            else:
                update_payload["properties"][name] = {"rich_text": {}}

        def update_db():
            return notion.databases.update(
                database_id=db_id,
                properties=update_payload["properties"]
            )

        result = safe_notion_call(update_db)
        print(f"Updated database: {db_id}")
        return jsonify({"message": "Updated", "database_id": db_id}), 200

    except Exception as e:
        print(f"Update error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get_rows", methods=["POST"])
def get_rows():
    data = request.get_json(force=True)
    db_id = data.get("database_id")

    if not db_id:
        return jsonify({"error": "Missing database_id"}), 400

    try:
        def query_db():
            return notion.databases.query(database_id=db_id)

        response = safe_notion_call(query_db)
        rows = []

        for result in response.get("results", []):
            row = {}
            props = result.get("properties", {})
            for key, value in props.items():
                if value["type"] == "title":
                    row[key] = value["title"][0]["text"]["content"] if value["title"] else ""
                elif value["type"] == "rich_text":
                    row[key] = value["rich_text"][0]["text"]["content"] if value["rich_text"] else ""
                elif value["type"] == "select":
                    row[key] = value["select"]["name"] if value["select"] else ""
                else:
                    row[key] = "[unsupported type]"
            rows.append(row)

        return jsonify(rows), 200

    except Exception as e:
        print(f"GET error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return "OK", 200

@app.route("/openapi.json", methods=["GET"])
def openapi_schema():
    return jsonify({
        "openapi": "3.0.0",
        "info": {
            "title": "Chirpy Note API",
            "version": "1.0.0",
            "description": "API for sending Chirpy notes into Notion"
        },
        "paths": {
            "/insert": {
                "post": {
                    "summary": "Insert a new Chirpy note",
                    "operationId": "send_chirpy_to_api",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "database_id": {
                                            "type": "string"
                                        },
                                        "values": {
                                            "type": "object",
                                            "properties": {
                                                "Tree": {
                                                    "type": "string"
                                                },
                                                "Notes": {
                                                    "type": "string"
                                                },
                                                "Status": {
                                                    "type": "string"
                                                },
                                                "Tags": {
                                                    "type": "array",
                                                    "items": { "type": "string" }
                                                },
                                                "Vibe": {
                                                    "type": "string"
                                                }
                                            },
                                            "required": ["Tree"]
                                        }
                                    },
                                    "required": ["database_id", "values"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Successful insert"
                        }
                    }
                }
            }
        }
    })
