from enum import Enum


class PatchPlanFilename(str, Enum):
    VERTICES_TO_ADD = "vertices_to_add.json"
    VERTICES_TO_UPDATE = "vertices_to_update.json"
    VERTICES_TO_DELETE = "vertices_to_delete.json"
    EDGES_TO_ADD = "edges_to_add.json"
    EDGES_TO_UPDATE = "edges_to_update.json"
    EDGES_TO_DELETE = "edges_to_delete.json"
    ADDED_DB_IDS = "added_db_ids.json"
    DELETED_DB_IDS = "deleted_db_ids.json"
    REVERTED_DELETED_DB_IDS = "reverted_deleted_db_ids.json"
