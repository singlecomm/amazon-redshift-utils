from __future__ import print_function

import os
import sys

# Copyright 2016-2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at
# http://aws.amazon.com/apache2.0/
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

# add the lib directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import boto3
import base64
import pg8000
import datetime
from datetime import timedelta
import json
import config_constants
import pgpasslib

#### Static Configuration
ssl = True
##################

__version__ = "1.0"
debug = False
pg8000.paramstyle = "qmark"


def run_command(cursor, statement):
    if debug:
        print("Running Statement: %s" % statement)

    t = datetime.datetime.now()
    cursor.execute(statement)
    interval = (datetime.datetime.now() - t).microseconds / 1000

    return interval


# nasty hack for backward compatibility, to extract label values from os.environ or event
def get_config_value(labels, configs):
    for l in labels:
        for c in configs:
            if l in c:
                if debug:
                    print("Resolved label value %s from config" % l)

                return c[l]

    return None


def create_schema_objects(cursor, conn):
    with open(os.path.dirname(__file__) + '/lib/history_table_creation.sql', 'r') as sql_file:
        table_creation = sql_file.read()

    for s in table_creation.split(";"):
        stmt = s.strip()
        if s is not None and stmt != "":
            if debug:
                print(stmt)
            try:
                cursor.execute(stmt)
            except Exception as e:
                print(e)
                raise e

    conn.commit()
    if debug:
        print("Successfully verified schema HISTORY & storage tables")


def snapshot_system_tables(cursor, conn, table_config):
    rowcounts = {}
    for t in table_config:
        table = t['table']
        stmt = t['insert']
        if debug:
            print("%s: %s" % (table, stmt))
        cursor.execute(stmt)
        c = cursor.rowcount
        rowcounts[table] = c

        if debug:
            print("%s: %s Rows Created" % (table, c))

    conn.commit()

    return rowcounts


def cleanup_snapshots(cursor, conn, cleanup_after_days, table_config):
    delete_after = (datetime.datetime.now() + timedelta(days=-cleanup_after_days)).strftime('%Y-%m-%d %H:%M:%S')

    if debug:
        print("Deleting history table data older than %s" % delete_after)

    rowcounts = {}
    for s in table_config:
        table = s['table']

        if 'override_sql' in s:
            stmt = s['override_sql'] % delete_after
        else:
            stmt = "delete from history.%s where %s < to_timestamp('%s','yyyy-mm-dd HH:MI:SS')" % (
                table, s['archiveColumn'], delete_after)

        if debug:
            print(stmt)

        cursor.execute(stmt)
        c = cursor.rowcount
        rowcounts[table] = c

        if debug:
            print("%s: %s Rows Deleted" % (table, c))

    conn.commit()

    return rowcounts


def snapshot(config_sources):
    aws_region = get_config_value(['AWS_REGION'], config_sources)

    set_debug = get_config_value(['DEBUG', 'debug', ], config_sources)
    if set_debug is not None and (set_debug or set_debug.upper() == 'TRUE'):
        global debug
        debug = True

    kms = boto3.client('kms', region_name=aws_region)

    if debug:
        print("Connected to AWS KMS & CloudWatch in %s" % aws_region)

    user = get_config_value(['DbUser', 'db_user', 'dbUser'], config_sources)
    host = get_config_value(['HostName', 'cluster_endpoint', 'dbHost', 'db_host'], config_sources)
    port = int(get_config_value(['HostPort', 'db_port', 'dbPort'], config_sources))
    database = get_config_value(['DatabaseName', 'db_name', 'db'], config_sources)

    # we may have been passed the password in the configuration, so extract it if we can
    pwd = get_config_value(['db_pwd'], config_sources)

    # override the password with the contents of .pgpass or environment variables
    try:
        pwd = pgpasslib.getpass(host,port, database,user)
    except pgpasslib.FileNotFound as e:
        pass

    if pwd is None:
        enc_password = get_config_value(['EncryptedPassword', 'encrypted_password', 'encrypted_pwd', 'dbPassword'],
                                        config_sources)
        # resolve the authorisation context, if there is one, and decrypt the password
        auth_context = get_config_value('kms_auth_context', config_sources)

        if auth_context is not None:
            auth_context = json.loads(auth_context)

        try:
            if auth_context is None:
                pwd = kms.decrypt(CiphertextBlob=base64.b64decode(enc_password))[
                    'Plaintext']
            else:
                pwd = kms.decrypt(CiphertextBlob=base64.b64decode(enc_password), EncryptionContext=auth_context)[
                    'Plaintext']
        except:
            print('KMS access failed: exception %s' % sys.exc_info()[1])
            print('Encrypted Password: %s' % enc_password)
            print('Encryption Context %s' % auth_context)
            raise

    # Connect to the cluster
    try:
        if debug:
            print('Connecting to Redshift: %s' % host)

        conn = pg8000.connect(database=database, user=user, password=pwd, host=host, port=port, ssl=ssl)
    except:
        print('Redshift Connection Failed: exception %s' % sys.exc_info()[1])
        raise

    if debug:
        print('Successfully Connected to Cluster')

    # create a new cursor for methods to run through
    cursor = conn.cursor()

    # set application name
    set_name = "set application_name to 'RedshiftSystemTablePersistence-v%s'" % __version__

    if debug:
        print(set_name)

    cursor.execute(set_name)

    # load the table configuration
    table_config = json.load(open(os.path.dirname(__file__) + '/lib/history_table_config.json', 'r'))

    # create the dependent objects if we need to
    create_schema_objects(cursor, conn)

    # snapshot stats into history tables
    insert_rowcounts = snapshot_system_tables(cursor, conn, table_config)

    # cleanup history tables if requested in the configuration
    delete_rowcounts = None
    cleanup_after_days = get_config_value([config_constants.SYSTABLE_CLEANUP_AFTER_DAYS], config_sources)
    if cleanup_after_days is not None:
        try:
            cleanup_after_days = int(cleanup_after_days)
        except ValueError:
            print("Configuration value '%s' must be an integer" % config_constants.SYSTABLE_CLEANUP_AFTER_DAYS)
            raise

        if cleanup_after_days > 0:
            delete_rowcounts = cleanup_snapshots(cursor, conn, cleanup_after_days, table_config)

        cursor.close()
        conn.close()

    return {"inserted": insert_rowcounts, "deleted": delete_rowcounts}
