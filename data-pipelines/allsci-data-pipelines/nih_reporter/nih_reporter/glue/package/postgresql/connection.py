import psycopg2

class PostgreSQLConnection:
    def __init__(self, db_params):
        self.db_params = {
            "dbname": db_params['database'],
            "user": db_params['username'],
            "password": db_params['password'],
            "host": db_params['host'],
            "port": db_params['port']
        }
        self.conn = self._connect()

    def _connect(self):
        try:
            conn = psycopg2.connect(**self.db_params)
            return conn

        except Exception as e:
            print(f"Error occurred: {e}")
        

    def execute_query(self, query):
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            self.conn.commit()
            print("Query executed successfully.")

        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Error occurred: {e}")

        finally:
            cursor.close()

    def close(self):
        self.conn.close()

def get_max_part_id(postgresql_conn, schema_table: str):
    
    with postgresql_conn.cursor() as cursor:
        # Fetch the max value from allsci_id_part
        cursor.execute(
            f"""
            SELECT COALESCE(MAX(allsci_id_part), 0)
            FROM {schema_table}
            WHERE allsci_id_part < 100000000000
            """)
        max_value = cursor.fetchone()[0]
    
    return max_value