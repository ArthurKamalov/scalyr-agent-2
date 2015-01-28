# Copyright 2015 Scalyr Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------
#
# A ScalyrMonitor which monitors the status of PostgreSQL databases.
#
# Note, this can be run in standalone mode by:
#     python -m scalyr_agent.run_monitor scalyr_agent.builtin_monitors.mysql_monitor
import sys
import re
import os
import stat
import errno
import string
from datetime import datetime

from scalyr_agent import ScalyrMonitor, UnsupportedSystem, define_config_option, define_metric, define_log_field

# We must require 2.6 or greater right now because PsycoPG2 requires it.
if sys.version_info[0] < 2 or (sys.version_info[0] == 2 and sys.version_info[1] < 5):
    raise UnsupportedSystem('postgresql_monitor', 'Requires Python 2.5 or greater.')

# We import psycopg2 from the third_party directory.  This
# relies on PYTHONPATH being set up correctly, which is done
# in both agent_main.py and config_main.py
#
# noinspection PyUnresolvedReferences,PyPackageRequirements
import psycopg2

__monitor__ = __name__


define_config_option(__monitor__, 'module',
                     'Always ``scalyr_agent.builtin_monitors.postgres_monitor ``', required_option=True)
define_config_option(__monitor__, 'id',
                     'Optional. Included in each log message generated by this monitor, as a field named ``instance``. '
                     'Allows you to distinguish between values recorded by different monitors. This is especially '
                     'useful if you are running multiple PostgreSQL instances on a single server; you can monitor each '
                     'instance with a separate postgresql_monitor record in the Scalyr Agent configuration.',
                     convert_to=str)
define_config_option(__monitor__, 'database_host',
                     'Name of host machine the agent will connect to PostgreSQL to retrieve monitoring data.',
                     convert_to=str)
define_config_option(__monitor__, 'database_port',
                     'Name of port on the host machine the agent will connect to PostgreSQL to retrieve monitoring data.',
                     convert_to=str)
define_config_option(__monitor__, 'database_name',
                     'Name of database the agent will connect to PostgreSQL to retrieve monitoring data.',
                     convert_to=str)
define_config_option(__monitor__, 'database_username',
                     'Username which the agent uses to connect to PostgreSQL to retrieve monitoring data.',
                     convert_to=str)
define_config_option(__monitor__, 'database_password',
                     'Password for connecting to PostgreSQL.', 
                     convert_to=str)

# Metric definitions.
define_metric(__monitor__, 'postgres.database.connections',
              'The number of current active connections.  The value is accurate to when the check was made.'
              , cumulative=False, category='connections')
define_metric(__monitor__, 'postgres.database.transactions_committed',
              'The number of database transactions that have been committed.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.transactions_rolledback',
              'The number of database transactions that have been rolled back.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.disk_blocks_read',
              'The number of disk blocks read into the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.disk_blocks_hit',
              'The number of disk blocks read that were found in the buffer cache.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.query_rows_returned',
              'The number of rows returned by all queries in the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.query_rows_fetched',
              'The number of rows fetched by all queries in the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.query_rows_inserted',
              'The number of rows inserted by all queries in the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.query_rows_updated',
              'The number of rows updated by all queries in the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.query_rows_deleted',
              'The number of rows deleted by all queries in the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.temp_files',
              'The number of temporary files created by queries to the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.temp_bytes',
              'The total amount of data written to temporary files by queries to the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.temp_bytes',
              'The total amount of data written to temporary files by queries to the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.deadlocks',
              'The number of deadlocks detected in the database.  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.blocks_read_time',
              'The amount of time data file blocks are read by clients in the database (in milliseconds).  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.blocks_write_time',
              'The amount of time data file blocks are written by clients in the database (in milliseconds).  '
              'The value is relative to postgres.database.stats_reset.'
              , cumulative=True, category='general')
define_metric(__monitor__, 'postgres.database.stats_reset',
              'The time at which database statistics were last reset.'
              , cumulative=False, category='general')

define_log_field(__monitor__, 'monitor', 'Always ``postgres_monitor``.')
define_log_field(__monitor__, 'instance', 'The ``id`` value from the monitor configuration.')
define_log_field(__monitor__, 'metric', 'The name of a metric being measured, e.g. "postgres.vars".')
define_log_field(__monitor__, 'value', 'The metric value.')


class PostgreSQLDb(object):
    """ Represents a PopstgreSQL database
    """
    
    _database_stats =  {
        'pg_stat_database': {
          'numbackends' : 'postgres.database.connections',
          'xact_commit' : 'postgres.database.transactions_committed',
          'xact_rollback' : 'postgres.database.transactions_rolledback',
          'blks_read' : 'postgres.database.disk_blocks_read',
          'blks_hit' : 'postgres.database.disk_blocks_hit',
          'tup_returned' : 'postgres.database.query_rows_returned',
          'tup_fetched' : 'postgres.database.query_rows_fetched',
          'tup_inserted' : 'postgres.database.query_rows_inserted',
          'tup_updated' : 'postgres.database.query_rows_updated',
          'tup_deleted' : 'postgres.database.query_rows_deleted',
          'temp_files' : 'postgres.database.temp_files',
          'temp_bytes' : 'postgres.database.temp_bytes',
          'deadlocks' : 'postgres.database.deadlocks',
          'blk_read_time' : 'postgres.database.blocks_read_time',
          'blk_write_time' : 'postgres.database.blocks_write_time',
          'stats_reset' : 'postgres.database.stats_reset'
        }
    }
    
    def _connect(self):
        try:
            conn = psycopg2.connect(self._connection_string)
            self._db = conn
            self._cursor = self._db.cursor()
            self._gather_db_information()                                                   
        except psycopg2.Error, me:
            self._db = None
            self._cursor = None
            self._logger.error("Database connect failed: %s" % me)
        except Exception, ex:
            self._logger.error("Exception trying to connect occured:  %s" % ex)
            raise Exception("Exception trying to connect:  %s" % ex)
        
    def _close(self):
        """Closes the cursor and connection to this PostgreSQL server."""
        if self._cursor:
            self._cursor.close()
        if self._db:
            self._db.close()
        self._cursor = None
        self._db = None
            
    def _reconnect(self):
        """Reconnects to this PostgreSQL server."""
        self._close()
        self._connect()
        
    def _get_version(self):
        version = "unknown"
        try:
            self._cursor.execute("select version();")
            r = self._cursor.fetchone()
            # assumes version is in the form of 'PostgreSQL x.y.z on ...'
            s = string.split(r[0])
            version = s[1]
        except:
            ex = sys.exc_info()[0]
            self._logger.error("Exception getting database version: %s" % ex)
        return version
        
    def _gather_db_information(self):
        self._version = self._get_version()
        try:
            if self._version == "unknown":
              self._major = self._medium = self._minor = 0
            else:
                version = self._version.split(".")
                self._major = int(version[0])
                self._medium = int(version[1])
        except (ValueError, IndexError), e:
            self._major = self._medium = 0
            self._version = "unknown"
        except:
            ex = sys.exc_info()[0]
            self._logger.error("Exception getting database version: %s" % ex)
            self._version = "unknown"
            self._major = self._medium = 0

    def _fields_and_data_to_dict(self, fields, data):
        result = {}
        for f, d in zip(fields, data):
            result[f] = d
        return result

    def _retrieve_database_table_stats(self, table):
        try:
            # get the fields and values
            self._cursor.execute("select * from %s where datname = '%s' limit 0;" % (table, self._database))
            fields = [desc[0] for desc in self._cursor.description];
            self._cursor.execute("select * from %s where datname = '%s';" % (table, self._database))
            data = self._cursor.fetchone()
        except psycopg2.OperationalError, (errcode, msg):
            if errcode != 2006:  # "PostgreSQL server has gone away"
                raise Exception("Database error -- " + errcode)
            self._reconnect()
            return None
  
        # combine the fields and data
        data = self._fields_and_data_to_dict(fields, data)
  
        # extract the ones we want
        return dict([(self._database_stats[table][i], data[i]) for i in self._database_stats[table].keys() if i in data])
        
    def retrieve_database_stats(self):
        result = {}
        for i in self._database_stats.keys():
            tmp = self._retrieve_database_table_stats(i);
            if tmp != None:
                result.update(tmp)
        return result
          
    def __str__(self):
        return "DB(%r:%r, %r)" % (self._host, self._port, self._version)
            
    def __repr__(self):
        return self.__str__()
   
    def __init__(self, host = None, port = None, database = None, username = None, password = None, logger = None):
        """Constructor: 
    
        @param database: database we are connecting to
        @param host: database host being connected to
        @param port: database port being connected to
        @param username: username to connect with
        @param password: password to establish connection
        """
        
        database_connection_config = []
        if host != None:
            database_connection_config.append("host=%s" % host)
        else:
          host = "localhost"
        if port != None:
            database_connection_config.append("port=%s" % port)
        else:
          port = "5432"
        if database != None:
            database_connection_config.append("dbname=%s" % database)
        if username != None:
            database_connection_config.append("user=%s" % username)
        if password != None:
            database_connection_config.append("password=%s" % password)
        
        self._connection_string = string.join(database_connection_config, " ")
        self._host = host
        self._port = port
        self._database = database
        self._logger = logger

        self._connect()
        if self._db is None:
            raise Exception('Unable to connect to db')


class PostgresMonitor(ScalyrMonitor):
    """A Scalyr agent monitor that monitors postgresql databases.
    """
    def _initialize(self):
        """Performs monitor-specific initialization.
        """

        # Useful instance variables:
        #   _sample_interval_secs:  The number of seconds between calls to gather_sample.
        #   _config:  The dict containing the configuration for this monitor instance as retrieved from configuration
        #             file.
        #   _logger:  The logger instance to report errors/warnings/etc.
        
        # determine how we are going to connect
        database = None
        host = None
        port = None
        username = None
        password = None
        if "database_host" in self._config:
            host = self._config["database_host"]
        if "database_port" in self._config:
            port = self._config["database_port"]
        if "database_name" in self._config:
            database = self._config["database_name"]
        if "database_username" in self._config:
            username = self._config["database_username"]
        if "database_password" in self._config:
            password = self._config["database_password"]
        
        if "database_name" not in self._config or "database_username" not in self._config or "database_password" not in self._config:
            raise Exception("database_name, database_username and database_password must be specified in the configuration.")
            
        self._sample_interval_secs = 30 # how often to check the database status    

        self._db = PostgreSQLDb ( database = database,
                                  host = host,
                                  port = port,
                                  username = username,
                                  password = password,
                                  logger = self._logger )


    def gather_sample(self):
        """Invoked once per sample interval to gather a statistic.
        """
        
        def timestamp_ms(dt):
            epoch = datetime(1970, 1, 1, 0, 0, 0, 0, tzinfo=psycopg2.tz.FixedOffsetTimezone(offset=-480, name=None))
            td = dt - epoch
            return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 1e3
        
        dbstats = self._db.retrieve_database_stats()
        if dbstats != None:
            for key in dbstats.keys():
                if key != "postgres.database.stats_reset":
                    self._logger.emit_value(key, dbstats[key])
                else:
                    self._logger.emit_value(key, timestamp_ms(dbstats[key]))
