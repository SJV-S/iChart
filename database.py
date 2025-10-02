from app_imports import *
from EventStateManager import EventBus


# Debug flag and function
DEBUG_DATABASE = False

def debug_print(message):
    """Print debug messages only when DEBUG_DATABASE is True"""
    if DEBUG_DATABASE:
        print(message)


class SQLiteDatabase:
    # Low-level database operations and connection management.
    # Handles schema creation, transactions, and basic CRUD operations.

    TABLE_DATA_POINTS = "series"
    TABLE_CHART_METADATA = "chart"
    TABLE_CHART_SYNC = "chart_sync"
    TABLE_TOMBSTONES = "tombstones"
    DB_NAME = 'opencelerator'

    # SINGLE SOURCE OF TRUTH FOR ALL SCHEMAS
    SCHEMA_DEFINITIONS = {
        'series': {  # TABLE_DATA_POINTS
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'chart_id': 'TEXT',
            'date': 'TEXT',
            'sys_col': 'TEXT',
            'value': 'REAL'
        },
        'chart': {  # TABLE_CHART_METADATA
            'chart_id': 'TEXT PRIMARY KEY',
            'metadata': 'TEXT',
            'thumbnail': 'BLOB',
            'metadata_hash': 'TEXT',
            'last_modified': 'INTEGER',
            'owner': 'TEXT',
            'accepting_changes': 'INTEGER DEFAULT 0'
        },
        'chart_sync': {  # TABLE_CHART_SYNC
            'chart_id': 'TEXT',
            'sync_location': 'TEXT',
            'last_sync': 'INTEGER',
            'local_hash': 'TEXT',
            '_primary_key': '(chart_id, sync_location)'
        },
        'tombstones': {  # TABLE_TOMBSTONES
            'chart_id': 'TEXT PRIMARY KEY',
            'added': 'INTEGER'
        }
    }

    COLUMN_DEFAULTS = {
        'chart': {
            'owner': None,  # Will be set to current user
            'accepting_changes': 0,
            'last_modified': 0
        }
    }

    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.connection = None
        self.cursor = None
        self.initialized = False

    def connect(self, db_path=None):
        """Establish database connection and create tables if needed."""
        if not db_path:
            db_path = self.data_manager.get_config_directory(as_str=True)

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        db_file = Path(db_path) / f"{self.DB_NAME}.db"
        
        debug_print(f"connect() - opening database file: {str(db_file)}")

        try:
            self.connection = sqlite3.connect(str(db_file))
            self.cursor = self.connection.cursor()
            self.initialized = True
            self._create_tables()
            self._migrate_schema()
            
            # Count total charts after database connection
            try:
                self.cursor.execute(f"SELECT COUNT(*) FROM {self.TABLE_CHART_METADATA}")
                chart_count = self.cursor.fetchone()[0]
                debug_print(f"connect() - total charts found in database: {chart_count}")
                
                # Also log all chart IDs for debugging
                self.cursor.execute(f"SELECT chart_id FROM {self.TABLE_CHART_METADATA}")
                chart_ids = [row[0] for row in self.cursor.fetchall()]
                debug_print(f"connect() - chart IDs in database: {chart_ids}")
            except sqlite3.Error as e:
                debug_print(f"connect() - error counting charts: {e}")
            
            return True
        except sqlite3.Error as e:
            debug_print(f"Database connection error: {e}")
            self.initialized = False
            return False

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.initialized = False

    def _create_tables(self):
        """Create tables using centralized schema definitions."""
        for table_name in self.SCHEMA_DEFINITIONS:
            sql = self._get_create_table_sql(table_name)
            self.cursor.execute(sql)
        self.connection.commit()

    def _get_create_table_sql(self, table_name):
        """Generate CREATE TABLE SQL from schema definition."""
        schema = self.SCHEMA_DEFINITIONS[table_name]
        columns = []
        primary_key = None

        for col_name, col_def in schema.items():
            if col_name == '_primary_key':
                primary_key = col_def
            elif not col_name.startswith('_'):
                columns.append(f"{col_name} {col_def}")

        sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n    "
        sql += ",\n    ".join(columns)

        if primary_key:
            sql += f",\n    PRIMARY KEY {primary_key}"

        sql += "\n)"
        return sql

    def _migrate_schema(self):
        """Simple migration: if old schema detected, backup data, drop and recreate tables with data."""
        try:
            self.cursor.execute(f"PRAGMA table_info({self.TABLE_DATA_POINTS})")
            columns = {row[1]: row[5] for row in self.cursor.fetchall()}

            # If 'id' column doesn't exist, need to migrate
            if 'id' not in columns:
                debug_print(f"_migrate_schema() - old schema detected, migrating to new schema")

                # Backup all data
                self.cursor.execute(f"SELECT chart_id, date, sys_col, value FROM {self.TABLE_DATA_POINTS}")
                data_backup = self.cursor.fetchall()

                self.cursor.execute(f"SELECT * FROM {self.TABLE_CHART_METADATA}")
                metadata_backup = self.cursor.fetchall()

                # Get column names for metadata
                self.cursor.execute(f"PRAGMA table_info({self.TABLE_CHART_METADATA})")
                metadata_cols = [row[1] for row in self.cursor.fetchall()]

                # Drop old tables
                self.cursor.execute(f"DROP TABLE IF EXISTS {self.TABLE_DATA_POINTS}")
                self.cursor.execute(f"DROP TABLE IF EXISTS {self.TABLE_CHART_METADATA}")
                self.cursor.execute(f"DROP TABLE IF EXISTS {self.TABLE_CHART_SYNC}")
                self.cursor.execute(f"DROP TABLE IF EXISTS {self.TABLE_TOMBSTONES}")

                # Recreate tables with new schema
                for table_name in self.SCHEMA_DEFINITIONS:
                    sql = self._get_create_table_sql(table_name)
                    self.cursor.execute(sql)

                # Restore data
                if data_backup:
                    self.cursor.executemany(
                        f"INSERT INTO {self.TABLE_DATA_POINTS} (chart_id, date, sys_col, value) VALUES (?, ?, ?, ?)",
                        data_backup
                    )

                if metadata_backup:
                    # Map old columns to new schema
                    for row in metadata_backup:
                        old_data = dict(zip(metadata_cols, row))
                        self.cursor.execute(
                            f"INSERT INTO {self.TABLE_CHART_METADATA} (chart_id, metadata, thumbnail, metadata_hash, last_modified, owner, accepting_changes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                old_data.get('chart_id'),
                                old_data.get('metadata'),
                                old_data.get('thumbnail'),
                                old_data.get('metadata_hash'),
                                old_data.get('last_modified', 0),
                                old_data.get('owner'),
                                old_data.get('accepting_changes', 0)
                            )
                        )

                self.connection.commit()
                debug_print(f"_migrate_schema() - migration complete, restored {len(data_backup)} data points")
        except sqlite3.Error as e:
            debug_print(f"_migrate_schema() - error: {e}")

    def _get_current_table_columns(self, table_name):
        """Get current columns in a table."""
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            return {row[1]: row[2] for row in self.cursor.fetchall()}  # {name: type}
        except sqlite3.OperationalError:
            return {}

    def _remove_deprecated_columns(self):
        """Remove columns that are no longer in schema (if supported)."""
        deprecated = {'chart': ['machine_id']}  # Add deprecated columns here

        for table_name, cols_to_remove in deprecated.items():
            current_columns = self._get_current_table_columns(table_name)
            expected_columns = {k for k in self.SCHEMA_DEFINITIONS[table_name].keys()
                                if not k.startswith('_')}

            for col_name in cols_to_remove:
                if col_name in current_columns and col_name not in expected_columns:
                    try:
                        self.cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {col_name}")
                    except sqlite3.OperationalError:
                        pass  # SQLite version doesn't support DROP COLUMN

    def _ensure_connection(self):
        """Ensure database connection is established."""
        if not self.initialized:
            return self.connect()
        return True

    def _get_current_user_name(self):
        """Get current user name from preferences"""
        return self.data_manager.user_preferences.get(
            'user_name',
            self.data_manager.get_default_user_name()
        )

    def execute_with_retry(self, query, params=None, fetch=None):
        """Execute SQL query with connection retry and error handling"""
        if not self._ensure_connection():
            return None

        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            if fetch == 'one':
                return self.cursor.fetchone()
            elif fetch == 'all':
                return self.cursor.fetchall()
            elif fetch == 'many':
                return self.cursor.fetchmany()

            return True
        except sqlite3.Error as e:
            debug_print(f"Database error: {e}")
            return None

    def execute_transaction(self, operations):
        if not self._ensure_connection():
            return False

        try:
            # TRANSACTION STEP TRACKING: Log each SQL statement execution
            for i, operation in enumerate(operations):
                query = operation['query']
                params = operation.get('params')
                
                # Log the operation being executed
                query_type = query.split()[0].upper()
                debug_print(f"execute_transaction - STEP_{i+1}: {query_type}")
                
                # FOREIGN KEY/CONSTRAINT CHECKING: Enable detailed error reporting
                self.cursor.execute("PRAGMA foreign_keys = ON")
                
                try:
                    if params:
                        self.cursor.execute(query, params)
                    else:
                        self.cursor.execute(query)
                    
                    # SQL EXECUTION VERIFICATION: Log affected row counts
                    affected_rows = self.cursor.rowcount
                    debug_print(f"execute_transaction - STEP_{i+1}_rows: {affected_rows}")
                    
                    # IMMEDIATE ROW COUNT CHECK: For INSERT operations, verify data was inserted
                    if query_type == "INSERT" and "data_points" in query.lower():
                        # Extract chart_id from the INSERT statement for verification
                        if "SELECT '" in query:
                            # For unsync operations with SELECT subquery
                            start_idx = query.find("SELECT '") + 8
                            end_idx = query.find("'", start_idx)
                            target_chart_id = query[start_idx:end_idx]
                            
                            # Verify rows were actually inserted
                            verify_cursor = self.connection.cursor()
                            verify_cursor.execute(f"SELECT COUNT(*) FROM {self.TABLE_DATA_POINTS} WHERE chart_id = ?", (target_chart_id,))
                            actual_count = verify_cursor.fetchone()[0]
                            debug_print(f"execute_transaction - STEP_{i+1}_verify_count: {actual_count}")
                        
                except sqlite3.Error as step_error:
                    debug_print(f"execute_transaction - STEP_{i+1}_error: {str(step_error)}")
                    # Check for constraint violations or other SQL errors
                    if "constraint" in str(step_error).lower():
                        debug_print(f"execute_transaction - CONSTRAINT_violation: {str(step_error)[:100]}")
                    raise step_error

            self.connection.commit()
            debug_print(f"execute_transaction - COMMIT_success: {len(operations)} operations")
            return True
            
        except sqlite3.Error as e:
            debug_print(f"execute_transaction - ERROR: {str(e)}")
            # Log specific error types
            if "constraint" in str(e).lower():
                debug_print(f"execute_transaction - CONSTRAINT_error: {str(e)[:100]}")
            elif "syntax" in str(e).lower():
                debug_print(f"execute_transaction - SYNTAX_error: {str(e)[:100]}")
            elif "database" in str(e).lower():
                debug_print(f"execute_transaction - DATABASE_error: {str(e)[:100]}")
                
            try:
                self.connection.rollback()
                debug_print(f"execute_transaction - ROLLBACK_success")
            except Exception as rollback_error:
                debug_print(f"execute_transaction - ROLLBACK_error: {str(rollback_error)[:50]}")
            return False

    def prepare_metadata(self, chart_data=None):
        """Prepare metadata for storage (removes raw_data)."""
        metadata = copy.deepcopy(chart_data or self.data_manager.chart_data)
        metadata.pop('raw_data', None)
        metadata.pop('owner', None)  # Use DB column instead
        return json.dumps(json.loads(json.dumps(metadata, default=str)))

    def calculate_metadata_hash(self, metadata_json):
        """Calculate MD5 hash of metadata."""
        return hashlib.md5(metadata_json.encode('utf-8')).hexdigest()

    def ensure_remote_columns(self, remote_cursor):
        """Ensure remote database matches schema using same definitions."""
        user_name = self._get_current_user_name()

        for table_name, expected_schema in self.SCHEMA_DEFINITIONS.items():
            # Get remote columns
            try:
                remote_cursor.execute(f"PRAGMA table_info({table_name})")
                current_columns = {row[1]: True for row in remote_cursor.fetchall()}
            except sqlite3.OperationalError:
                current_columns = {}

            # Add missing columns
            for col_name, col_def in expected_schema.items():
                if col_name.startswith('_'):
                    continue
                if col_name not in current_columns:
                    try:
                        remote_cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")
                    except sqlite3.OperationalError:
                        pass

            # Set defaults
            if table_name in self.COLUMN_DEFAULTS:
                for col_name, default_value in self.COLUMN_DEFAULTS[table_name].items():
                    if default_value is None and col_name == 'owner':
                        default_value = user_name

                    remote_cursor.execute(
                        f"UPDATE {table_name} SET {col_name} = ? WHERE {col_name} IS NULL OR {col_name} = ''",
                        (default_value,)
                    )

    def vacuum_database(self, respect_time_limit=True):
        """Vacuum database to reclaim space"""
        if not self.initialized or not self.connection:
            return

        last_vacuum_raw = self.data_manager.event_bus.emit("get_user_preference", ['last_vacuum', 0])
        if isinstance(last_vacuum_raw, str):
            last_vacuum = int(last_vacuum_raw) if last_vacuum_raw.isdigit() else 0
        else:
            last_vacuum = int(last_vacuum_raw)

        current_time = int(time.time())
        one_week_seconds = 7 * 24 * 60 * 60
        time_to_vacuum = current_time - last_vacuum > one_week_seconds

        if not respect_time_limit or time_to_vacuum:
            try:
                # Commit any pending transactions
                try:
                    self.connection.commit()
                except sqlite3.Error:
                    try:
                        self.connection.rollback()
                    except sqlite3.Error:
                        pass

                # Set autocommit mode for VACUUM
                original_isolation = self.connection.isolation_level
                self.connection.isolation_level = None

                self.cursor.execute("VACUUM")

                # Restore normal transaction mode
                self.connection.isolation_level = original_isolation or ""

                # Update last vacuum timestamp
                self.data_manager.event_bus.emit("update_user_preference", ['last_vacuum', current_time])
                self.data_manager.user_preferences['last_vacuum'] = current_time
                self.data_manager.save_user_preferences()

            except sqlite3.Error:
                # Ensure isolation level is restored
                try:
                    self.connection.isolation_level = original_isolation or ""
                except:
                    pass

    def cleanup_journal(self):
        """Clean up database journal files."""
        try:
            self.cursor.execute("PRAGMA journal_mode=DELETE")
            self.cursor.execute("PRAGMA wal_checkpoint(FULL)")
        except sqlite3.Error as e:
            debug_print(f"Error cleaning up journal: {e}")

    def create_tables_for_remote(self, remote_cursor):
        """Create tables on remote using same schema definitions."""
        for table_name in self.SCHEMA_DEFINITIONS:
            sql = self._get_create_table_sql(table_name)
            remote_cursor.execute(sql)

        # Set defaults
        user_name = self._get_current_user_name()
        if 'chart' in self.COLUMN_DEFAULTS:
            for col_name, default_value in self.COLUMN_DEFAULTS['chart'].items():
                if default_value is None and col_name == 'owner':
                    default_value = user_name

                remote_cursor.execute(
                    f"UPDATE chart SET {col_name} = ? WHERE {col_name} IS NULL OR {col_name} = ''",
                    (default_value,)
                )

        remote_cursor.connection.commit()


class TombstoneManager:
    def __init__(self, db: 'SQLiteDatabase', data_manager):
        self.db = db
        self.data_manager = data_manager

    def is_tombstoned(self, remote_cursor, chart_id):
        """Check if a chart_id is tombstoned in the remote database"""
        try:
            # Use centralized schema to create tombstones table
            sql = self.db._get_create_table_sql(self.db.TABLE_TOMBSTONES)
            remote_cursor.execute(sql)

            remote_cursor.execute(f"SELECT 1 FROM {self.db.TABLE_TOMBSTONES} WHERE chart_id = ?", (chart_id,))
            found = remote_cursor.fetchone() is not None
            
            # Extract location from the connection if possible, or use generic identifier
            location = "drive1"  # Default fallback since we can't easily extract from cursor
            debug_print(f"is_tombstoned - chart=\"{chart_id}\", location=\"{location}\", found={found}")
            return found
        except:
            return False

    def add_tombstone_to_remote(self, location_key, chart_id):
        """Add tombstone to remote database with timestamp"""
        db_locations = self.data_manager.user_preferences.get('db_location', {})
        location_path = db_locations.get(location_key)

        if not location_path or not Path(location_path).exists():
            return

        remote_db_path = Path(location_path) / f'{self.db.DB_NAME}-{location_key}.db'

        if remote_db_path.exists():
            try:
                with sqlite3.connect(str(remote_db_path)) as remote_conn:
                    remote_cursor = remote_conn.cursor()

                    # Use centralized schema to create tombstones table
                    sql = self.db._get_create_table_sql(self.db.TABLE_TOMBSTONES)
                    remote_cursor.execute(sql)

                    current_time = int(time.time())
                    remote_cursor.execute(
                        f"INSERT OR IGNORE INTO {self.db.TABLE_TOMBSTONES} (chart_id, added) VALUES (?, ?)",
                        (chart_id, current_time)
                    )
                    remote_conn.commit()
            except Exception as e:
                debug_print(f"Error adding tombstone to {location_key}: {e}")

    def process_tombstones(self, remote_cursor):
        """Process tombstones: delete local charts and remove from remote"""
        try:
            # Use centralized schema to create tombstones table
            sql = self.db._get_create_table_sql(self.db.TABLE_TOMBSTONES)
            remote_cursor.execute(sql)

            remote_cursor.execute(f"SELECT chart_id FROM {self.db.TABLE_TOMBSTONES}")
            tombstoned_chart_ids = [row[0] for row in remote_cursor.fetchall()]
            
            # Extract location from remote cursor if possible, or use generic identifier
            location = "unknown_location"  # Default fallback since we can't easily extract from cursor
            try:
                # Try to get location from connection string if available
                connection_name = str(remote_cursor.connection)
                if "opencelerator-" in connection_name:
                    location = connection_name.split("opencelerator-")[1].split(".db")[0]
            except:
                pass
            
            debug_print(f"process_tombstones - location=\"{location}\", tombstones_found={len(tombstoned_chart_ids)}")
            
            # Log first 3 tombstoned chart IDs for debugging
            first_three_ids = tombstoned_chart_ids[:3] if tombstoned_chart_ids else []
            debug_print(f"process_tombstones - tombstoned_chart_ids={first_three_ids}")

            for tombstone_chart_id in tombstoned_chart_ids:
                # Delete local chart
                local_result = self.db.execute_with_retry(
                    f"SELECT chart_id FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                    (tombstone_chart_id,),
                    fetch='one'
                )

                if local_result:
                    chart_id = local_result[0]
                    debug_print(f"process_tombstones - deleting local chart \"{chart_id}\"")
                    self.db.execute_with_retry(
                        f"DELETE FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?",
                        (chart_id,)
                    )
                    self.db.execute_with_retry(
                        f"DELETE FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                        (chart_id,)
                    )
                    self.db.execute_with_retry(
                        f"DELETE FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ?",
                        (chart_id,)
                    )

                # Delete remote chart
                remote_cursor.execute(
                    f"SELECT chart_id FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                    (tombstone_chart_id,)
                )
                remote_result = remote_cursor.fetchone()

                if remote_result:
                    chart_id = remote_result[0]
                    debug_print(f"process_tombstones - deleting remote chart \"{chart_id}\"")
                    remote_cursor.execute(f"DELETE FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?", (chart_id,))
                    remote_cursor.execute(f"DELETE FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?", (chart_id,))

            remote_cursor.connection.commit()
            if self.db.connection:
                self.db.connection.commit()

        except Exception as e:
            debug_print(f"Error processing tombstones: {e}")

    def add_tombstones_for_chart_deletion(self, chart_id, chart_owner):
        """Add tombstones to all remote locations when a chart is deleted by its owner"""
        current_user_name = self.db._get_current_user_name()

        # Only add tombstones if we are the owner
        if chart_owner != current_user_name:
            return

        sync_results = self.db.execute_with_retry(
            f"SELECT sync_location FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ?",
            (chart_id,),
            fetch='all'
        )

        if sync_results:
            sync_locations = [row[0] for row in sync_results]
            tombstones_created = 0
            for location in sync_locations:
                self.add_tombstone_to_remote(location, chart_id)
                tombstones_created += 1
            debug_print(f"add_tombstones_for_chart_deletion - chart_id=\"{chart_id}\", owner=\"{chart_owner}\", locations_count={len(sync_locations)}, tombstones_created={tombstones_created}")
            
            # Now that tombstones have been created, delete the sync records
            self.db.execute_with_retry(
                f"DELETE FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ?",
                (chart_id,)
            )
            if self.db.connection:
                self.db.connection.commit()
        else:
            debug_print(f"add_tombstones_for_chart_deletion - chart_id=\"{chart_id}\", owner=\"{chart_owner}\", locations_count=0, tombstones_created=0")


class ChartRepository:
    # Manages chart data persistence, metadata handling, and chart-specific business logic.
    # Handles chart CRUD operations, permissions, and import/export functionality.

    def __init__(self, db: 'SQLiteDatabase', data_manager, event_bus):
        self.db = db
        self.data_manager = data_manager
        self.event_bus = event_bus

    def save_complete_chart(self):
        """Save complete chart (data + metadata) to database."""

        # Validation: Reject save if chart_id is null/empty
        chart_id = self.data_manager.chart_data['chart_file_path']
        if not chart_id or (isinstance(chart_id, str) and not chart_id.strip()):
            debug_print('save_complete_chart - ERROR: chart_id is null or empty, rejecting save')
            return False
        else:
            debug_print('save complete chart ran')

        df_data = self.data_manager.df_raw.copy()
        chart_data = copy.deepcopy(self.data_manager.chart_data)

        permissions = self._get_save_permissions(chart_id)
        last_modified = int(time.time())
        self.event_bus.emit("update_chart_data", ['data_modified', last_modified])

        if not permissions['can_save']:
            return False

        operations = [
            {'query': f"DELETE FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?", 'params': (chart_id,)},
            {'query': f"DELETE FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?", 'params': (chart_id,)},
        ]

        # Add data point operations
        if not df_data.empty:
            data_rows = self._prepare_data_points(chart_id, df_data)
            for row in data_rows:
                operations.append({
                    'query': f"INSERT INTO {self.db.TABLE_DATA_POINTS} (chart_id, date, sys_col, value) VALUES (?, ?, ?, ?)",
                    'params': row
                })

        # Add metadata operation
        metadata_json = self.db.prepare_metadata(chart_data)
        metadata_hash = self.db.calculate_metadata_hash(metadata_json)
        thumbnail_data = self.data_manager.event_bus.emit('get_thumbnail', {'size': (96, 96)})

        operations.append({
            'query': f"""INSERT OR REPLACE INTO {self.db.TABLE_CHART_METADATA} 
                        (chart_id, metadata, thumbnail, metadata_hash, last_modified, owner, accepting_changes) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
            'params': (chart_id, metadata_json, thumbnail_data, metadata_hash, last_modified,
                       permissions['preserve_owner'], permissions['preserve_accepting_changes'])
        })

        success = self.db.execute_transaction(operations)

        if success:
            self.db.cleanup_journal()
            # Return data for sync operations
            return {
                'chart_id': chart_id,
                'df_data': df_data,
                'chart_data': chart_data,
                'permissions': permissions
            }

        return False

    def load_chart_data(self, chart_id):
        """Load chart data from database and return as DataFrame."""
        debug_print(f"load_chart_data() - attempting to load chart: \"{chart_id}\"")
        
        # Check if chart exists in database first
        chart_exists = self.db.execute_with_retry(
            f"SELECT COUNT(*) FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
            (chart_id,),
            fetch='one'
        )
        
        if chart_exists and chart_exists[0] > 0:
            debug_print(f"load_chart_data() - chart \"{chart_id}\" found in database")
        else:
            debug_print(f"load_chart_data() - chart \"{chart_id}\" NOT found in database")
            # List all available charts for debugging
            all_charts = self.db.execute_with_retry(
                f"SELECT chart_id FROM {self.db.TABLE_CHART_METADATA}",
                fetch='all'
            )
            available_chart_ids = [row[0] for row in all_charts] if all_charts else []
            debug_print(f"load_chart_data() - available charts in database: {available_chart_ids}")

        # Load data points including id
        results = self.db.execute_with_retry(
            f"SELECT id, date, sys_col, value FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?",  # Added 'id'
            (chart_id,),
            fetch='all'
        )

        # Load metadata
        metadata_loaded = self._load_chart_metadata(chart_id)
        debug_print(f"load_chart_data() - metadata loaded successfully: {metadata_loaded}")

        if not results:
            debug_print(f"load_chart_data() - no data points found for chart \"{chart_id}\"")
            return pd.DataFrame()

        debug_print(f"load_chart_data() - found {len(results)} data points for chart \"{chart_id}\"")
        return self._build_dataframe_from_series_table(results)

    def delete_chart(self, chart_id):
        """Delete chart data and metadata from database."""
        chart_id = self._extract_chart_id(chart_id)

        if not self.db._ensure_connection():
            return False

        try:
            # Get chart owner and sync count
            result = self.db.execute_with_retry(
                f"SELECT owner FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )
            chart_owner = result[0] if result else None
            
            # Get sync count before deletion
            sync_results = self.db.execute_with_retry(
                f"SELECT COUNT(*) FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )
            sync_count = sync_results[0] if sync_results else 0

            operations = [
                {'query': f"DELETE FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?", 'params': (chart_id,)},
                {'query': f"DELETE FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?", 'params': (chart_id,)},
            ]

            success = self.db.execute_transaction(operations)

            if success:
                debug_print(f"delete_chart - chart_id=\"{chart_id}\", owner=\"{chart_owner}\", sync_count={sync_count}")
                # Return info needed for tombstone creation
                return {
                    'success': True,
                    'chart_owner': chart_owner,
                    'chart_id': chart_id
                }

            return {'success': False}

        except Exception as e:
            debug_print(f"Error deleting chart data: {e}")
            return {'success': False}

    def has_chart_changed(self, chart_id):
        """Check if current chart data differs from stored version."""
        if not self.db._ensure_connection():
            return True

        try:
            result = self.db.execute_with_retry(
                f"SELECT metadata_hash, owner, accepting_changes FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )

            if not result:
                return True

            stored_hash, owner, accepting_changes = result
            current_user_name = self.db._get_current_user_name()

            # If user is not the owner and chart is not accepting changes, return False
            is_owner = (owner == current_user_name)
            can_save = is_owner or bool(accepting_changes)

            if not can_save:
                return False

            current_metadata_json = self.db.prepare_metadata()
            current_hash = self.db.calculate_metadata_hash(current_metadata_json)

            return stored_hash != current_hash

        except Exception as e:
            debug_print(f"Error checking if chart has changed: {e}")
            return True

    def get_chart_metadata(self, chart_id):
        """Get chart metadata including thumbnail"""
        if not self.db._ensure_connection():
            return None

        try:
            result = self.db.execute_with_retry(
                f"SELECT metadata, thumbnail FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )

            if result:
                metadata_json, thumbnail_data = result
                metadata = json.loads(metadata_json)
                return {'metadata': metadata, 'thumbnail': thumbnail_data}

            return None
        except Exception as e:
            debug_print(f"Error retrieving chart metadata for {chart_id}: {e}")
            return None

    def get_chart_thumbnail(self, chart_id):
        """Get chart thumbnail from database."""
        chart_id = self._extract_chart_id(chart_id)

        result = self.db.execute_with_retry(
            f"SELECT thumbnail FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
            (chart_id,),
            fetch='one'
        )

        return result[0] if result and result[0] else None

    def get_chart_permissions(self, chart_id):
        """Get permission information for a chart"""
        if not self.db._ensure_connection():
            return {'is_owner': False, 'has_write_access': False, 'accepting_changes': False}

        try:
            result = self.db.execute_with_retry(
                f"SELECT owner, accepting_changes FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )

            if not result:
                return {'is_owner': False, 'has_write_access': False, 'accepting_changes': False}

            owner, accepting_changes = result
            current_user_name = self.db._get_current_user_name()

            is_owner = (owner == current_user_name)
            has_write_access = is_owner or bool(accepting_changes)

            return {
                'is_owner': is_owner,
                'has_write_access': has_write_access,
                'accepting_changes': bool(accepting_changes)
            }

        except Exception as e:
            debug_print(f"Error getting permissions for chart {chart_id}: {e}")
            return {'is_owner': False, 'has_write_access': False, 'accepting_changes': False}

    def get_chart_display_info(self, chart_ids):
        """Get display information for a list of chart IDs including ownership"""
        if not self.db._ensure_connection():
            return {}

        if not chart_ids:
            return {}

        chart_info = {}
        current_user_name = self.db._get_current_user_name()

        for chart_id in chart_ids:
            try:
                result = self.db.execute_with_retry(
                    f"SELECT owner FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                    (chart_id,),
                    fetch='one'
                )

                if result:
                    owner = result[0] or current_user_name
                    is_owner = (owner == current_user_name)
                    chart_info[chart_id] = {
                        'owner': owner,
                        'is_owner': is_owner
                    }

            except Exception as e:
                debug_print(f"Error getting chart info for {chart_id}: {e}")

        return chart_info

    def get_all_chart_ids(self):
        """Get list of all chart IDs in database."""
        if not self.db._ensure_connection():
            return []

        results = self.db.execute_with_retry(
            f"SELECT DISTINCT chart_id FROM {self.db.TABLE_CHART_METADATA}",
            fetch='all'
        )

        return [row[0] for row in results] if results else []

    def get_chart_ids_for_location(self, location):
        """Get chart IDs for a specific location"""
        if not self.db._ensure_connection():
            return []

        try:
            if location == 'local':
                # Get synced charts
                synced_results = self.db.execute_with_retry(
                    f"SELECT DISTINCT chart_id FROM {self.db.TABLE_CHART_SYNC}",
                    fetch='all'
                )
                synced_charts = {row[0] for row in synced_results} if synced_results else set()

                # Get all charts
                all_results = self.db.execute_with_retry(
                    f"SELECT chart_id FROM {self.db.TABLE_CHART_METADATA}",
                    fetch='all'
                )
                all_charts = [row[0] for row in all_results] if all_results else []

                return [chart for chart in all_charts if chart not in synced_charts]
            else:
                # Get charts synced to specific location
                results = self.db.execute_with_retry(
                    f"SELECT DISTINCT chart_id FROM {self.db.TABLE_CHART_SYNC} WHERE sync_location = ?",
                    (location,),
                    fetch='all'
                )
                return [row[0] for row in results] if results else []
        except Exception as e:
            debug_print(f"Error getting chart IDs for location {location}: {e}")
            return []

    def json_import(self, data):
        """Import JSON file to database"""
        json_file_path = data['json_file_path']
        base_chart_id = data['chart_id']

        # Always generate a fresh timestamp for imports
        # Remove existing timestamp if present (only if suffix after underscore is all digits)
        if '_' in base_chart_id:
            parts = base_chart_id.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                # Rightmost part is all digits (timestamp), remove it
                clean_base_name = parts[0]
            else:
                # Rightmost part is not a timestamp, keep whole name
                clean_base_name = base_chart_id
        else:
            clean_base_name = base_chart_id

        # Always append current timestamp
        chart_id = f"{clean_base_name}_{int(time.time())}"

        try:
            with open(json_file_path, 'r') as file:
                loaded_chart = json.load(file)
        except json.JSONDecodeError:
            # File is corrupted, attempt to repair it
            loaded_chart = self.data_manager.file_manager._repair_corrupted_chart_file(json_file_path)
            # Notify user about the repair
            repair_data = {
                'title': "Corrupted Chart File",
                'message': f"The chart file was corrupted and has been repaired. Some settings may have been reset to defaults.",
                'options': ['OK']
            }
            self.event_bus.emit('trigger_user_prompt', repair_data)
        except FileNotFoundError:
            debug_print(f"File not found: {json_file_path}")
            return False

        # Clean the chart data
        clean_chart_data = self.data_manager.file_manager.chart_cleaning(loaded_chart, chart_id)

        # Process raw_data if it exists
        raw_data = clean_chart_data.get('raw_data')

        # If raw_data is not available, try using the legacy Backup field
        if not raw_data:
            backup_data = clean_chart_data.get('Backup')
            if backup_data:
                # Migrate the data to the new raw_data field
                clean_chart_data['raw_data'] = backup_data
                raw_data = backup_data

        if raw_data:
            try:
                # Convert stored JSON data back to a DataFrame
                df = pd.DataFrame.from_records(raw_data)

                # Convert 'd' column to datetime
                if 'd' in df.columns:
                    df['d'] = pd.to_datetime(df['d'])

                # Save to database with renewed hash
                return self._save_imported_chart(chart_id, df, clean_chart_data)
            except Exception as e:
                debug_print(f"Error importing JSON chart to database: {e}")
                return False
        else:
            # For empty charts with no data
            empty_df = pd.DataFrame()
            return self._save_imported_chart(chart_id, empty_df, clean_chart_data)

    def json_export(self, data):
        """Export chart from database to JSON file"""
        chart_id = data['chart_id']
        file_path = data['file_path']

        try:
            # Get chart metadata from database
            metadata_result = self.db.execute_with_retry(
                f"SELECT metadata FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )

            if not metadata_result:
                debug_print(f"Chart metadata not found for chart_id: {chart_id}")
                return False

            # Parse the metadata JSON
            try:
                chart_json = json.loads(metadata_result[0])
            except json.JSONDecodeError as e:
                debug_print(f"Error parsing chart metadata JSON for {chart_id}: {e}")
                return False

            # Get chart data points from database
            data_points_result = self.db.execute_with_retry(
                f"SELECT date, sys_col, value FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?",
                (chart_id,),
                fetch='all'
            )

            # Convert data points back to DataFrame format and add to raw_data
            if data_points_result:
                # Group data points by date
                dates = sorted(set(row[0] for row in data_points_result))
                columns = set(row[1] for row in data_points_result)

                # Build raw_data structure
                raw_data = {'d': dates}
                for col in columns:
                    raw_data[col] = [None] * len(dates)

                # Fill in the data
                date_to_index = {date: idx for idx, date in enumerate(dates)}
                for date, col, value in data_points_result:
                    raw_data[col][date_to_index[date]] = value

                chart_json['raw_data'] = raw_data
            else:
                chart_json['raw_data'] = {}

            # Write to file with proper formatting
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(chart_json, f, indent=2, ensure_ascii=False)

            debug_print(f"Successfully exported chart {chart_id} to {file_path}")
            return True

        except Exception as e:
            debug_print(f"Error exporting chart from database: {e}")
            return False

    def unsync_chart(self, chart_id):
        """Remove chart from sync by renaming chart_id to new local name and handling remote deletion."""
        chart_id = self._extract_chart_id(chart_id)

        if not self.db._ensure_connection():
            return False

        try:
            # Get chart owner and sync locations before rename
            result = self.db.execute_with_retry(
                f"SELECT owner FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )
            chart_owner = result[0] if result else None

            sync_results = self.db.execute_with_retry(
                f"SELECT sync_location FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ?",
                (chart_id,),
                fetch='all'
            )
            sync_locations = [row[0] for row in sync_results] if sync_results else []

            # Create new chart_id with timestamp
            new_timestamp = str(int(time.time()))
            if '_' in chart_id:
                base_name = chart_id.rsplit('_', 1)[0]
                new_chart_id = f"{base_name}_{new_timestamp}"
            else:
                new_chart_id = f"{chart_id}_{new_timestamp}"

            # Update chart_file_path in metadata JSON
            metadata_result = self.db.execute_with_retry(
                f"SELECT metadata FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )

            if not metadata_result:
                return {'success': False}

            metadata_dict = json.loads(metadata_result[0])
            metadata_dict['chart_file_path'] = new_chart_id
            updated_metadata = json.dumps(metadata_dict)
            new_metadata_hash = hashlib.md5(updated_metadata.encode('utf-8')).hexdigest()

            operations = [
                # Update chart_id in data points table
                {
                    'query': f"UPDATE {self.db.TABLE_DATA_POINTS} SET chart_id = ? WHERE chart_id = ?",
                    'params': (new_chart_id, chart_id)
                },
                # Update chart_id and metadata in chart table
                {
                    'query': f"UPDATE {self.db.TABLE_CHART_METADATA} SET chart_id = ?, metadata = ?, metadata_hash = ? WHERE chart_id = ?",
                    'params': (new_chart_id, updated_metadata, new_metadata_hash, chart_id)
                },
                # Delete sync records for original chart_id
                {
                    'query': f"DELETE FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ?",
                    'params': (chart_id,)
                }
            ]

            # Execute transaction
            success = self.db.execute_transaction(operations)

            if success:
                # Add tombstones to remote databases
                current_user_name = self.db._get_current_user_name()
                if chart_owner == current_user_name:
                    for location in sync_locations:
                        self.db.data_manager.sqlite_manager.tombstone_manager.add_tombstone_to_remote(location,
                                                                                                      chart_id)

                # self.data_manager.chart_data['chart_file_path'] = new_chart_id
                return {
                    'success': True,
                    'new_chart_id': new_chart_id,
                    'original_chart_id': chart_id,
                    'chart_owner': chart_owner
                }

            return {'success': False}

        except Exception as e:
            return {'success': False}
    def is_chart_synced(self, chart_id):
        """Check if a chart is in the sync table"""
        if not self.db._ensure_connection():
            return False

        result = self.db.execute_with_retry(
            f"SELECT 1 FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ? LIMIT 1",
            (chart_id,),
            fetch='one'
        )

        return result is not None

    def toggle_accepting_changes(self, chart_id):
        """Toggle accepting_changes for a specific chart"""
        if not self.db._ensure_connection():
            return False

        try:
            # Get current state
            result = self.db.execute_with_retry(
                f"SELECT accepting_changes FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )

            if not result:
                return False

            current_state = bool(result[0])
            new_state = 0 if current_state else 1

            # Update local
            success = self.db.execute_with_retry(
                f"UPDATE {self.db.TABLE_CHART_METADATA} SET accepting_changes = ? WHERE chart_id = ?",
                (new_state, chart_id)
            )

            if success:
                self.db.connection.commit()
                return {
                    'success': True,
                    'chart_id': chart_id,
                    'new_state': new_state
                }

            return {'success': False}

        except Exception as e:
            debug_print(f"Error toggling accepting_changes for chart {chart_id}: {e}")
            return {'success': False}

    def update_username_ownership(self, data):
        """Update username in preferences and database"""
        old_username = data['old_username']
        new_username = data['new_username']

        if not self.db._ensure_connection():
            return False

        try:
            # Update user preferences
            self.data_manager.user_preferences['user_name'] = new_username
            self.data_manager.save_user_preferences()

            # Update local database ownership
            operations = [
                {
                    'query': f"UPDATE {self.db.TABLE_CHART_METADATA} SET owner = ? WHERE owner = ?",
                    'params': (new_username, old_username)
                }
            ]

            success = self.db.execute_transaction(operations)

            if success:
                return {
                    'success': True,
                    'old_username': old_username,
                    'new_username': new_username
                }

            return {'success': False}

        except Exception as e:
            debug_print(f"Error updating username ownership: {e}")
            return {'success': False}

    # Private helper methods
    def _get_save_permissions(self, chart_id):
        """Extract permission bools needed for save operations."""
        current_user_name = self.db._get_current_user_name()

        result = self.db.execute_with_retry(
            f"SELECT owner, accepting_changes FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
            (chart_id,),
            fetch='one'
        )

        if result:
            existing_owner, existing_accepting_changes = result
            is_owner = (existing_owner == current_user_name)
            is_existing_chart = True
            can_save = is_owner or existing_accepting_changes
            preserve_owner = existing_owner
            preserve_accepting_changes = existing_accepting_changes
        else:
            is_owner = True
            is_existing_chart = False
            can_save = True
            preserve_owner = current_user_name
            preserve_accepting_changes = 0

        return {
            'is_owner': is_owner,
            'is_existing_chart': is_existing_chart,
            'can_save': can_save,
            'preserve_owner': preserve_owner,
            'preserve_accepting_changes': preserve_accepting_changes
        }

    def _prepare_data_points(self, chart_id, df_data):
        # Transform DataFrame from wide format to long format for database storage.
        # Converts DataFrame rows (one per date with multiple value columns) into individual database rows (one per date-column-value).

        rows = []
        for _, row in df_data.iterrows():
            date = row['d'].strftime('%Y-%m-%d') if hasattr(row['d'], 'strftime') else str(row['d'])

            for col in row.index:
                if col == 'd':  # Skip the date column itself
                    continue

                value = row[col]
                # Convert NaN to None, non-NaN to float (if not already None)
                processed_value = None if pd.isna(value) else float(value)
                rows.append((chart_id, date, col, processed_value))

        return rows

    def _build_dataframe_from_series_table(self, results):
        if not results:
            return pd.DataFrame()

        # Determine the columns
        sys_col_idx = 2
        all_sys_cols = []
        for r in results:
            sys_col = r[sys_col_idx]
            if sys_col not in all_sys_cols:
                all_sys_cols.append(sys_col)
            else:
                break

        n_cols = len(all_sys_cols)
        rows = []

        # Iterate results in chunks of size n_cols
        for i in range(0, len(results), n_cols):
            chunk = results[i:i + n_cols]
            if len(chunk) != n_cols:
                # handle incomplete row if needed
                continue

            row = {"d": chunk[0][1]}  # date is in index 1
            for r in chunk:
                col = r[2]
                val = r[3]
                row[col] = val
            rows.append(row)

        df = pd.DataFrame(rows)
        df["d"] = pd.to_datetime(df["d"])
        df = df.reset_index(drop=True)

        return df


    def _load_chart_metadata(self, chart_id):
        """Load chart metadata from database."""
        result = self.db.execute_with_retry(
            f"SELECT metadata FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
            (chart_id,),
            fetch='one'
        )

        if result:
            metadata = json.loads(result[0])
            raw_data = self.data_manager.chart_data.get('raw_data', {})
            self.data_manager.chart_data.update(metadata)
            self.data_manager.chart_data['raw_data'] = raw_data
            return True
        return False

    def _extract_chart_id(self, chart_id):
        """Extract chart ID from various input formats"""
        return chart_id  # Placeholder - implement based on original logic

    def _get_unique_chart_id(self, base_chart_id):
        """Generate unique chart_id by adding timestamp suffix if needed"""
        if not self.db._ensure_connection():
            return base_chart_id

        # Check if base chart_id exists
        result = self.db.execute_with_retry(
            f"SELECT chart_id FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
            (base_chart_id,),
            fetch='one'
        )

        # If it doesn't exist, use the base name
        if not result:
            return base_chart_id

        # If it exists, add timestamp suffix
        timestamp = str(int(time.time()))
        return f"{base_chart_id}_{timestamp}"

    def _save_imported_chart(self, chart_id, df_data, chart_data):
        """Save imported chart with renewed metadata hash"""
        # Update chart_data to reflect the potentially new chart_id
        # chart_data['chart_file_path'] = chart_id

        # Get current permissions
        permissions = self._get_save_permissions(chart_id)

        if not permissions['can_save']:
            return False

        operations = [
            {'query': f"DELETE FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?", 'params': (chart_id,)},
            {'query': f"DELETE FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?", 'params': (chart_id,)},
        ]

        # Add data point operations
        if not df_data.empty:
            data_rows = self._prepare_data_points(chart_id, df_data)
            for row in data_rows:
                operations.append({
                    'query': f"INSERT INTO {self.db.TABLE_DATA_POINTS} (chart_id, date, sys_col, value) VALUES (?, ?, ?, ?)",
                    'params': row
                })

        # Prepare metadata and create renewed hash
        metadata_json = self.db.prepare_metadata(chart_data)
        original_hash = self.db.calculate_metadata_hash(metadata_json)

        # Create renewed hash: hash(timestamp + original_hash)
        timestamp = str(int(time.time()))
        renewed_hash_input = f"{timestamp}{original_hash}"
        renewed_hash = hashlib.md5(renewed_hash_input.encode('utf-8')).hexdigest()
        hash_prefix = renewed_hash[:8]

        thumbnail_data = self.data_manager.event_bus.emit('get_thumbnail', {'size': (96, 96)})
        last_modified = int(time.time())

        operations.append({
            'query': f"""INSERT OR REPLACE INTO {self.db.TABLE_CHART_METADATA} 
                        (chart_id, metadata, thumbnail, metadata_hash, last_modified, owner, accepting_changes) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
            'params': (chart_id, metadata_json, thumbnail_data, renewed_hash, last_modified,
                       permissions['preserve_owner'], permissions['preserve_accepting_changes'])
        })

        # Get database file modification time before transaction
        try:
            db_path = self.db.data_manager.get_config_directory(as_str=True)
            db_file_path = os.path.join(db_path, f"{self.db.DB_NAME}.db")
            debug_print(f"save_imported_chart - writing to database file: {db_file_path}")
            if os.path.exists(db_file_path):
                mod_time_before = os.path.getmtime(db_file_path)
                debug_print(f"save_imported_chart - db file mod time before: {mod_time_before}")
            else:
                debug_print(f"save_imported_chart - db file does not exist before transaction")
                mod_time_before = None
        except Exception as e:
            debug_print(f"save_imported_chart - error getting mod time before: {e}")
            mod_time_before = None

        debug_print(f"save_imported_chart - attempting database transaction")
        success = self.db.execute_transaction(operations)
        debug_print(f"save_imported_chart - transaction_success={success}")

        # Get database file modification time after transaction
        try:
            if os.path.exists(db_file_path):
                mod_time_after = os.path.getmtime(db_file_path)
                debug_print(f"save_imported_chart - db file mod time after: {mod_time_after}")
                if mod_time_before is not None:
                    mod_time_changed = mod_time_after != mod_time_before
                    debug_print(f"save_imported_chart - db file modified: {mod_time_changed}")
            else:
                debug_print(f"save_imported_chart - db file does not exist after transaction")
        except Exception as e:
            debug_print(f"save_imported_chart - error getting mod time after: {e}")

        if success:
            self.db.cleanup_journal()
            debug_print(f"save_imported_chart - cleanup completed")
            debug_print(f"save_imported_chart - chart_id=\"{chart_id}\", hash_prefix=\"{hash_prefix}\"")
            return {
                'success': True,
                'chart_id': chart_id,
                'df_data': df_data,
                'chart_data': chart_data,
                'permissions': permissions
            }

        return False


class SyncManager:
    # Manages bidirectional synchronization with remote databases.
    # Handles conflict resolution, chart sharing, and remote database operations.

    def __init__(self, db: 'SQLiteDatabase', chart_repo: 'ChartRepository', tombstone_manager: 'TombstoneManager', data_manager, event_bus):
        self.db = db
        self.chart_repo = chart_repo
        self.tombstone_manager = tombstone_manager
        self.data_manager = data_manager
        self.event_bus = event_bus

    def sync_remotes(self):
        """Bidirectional sync of charts marked for sharing with remote databases."""
        debug_print('sync remotes ran')
        if not self.db._ensure_connection():
            return False

        db_locations = self.data_manager.user_preferences.get('db_location', {})
        remote_locations = {k: v for k, v in db_locations.items() if k != 'local'}

        for location_key, location_path in remote_locations.items():
            if not location_path or not Path(location_path).exists():
                continue

            self.resolve_db_conflict(location_path, location_key)
            db_path = Path(location_path) / f'{self.db.DB_NAME}-{location_key}.db'

            if not db_path.exists():
                self.create_remote_db(location_key, location_path)

            if db_path.exists():
                self._sync_with_remote(location_key, db_path)

        return True

    def share_chart_to_location(self, data):
        """Share a chart to the specified location"""
        chart_id = data['chart_id']
        location = data['location']

        if not self.db._ensure_connection():
            return False

        try:
            # Get actual chart_id
            result = self.db.execute_with_retry(
                f"SELECT chart_id FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                (chart_id,),
                fetch='one'
            )

            if not result:
                return False

            actual_chart_id = result[0]

            # Check if already synced
            existing = self.db.execute_with_retry(
                f"SELECT chart_id FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ? AND sync_location = ?",
                (actual_chart_id, location),
                fetch='one'
            )

            if existing:
                return False

            # Add to sync table (no hash needed)
            success = self.db.execute_with_retry(
                f"INSERT INTO {self.db.TABLE_CHART_SYNC} (chart_id, sync_location, last_sync) VALUES (?, ?, ?)",
                (actual_chart_id, location, 0)
            )

            if success:
                self.db.connection.commit()

                # Push to shared location
                df_data = self.chart_repo.load_chart_data(actual_chart_id)
                if df_data is None:
                    df_data = pd.DataFrame()

                metadata_result = self.db.execute_with_retry(
                    f"SELECT metadata FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                    (actual_chart_id,),
                    fetch='one'
                )

                if metadata_result:
                    chart_metadata = json.loads(metadata_result[0])
                    self._push_to_shared_locations(actual_chart_id, df_data, chart_metadata)

                return True

            return False

        except Exception as e:
            debug_print(f"Error sharing chart {chart_id} to {location}: {e}")
            return False

    def push_chart_changes(self, save_result):
        """Push chart changes to shared locations after save"""
        if not save_result or not isinstance(save_result, dict):
            return False

        chart_id = save_result.get('chart_id')
        df_data = save_result.get('df_data')
        chart_data = save_result.get('chart_data')
        permissions = save_result.get('permissions')

        if chart_id and self.chart_repo.is_chart_synced(chart_id):
            return self._push_to_shared_locations(chart_id, df_data, chart_data, permissions)

        return True

    def push_accepting_changes(self, toggle_result):
        """Push accepting_changes toggle to remote databases"""
        if not toggle_result or not toggle_result.get('success'):
            return False

        chart_id = toggle_result['chart_id']
        new_state = toggle_result['new_state']

        return self._push_accepting_changes_to_remotes(chart_id, new_state)

    def push_username_changes(self, update_result):
        """Push username changes to all remote databases"""
        if not update_result or not update_result.get('success'):
            return False

        old_username = update_result['old_username']
        new_username = update_result['new_username']

        return self._push_username_to_remotes(old_username, new_username)

    def handle_chart_deletion(self, delete_result):
        """Handle chart deletion with tombstone creation"""
        if not delete_result or not delete_result.get('success'):
            return False

        chart_id = delete_result['chart_id']
        chart_owner = delete_result['chart_owner']

        self.tombstone_manager.add_tombstones_for_chart_deletion(chart_id, chart_owner)
        return True

    def handle_chart_unsync(self, unsync_result):
        """Handle chart unsyncing by deleting original and creating tombstones"""
        if not unsync_result or not unsync_result.get('success'):
            return False

        original_chart_id = unsync_result['original_chart_id']

        # Delete the original synced chart
        delete_result = self.chart_repo.delete_chart(original_chart_id)
        if delete_result.get('success'):
            tombstone_result = self.handle_chart_deletion(delete_result)
            debug_print(f"handle_chart_unsync - copy=success, delete=success, tombstone={'success' if tombstone_result else 'fail'}")
            return True

        # If deletion failed, rollback the copy
        new_chart_id = unsync_result['new_chart_id']
        rollback_ops = [
            {'query': f"DELETE FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?",
             'params': (new_chart_id,)},
            {'query': f"DELETE FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
             'params': (new_chart_id,)},
        ]
        self.db.execute_transaction(rollback_ops)
        debug_print(f"handle_chart_unsync - copy=success, delete=fail, tombstone=fail")
        return False

    def create_remote_db(self, location_key, location_path):
        """Create a new remote database at the specified location."""
        db_filename = f'{self.db.DB_NAME}-{location_key}.db'
        remote_db_path = Path(location_path) / db_filename

        remote_db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with sqlite3.connect(str(remote_db_path)) as remote_conn:
                remote_cursor = remote_conn.cursor()
                # Use centralized schema from SQLiteDatabase
                self.db.create_tables_for_remote(remote_cursor)

            debug_print(f"Created remote database: {remote_db_path}")
            return True

        except Exception as e:
            debug_print(f"Failed to create remote database: {e}")
            return False

    def resolve_db_conflict(self, location_path, location_key):
        """Resolve sync conflicts by merging database files, preserving conflicting versions with prefixes."""
        location_path = Path(location_path)
        db_files = list(location_path.glob(f"{self.db.DB_NAME}*.db"))

        if len(db_files) <= 1:
            return True

        main_db_name = f"{self.db.DB_NAME}-{location_key}.db"
        main_db = location_path / main_db_name

        if main_db not in db_files:
            return False

        conflict_dbs = [f for f in db_files if f != main_db]

        try:
            all_charts = {}  # chart_id -> list of versions with metadata

            # Collect all chart versions from all database files
            for db_file in db_files:
                with sqlite3.connect(str(db_file)) as conn:
                    cursor = conn.cursor()
                    self.db.ensure_remote_columns(cursor)

                    cursor.execute(f"""
                        SELECT chart_id, metadata, thumbnail, metadata_hash, 
                               COALESCE(last_modified, 0) as last_modified,
                               COALESCE(owner, ?) as owner,
                               COALESCE(accepting_changes, 0) as accepting_changes
                        FROM {self.db.TABLE_CHART_METADATA}
                    """, (self.db._get_current_user_name(),))

                    for chart_id, metadata, thumbnail, hash_val, timestamp, owner, accepting_changes in cursor.fetchall():
                        cursor.execute(
                            f"SELECT date, sys_col, value FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?",
                            (chart_id,))
                        data_points = cursor.fetchall()

                        chart_version = {
                            'metadata': metadata,
                            'thumbnail': thumbnail,
                            'hash': hash_val,
                            'timestamp': timestamp,
                            'owner': owner,
                            'accepting_changes': accepting_changes,
                            'data_points': data_points
                        }

                        if chart_id not in all_charts:
                            all_charts[chart_id] = []
                        all_charts[chart_id].append(chart_version)

            # Process each chart to determine conflict resolution strategy
            charts_to_save = {}  # final_chart_id -> chart_data

            for chart_id, versions in all_charts.items():
                # Get unique timestamps
                unique_timestamps = list(set(version['timestamp'] for version in versions))

                if len(unique_timestamps) == 1:
                    # No timestamp conflict - all versions agree, save any one
                    charts_to_save[chart_id] = versions[0]
                    debug_print(
                        f"resolve_db_conflict - chart '{chart_id}': no conflict (timestamp={unique_timestamps[0]})")
                else:
                    # Timestamp conflict - preserve all versions
                    unique_timestamps.sort(reverse=True)  # Newest first
                    newest_timestamp = unique_timestamps[0]

                    # Save the newest version with original chart_id
                    newest_version = next(v for v in versions if v['timestamp'] == newest_timestamp)
                    charts_to_save[chart_id] = newest_version

                    # Save older versions with conflict_ prefix
                    older_versions = [v for v in versions if v['timestamp'] != newest_timestamp]
                    for i, older_version in enumerate(older_versions):
                        # Create conflict chart_id with prefix
                        if len(older_versions) == 1:
                            conflict_chart_id = f"conflict_{chart_id}"
                        else:
                            conflict_chart_id = f"conflict_{i + 1}_{chart_id}"

                        # Update metadata to reflect new chart_id
                        try:
                            metadata_dict = json.loads(older_version['metadata'])
                            metadata_dict['chart_file_path'] = conflict_chart_id
                            older_version['metadata'] = json.dumps(metadata_dict)

                            # Recalculate metadata hash for the updated metadata
                            older_version['hash'] = hashlib.md5(older_version['metadata'].encode('utf-8')).hexdigest()
                        except (json.JSONDecodeError, KeyError):
                            # If metadata parsing fails, continue with original metadata
                            pass

                        charts_to_save[conflict_chart_id] = older_version

                    debug_print(
                        f"resolve_db_conflict - chart '{chart_id}': conflict resolved, saved {len(older_versions)} older versions with conflict_ prefix")

            # Rebuild main database with all resolved charts
            with sqlite3.connect(str(main_db)) as main_conn:
                main_cursor = main_conn.cursor()
                self.db.ensure_remote_columns(main_cursor)

                # Clear existing data
                main_cursor.execute(f"DELETE FROM {self.db.TABLE_DATA_POINTS}")
                main_cursor.execute(f"DELETE FROM {self.db.TABLE_CHART_METADATA}")

                # Insert all resolved charts
                for final_chart_id, chart_data in charts_to_save.items():
                    main_cursor.execute(f"""
                        INSERT INTO {self.db.TABLE_CHART_METADATA} 
                        (chart_id, metadata, thumbnail, metadata_hash, last_modified, owner, accepting_changes) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (final_chart_id, chart_data['metadata'], chart_data['thumbnail'], chart_data['hash'],
                          chart_data['timestamp'], chart_data['owner'], chart_data['accepting_changes']))

                    if chart_data['data_points']:
                        # Update data points to use the final_chart_id
                        main_cursor.executemany(f"""
                            INSERT INTO {self.db.TABLE_DATA_POINTS} (chart_id, date, sys_col, value) 
                            VALUES (?, ?, ?, ?)
                        """, [(final_chart_id, date, sys_col, value) for date, sys_col, value in
                              chart_data['data_points']])

                main_conn.commit()

            # Delete conflict files
            for conflict_db in conflict_dbs:
                conflict_db.unlink()

            debug_print(
                f"resolve_db_conflict - merged {len(db_files)} database files into {len(charts_to_save)} charts")
            return True

        except Exception as e:
            debug_print(f"Conflict resolution failed: {e}")
            return False

    # Private sync implementation methods
    def _sync_with_remote(self, location_key, remote_db_path):
        """Sync charts marked for this location with remote database."""
        with sqlite3.connect(str(remote_db_path)) as remote_conn:
            remote_cursor = remote_conn.cursor()

            self.db.ensure_remote_columns(remote_cursor)
            self.tombstone_manager.process_tombstones(remote_cursor)
            self._discover_new_shared_charts(location_key, remote_cursor)

            # Get charts marked for sync
            charts_results = self.db.execute_with_retry(
                f"SELECT chart_id FROM {self.db.TABLE_CHART_SYNC} WHERE sync_location = ?",
                (location_key,),
                fetch='all'
            )

            if not charts_results:
                return

            chart_ids = [row[0] for row in charts_results]

            if not chart_ids:
                return

            # Sync each marked chart
            for chart_id in chart_ids:
                if self.tombstone_manager.is_tombstoned(remote_cursor, chart_id):
                    continue

                # Get timestamps directly
                local_result = self.db.execute_with_retry(
                    f"SELECT last_modified FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                    (chart_id,),
                    fetch='one'
                )
                local_timestamp = local_result[0] if local_result else 0

                remote_cursor.execute(f"SELECT last_modified FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                                      (chart_id,))
                remote_row = remote_cursor.fetchone()
                remote_timestamp = remote_row[0] if remote_row else 0

                debug_print(f"[SYNC DEBUG] Chart {chart_id}: local={local_timestamp}, remote={remote_timestamp}")

                if local_timestamp == remote_timestamp:
                    debug_print(f"[SYNC DEBUG] Timestamps equal, no sync needed")
                elif local_timestamp > remote_timestamp:
                    debug_print(f"[SYNC DEBUG] Local newer, copying to remote")
                    debug_print(f"_sync_with_remote - location=\"{location_key}\", chart=\"{chart_id}\", direction=\"local_newer\"")
                    self._copy_chart(chart_id, self.db.cursor, remote_cursor)
                else:
                    debug_print(f"[SYNC DEBUG] Remote newer, copying to local")
                    debug_print(f"_sync_with_remote - location=\"{location_key}\", chart=\"{chart_id}\", direction=\"remote_newer\"")
                    self._copy_chart(chart_id, remote_cursor, self.db.cursor)

    def _discover_new_shared_charts(self, location_key, remote_cursor):
        """Discover charts in remote that aren't in chart_sync and add them"""
        try:
            current_user_name = self.db._get_current_user_name()

            remote_cursor.execute(
                f"SELECT chart_id, COALESCE(owner, '') as owner FROM {self.db.TABLE_CHART_METADATA}"
            )
            remote_charts = remote_cursor.fetchall()

            synced_results = self.db.execute_with_retry(
                f"SELECT chart_id FROM {self.db.TABLE_CHART_SYNC} WHERE sync_location = ?",
                (location_key,),
                fetch='all'
            )
            synced_chart_ids = {row[0] for row in synced_results} if synced_results else set()

            new_charts = []
            for chart_id, owner in remote_charts:
                if chart_id not in synced_chart_ids:
                    new_charts.append(chart_id)

            # Add new charts to sync (no hash needed)
            operations = []
            for chart_id in new_charts:
                operations.append({
                    'query': f"INSERT INTO {self.db.TABLE_CHART_SYNC} (chart_id, sync_location, last_sync) VALUES (?, ?, ?)",
                    'params': (chart_id, location_key, 0)
                })

            if operations:
                self.db.execute_transaction(operations)
                debug_print(f"Discovered {len(new_charts)} new shared charts from other owners for {location_key}")
                debug_print(f"_discover_new_shared_charts - location=\"{location_key}\", remote_count={len(remote_charts)}, new_count={len(new_charts)}")
            else:
                debug_print(f"_discover_new_shared_charts - location=\"{location_key}\", remote_count={len(remote_charts)}, new_count=0")

        except Exception as e:
            debug_print(f"Error discovering new charts: {e}")

    def _copy_chart(self, chart_id, from_cursor, to_cursor):
        """Copy chart from one database to another."""
        from_cursor.execute(f"SELECT * FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?", (chart_id,))
        row = from_cursor.fetchone()
        if not row:
            return

        from_cursor.execute(f"PRAGMA table_info({self.db.TABLE_CHART_METADATA})")
        from_columns = [col[1] for col in from_cursor.fetchall()]
        chart_data = dict(zip(from_columns, row))

        from_cursor.execute(f"SELECT date, sys_col, value FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?",
                            (chart_id,))
        data_points = from_cursor.fetchall()

        # Delete existing data
        to_cursor.execute(f"DELETE FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?", (chart_id,))
        to_cursor.execute(f"DELETE FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?", (chart_id,))

        # Ensure target has all columns
        self.db.ensure_remote_columns(to_cursor)

        # Insert metadata
        to_cursor.execute(f"""
            INSERT OR REPLACE INTO {self.db.TABLE_CHART_METADATA} 
            (chart_id, metadata, thumbnail, metadata_hash, last_modified, owner, accepting_changes) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            chart_data['chart_id'],
            chart_data['metadata'],
            chart_data['thumbnail'],
            chart_data['metadata_hash'],
            chart_data.get('last_modified', int(time.time())),
            chart_data.get('owner', self.db._get_current_user_name()),
            chart_data.get('accepting_changes', 0)
        ))

        # Insert data points
        if data_points:
            to_cursor.executemany(f"INSERT INTO {self.db.TABLE_DATA_POINTS} (chart_id, date, sys_col, value) VALUES (?, ?, ?, ?)",
                                  [(chart_id, date, sys_col, value) for date, sys_col, value in data_points])

        to_cursor.connection.commit()

    def _update_sync_record(self, chart_id, location_key):
        """Update chart_sync table with latest sync timestamp."""
        current_time = int(time.time())
        self.db.execute_with_retry(
            f"UPDATE {self.db.TABLE_CHART_SYNC} SET last_sync = ? WHERE chart_id = ? AND sync_location = ?",
            (current_time, chart_id, location_key)
        )
        self.db.connection.commit()

    def _push_to_shared_locations(self, chart_id, df_data, chart_data, permissions=None):
        """Push updated chart to all locations where it's shared"""
        if not self.db._ensure_connection():
            return False

        try:
            if permissions is None:
                permissions = self.chart_repo._get_save_permissions(chart_id)

            if not permissions['can_save']:
                return False

            # Get sync locations
            sync_results = self.db.execute_with_retry(
                f"SELECT sync_location FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ?",
                (chart_id,),
                fetch='all'
            )

            if not sync_results:
                return True

            sync_locations = [row[0] for row in sync_results]
            db_locations = self.data_manager.user_preferences.get('db_location', {})

            for location_key in sync_locations:
                location_path = db_locations.get(location_key)

                if not location_path or not Path(location_path).exists():
                    continue

                db_path = Path(location_path) / f'{self.db.DB_NAME}-{location_key}.db'

                if not db_path.exists():
                    continue

                self._push_chart_to_remote_db(chart_id, df_data, chart_data, db_path, location_key)

            return True

        except Exception as e:
            debug_print(f"Error in _push_to_shared_locations: {e}")
            return False

    def _push_chart_to_remote_db(self, chart_id, df_data, chart_data, db_path, location_key):
        """Push a single chart to a remote database"""
        try:
            self.event_bus.emit('mark_local_db_change')

            with sqlite3.connect(str(db_path)) as remote_conn:
                remote_cursor = remote_conn.cursor()

                # Ensure remote has new columns
                self.db.ensure_remote_columns(remote_cursor)

                # Check if tombstoned
                if self.tombstone_manager.is_tombstoned(remote_cursor, chart_id):
                    return

                # Delete existing data
                remote_cursor.execute(f"DELETE FROM {self.db.TABLE_DATA_POINTS} WHERE chart_id = ?", (chart_id,))
                remote_cursor.execute(f"DELETE FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?", (chart_id,))

                # Insert data points
                if not df_data.empty:
                    data_rows = self.chart_repo._prepare_data_points(chart_id, df_data)
                    remote_cursor.executemany(
                        f"INSERT OR REPLACE INTO {self.db.TABLE_DATA_POINTS} (chart_id, date, sys_col, value) VALUES (?, ?, ?, ?)",
                        data_rows
                    )

                # Get complete metadata from local database
                local_result = self.db.execute_with_retry(
                    f"SELECT metadata, thumbnail, metadata_hash, last_modified, owner, accepting_changes FROM {self.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                    (chart_id,),
                    fetch='one'
                )

                if local_result:
                    metadata_json, thumbnail_data, metadata_hash, last_modified, owner, accepting_changes = local_result

                    remote_cursor.execute(
                        f"INSERT OR REPLACE INTO {self.db.TABLE_CHART_METADATA} (chart_id, metadata, thumbnail, metadata_hash, last_modified, owner, accepting_changes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            chart_id, metadata_json, thumbnail_data, metadata_hash, last_modified, owner,
                            accepting_changes)
                    )

                    remote_conn.commit()

                    # Update local sync record (only timestamp, no hash)
                    self._update_sync_record(chart_id, location_key)

        except Exception as e:
            debug_print(f"Error pushing chart {chart_id} to {location_key}: {e}")

    def _push_accepting_changes_to_remotes(self, chart_id, accepting_changes_value):
        """Push accepting_changes boolean update to remote databases for a specific chart"""
        self.event_bus.emit('mark_local_db_change')

        if not self.db._ensure_connection():
            return False

        try:
            # Empty if chart id not in chart_sync table
            sync_results = self.db.execute_with_retry(
                f"SELECT sync_location FROM {self.db.TABLE_CHART_SYNC} WHERE chart_id = ?",
                (chart_id,),
                fetch='all'
            )

            if not sync_results:
                return True

            sync_locations = [row[0] for row in sync_results]
            db_locations = self.data_manager.user_preferences.get('db_location', {})

            for location_key in sync_locations:
                location_path = db_locations.get(location_key)

                if not location_path or not Path(location_path).exists():
                    continue

                db_path = Path(location_path) / f'{self.db.DB_NAME}-{location_key}.db'

                if not db_path.exists():
                    continue

                try:
                    with sqlite3.connect(str(db_path)) as remote_conn:
                        remote_cursor = remote_conn.cursor()
                        self.db.ensure_remote_columns(remote_cursor)

                        # Update accepting_changes and last_modified timestamp
                        current_time = int(time.time())
                        remote_cursor.execute(
                            f"UPDATE {self.db.TABLE_CHART_METADATA} SET accepting_changes = ?, last_modified = ? WHERE chart_id = ?",
                            (accepting_changes_value, current_time, chart_id)
                        )

                        remote_conn.commit()

                except Exception as e:
                    debug_print(f"Error pushing accepting_changes for chart {chart_id} to {location_key}: {e}")

            return True

        except Exception as e:
            debug_print(f"Error in _push_accepting_changes_to_remotes: {e}")
            return False

    def _push_username_to_remotes(self, old_username, new_username):
        """Push username changes to all remote databases"""
        self.event_bus.emit('mark_local_db_change')

        if not self.db._ensure_connection():
            return False

        try:
            db_locations = self.data_manager.user_preferences.get('db_location', {})
            sync_locations = [loc for loc in db_locations.keys() if loc != 'local']

            for location_key in sync_locations:
                location_path = db_locations.get(location_key)

                if not location_path or not Path(location_path).exists():
                    continue

                db_path = Path(location_path) / f'{self.db.DB_NAME}-{location_key}.db'

                if not db_path.exists():
                    continue

                try:
                    with sqlite3.connect(str(db_path)) as remote_conn:
                        remote_cursor = remote_conn.cursor()
                        self.db.ensure_remote_columns(remote_cursor)

                        # Update username in remote database
                        remote_cursor.execute(
                            f"UPDATE {self.db.TABLE_CHART_METADATA} SET owner = ? WHERE owner = ?",
                            (new_username, old_username)
                        )

                        remote_conn.commit()
                        debug_print(f"Updated username in remote database: {location_key}")

                except Exception as e:
                    debug_print(f"Error updating username in remote database {location_key}: {e}")

            return True

        except Exception as e:
            debug_print(f"Error in _push_username_to_remotes: {e}")
            return False


class DatabaseMonitor:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.event_bus = EventBus()
        self.timer = QTimer()
        self.timer.setInterval(10 * 1000)  # 10 second interval as ms
        self.timer.timeout.connect(self.check_databases)
        self.monitoring_active = False
        self.ignore_next_change = False  # Ignore next change cycle

        # Event bus subscriptions
        self.event_bus.subscribe('mark_local_db_change', self.mark_local_db_change)
        debug_print(f"[DB Monitor] Initialized with 5s interval")

    def start_monitoring(self):
        """Start monitoring all remote databases"""
        db_locations = self.data_manager.user_preferences.get('db_location', {})
        remote_locations = {k: v for k, v in db_locations.items() if k != 'local'}

        debug_print(
            f"[DB Monitor] Starting monitoring. Found {len(remote_locations)} remote locations: {list(remote_locations.keys())}")

        self.ignore_next_change = False
        found_dbs = 0

        for location_key, location_path in remote_locations.items():
            if not location_path or not Path(location_path).exists():
                debug_print(f"[DB Monitor] Location '{location_key}' path does not exist: {location_path}")
                continue

            db_path = Path(location_path) / f'{self.data_manager.sqlite_manager.db.DB_NAME}-{location_key}.db'
            if db_path.exists():
                found_dbs += 1
                debug_print(f"[DB Monitor] Found database: {db_path}")
            else:
                debug_print(f"[DB Monitor] Database not found: {db_path}")

        if remote_locations:
            self.monitoring_active = True
            self.timer.start()
            debug_print(f"[DB Monitor] Started monitoring {found_dbs} databases")
            return True
        else:
            debug_print(f"[DB Monitor] No remote locations to monitor")
            return False

    def stop_monitoring(self):
        """Stop monitoring databases"""
        debug_print(f"[DB Monitor] Stopping monitoring")
        self.timer.stop()
        self.monitoring_active = False
        self.ignore_next_change = False

    def mark_local_db_change(self):
        """Mark to ignore next change cycle"""
        debug_print(f"[DB Monitor] Marked to ignore next change cycle")
        self.ignore_next_change = True

    def check_databases(self):
        """Check if any monitored databases have changes in synced charts"""
        if not self.monitoring_active:
            return

        db_locations = self.data_manager.user_preferences.get('db_location', {})
        remote_locations = {k: v for k, v in db_locations.items() if k != 'local'}

        changes_detected = False

        for location_key, location_path in remote_locations.items():
            if not location_path or not Path(location_path).exists():
                continue

            db_path = Path(location_path) / f'{self.data_manager.sqlite_manager.db.DB_NAME}-{location_key}.db'
            if not db_path.exists():
                continue

            # Check for timestamp differences
            if self._has_timestamp_differences(location_key, db_path):
                changes_detected = True
                debug_print(f"[DB Monitor] Chart changes detected in {location_key}")

                if self.ignore_next_change:
                    debug_print(f"[DB Monitor] Ignoring change (local modification)")
                    self.ignore_next_change = False
                else:
                    debug_print(f"[DB Monitor] External chart changes detected - triggering sync")
                    self.event_bus.emit('sync_remotes')

                    # After sync, check if current chart metadata has changed
                    self._check_current_chart_metadata_change()
                    return

        if not changes_detected:
            debug_print(f"[DB Monitor] Checked {len(remote_locations)} databases - no chart changes")

    def _has_timestamp_differences(self, location_key, db_path):
        """Check if any synced chart has different timestamps between local and remote"""
        if not self.data_manager.sqlite_manager.db._ensure_connection():
            return False

        try:
            # Get charts that are synced to this location
            synced_results = self.data_manager.sqlite_manager.db.execute_with_retry(
                f"SELECT chart_id FROM {self.data_manager.sqlite_manager.db.TABLE_CHART_SYNC} WHERE sync_location = ?",
                (location_key,),
                fetch='all'
            )

            if not synced_results:
                return False

            synced_chart_ids = [row[0] for row in synced_results]

            # Connect to remote database
            with sqlite3.connect(str(db_path)) as remote_conn:
                remote_cursor = remote_conn.cursor()

                # Check each synced chart for timestamp differences
                for chart_id in synced_chart_ids:
                    # Get local timestamp
                    local_result = self.data_manager.sqlite_manager.db.execute_with_retry(
                        f"SELECT last_modified FROM {self.data_manager.sqlite_manager.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                        (chart_id,),
                        fetch='one'
                    )
                    local_timestamp = local_result[0] if local_result else 0

                    # Get remote timestamp
                    remote_cursor.execute(
                        f"SELECT last_modified FROM {self.data_manager.sqlite_manager.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
                        (chart_id,)
                    )
                    remote_result = remote_cursor.fetchone()
                    remote_timestamp = remote_result[0] if remote_result else 0

                    # If timestamps differ, we have changes
                    if local_timestamp != remote_timestamp:
                        debug_print(f"[DB Monitor] Timestamp difference for chart {chart_id}: local={local_timestamp}, remote={remote_timestamp}")
                        return True

            return False

        except Exception as e:
            debug_print(f"[DB Monitor] Error checking timestamps for {location_key}: {e}")
            return False

    def _check_current_chart_metadata_change(self):
        """Check if the currently viewed chart's metadata has changed after sync"""
        current_chart_id = self.data_manager.chart_data.get('chart_file_path')

        if not current_chart_id:
            return  # No chart currently loaded

        # Get the chart_data timestamp (data_modified)
        chart_data_timestamp = self.data_manager.chart_data.get('data_modified', 0)

        # Get the database timestamp (last_modified)
        result = self.data_manager.sqlite_manager.db.execute_with_retry(
            f"SELECT last_modified FROM {self.data_manager.sqlite_manager.db.TABLE_CHART_METADATA} WHERE chart_id = ?",
            (current_chart_id,),
            fetch='one'
        )

        if result:
            db_timestamp = result[0] or 0

            # Convert to int for comparison (in case chart_data_timestamp is string)
            chart_data_timestamp = int(chart_data_timestamp) if chart_data_timestamp else 0
            db_timestamp = int(db_timestamp) if db_timestamp else 0

            if db_timestamp != chart_data_timestamp:
                debug_print(f"[DB Monitor] Current chart timestamps differ - reloading chart")
                debug_print(f"  Chart data timestamp: {chart_data_timestamp}")
                debug_print(f"  Database timestamp: {db_timestamp}")

                # Reload the current chart
                self.event_bus.emit('load_chart', current_chart_id)

    def refresh_monitoring(self):
        """Refresh the list of databases being monitored"""
        debug_print(f"[DB Monitor] Refreshing monitoring")
        if self.monitoring_active:
            self.stop_monitoring()
            self.start_monitoring()


class SQLiteManager:
    # Facade class that coordinates the refactored database components.
    # Maintains the original interface for backward compatibility.

    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.event_bus = EventBus()

        # Initialize component classes
        self.db = SQLiteDatabase(data_manager)
        self.tombstone_manager = TombstoneManager(self.db, data_manager)
        self.chart_repo = ChartRepository(self.db, data_manager, self.event_bus)
        self.sync_manager = SyncManager(self.db, self.chart_repo, self.tombstone_manager, data_manager, self.event_bus)

        # Maintain original properties for compatibility
        self.connection = None
        self.cursor = None
        self.initialized = False

        # Register event subscriptions
        self._register_event_subscriptions()

    def _register_event_subscriptions(self):
        """Register all event bus subscriptions"""
        self.event_bus.subscribe('has_chart_changed', self.has_chart_changed, has_data=True)
        self.event_bus.subscribe('delete_chart', self._handle_delete_chart, has_data=True)
        self.event_bus.subscribe('vacuum_database', self.vacuum_database)
        self.event_bus.subscribe('sync_remotes', self.sync_remotes)
        self.event_bus.subscribe('json_import_to_database', self.json_import, has_data=True)
        self.event_bus.subscribe('json_export_from_database', self.json_export, has_data=True)
        self.event_bus.subscribe('get_chart_ids_for_location', self.get_chart_ids_for_location, has_data=True)
        self.event_bus.subscribe('get_chart_permissions', self.get_chart_permissions, has_data=True)
        self.event_bus.subscribe('get_chart_metadata', self.get_chart_metadata, has_data=True)
        self.event_bus.subscribe('share_chart_to_location', self.share_chart_to_location, has_data=True)
        self.event_bus.subscribe('unsync_chart', self._handle_unsync_chart, has_data=True)
        self.event_bus.subscribe('toggle_accepting_changes', self._handle_toggle_accepting_changes, has_data=True)
        self.event_bus.subscribe('is_chart_synced', self.is_chart_synced, has_data=True)
        self.event_bus.subscribe('update_username_ownership', self._handle_update_username_ownership, has_data=True)
        self.event_bus.subscribe('get_chart_display_info', self.get_chart_display_info, has_data=True)
        self.event_bus.subscribe('save_complete_chart', self._handle_save_complete_chart)

    # Event handler methods that coordinate between components
    def _handle_save_complete_chart(self):
        """Handle save and sync coordination"""
        save_result = self.chart_repo.save_complete_chart()
        if save_result:
            self.sync_manager.push_chart_changes(save_result)
        return save_result

    def _handle_delete_chart(self, chart_id):
        """Handle delete and tombstone coordination"""
        delete_result = self.chart_repo.delete_chart(chart_id)
        if delete_result:
            self.sync_manager.handle_chart_deletion(delete_result)
        return delete_result

    def _handle_unsync_chart(self, chart_id):
        """Handle unsync coordination"""
        unsync_result = self.chart_repo.unsync_chart(chart_id)
        if unsync_result:
            self.sync_manager.handle_chart_unsync(unsync_result)
        return unsync_result

    def _handle_toggle_accepting_changes(self, chart_id):
        """Handle toggle and sync coordination"""
        toggle_result = self.chart_repo.toggle_accepting_changes(chart_id)
        if toggle_result:
            self.sync_manager.push_accepting_changes(toggle_result)
        return toggle_result

    def _handle_update_username_ownership(self, data):
        """Handle username update and sync coordination"""
        update_result = self.chart_repo.update_username_ownership(data)
        if update_result:
            self.sync_manager.push_username_changes(update_result)
        return update_result

    # Direct delegation methods (maintain original interface)
    def connect(self, db_path=None):
        result = self.db.connect(db_path)
        # Update facade properties
        self.connection = self.db.connection
        self.cursor = self.db.cursor
        self.initialized = self.db.initialized
        return result

    def close(self):
        self.db.close()
        self.connection = None
        self.cursor = None
        self.initialized = False

    def vacuum_database(self, respect_time_limit=True):
        return self.db.vacuum_database(respect_time_limit)

    def sync_remotes(self):
        return self.sync_manager.sync_remotes()

    def has_chart_changed(self, chart_id):
        return self.chart_repo.has_chart_changed(chart_id)

    def get_chart_metadata(self, chart_id):
        return self.chart_repo.get_chart_metadata(chart_id)

    def get_chart_permissions(self, chart_id):
        return self.chart_repo.get_chart_permissions(chart_id)

    def get_chart_ids_for_location(self, location):
        return self.chart_repo.get_chart_ids_for_location(location)

    def get_chart_display_info(self, chart_ids):
        return self.chart_repo.get_chart_display_info(chart_ids)

    def is_chart_synced(self, chart_id):
        return self.chart_repo.is_chart_synced(chart_id)

    def json_import(self, data):
        return self.chart_repo.json_import(data)

    def json_export(self, data):
        return self.chart_repo.json_export(data)

    def share_chart_to_location(self, data):
        return self.sync_manager.share_chart_to_location(data)

    def load_chart_data(self, chart_id):
        debug_print('load chart ran')
        return self.chart_repo.load_chart_data(chart_id)

    def get_chart_thumbnail(self, chart_id):
        return self.chart_repo.get_chart_thumbnail(chart_id)

    def get_all_chart_ids(self):
        return self.chart_repo.get_all_chart_ids()

    # Private method access for compatibility (temporary)
    def _ensure_connection(self):
        return self.db._ensure_connection()

    def _execute_with_retry(self, query, params=None, fetch=None):
        return self.db.execute_with_retry(query, params, fetch)

    def _execute_transaction(self, operations):
        return self.db.execute_transaction(operations)

    # Table name access for compatibility
    @property
    def TABLE_DATA_POINTS(self):
        return self.db.TABLE_DATA_POINTS

    @property
    def TABLE_CHART_METADATA(self):
        return self.db.TABLE_CHART_METADATA

    @property
    def TABLE_CHART_SYNC(self):
        return self.db.TABLE_CHART_SYNC

    @property
    def TABLE_TOMBSTONES(self):
        return self.db.TABLE_TOMBSTONES
