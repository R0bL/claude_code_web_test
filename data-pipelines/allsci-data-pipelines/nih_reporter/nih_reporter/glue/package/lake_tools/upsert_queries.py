from dataclasses import dataclass

@dataclass
class QuerySet:
    update_query: str
    insert_records: str
    insert_query: str
    insert_master_query: str = ""
    update_master_table: str = ""
