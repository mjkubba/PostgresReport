#!/usr/bin/env python3

# pg_health_check.py
# Author: MJ Kubba <mjkubba@amazon.com>
# based on work of Vivek Singh
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import getpass
import datetime
import sys
import boto3
import os
import subprocess
import json

subprocess.call('pip install psycopg2-binary -t /tmp/ --no-cache-dir'.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sys.path.insert(1, '/tmp/')
import psycopg2

def check_input(input_obj):
    if "secret" in input_obj:
        return(True)
    else:
        if "endpoint" not in input_obj:
            print("missing endpoint")
            return(False)
        elif "dbname" not in input_obj:
            print("missing dbname")
            return(False)
        elif "rdsport" not in input_obj:
            print("missing rdsport")
            return(False)
        elif "masteruser" not in input_obj:
            print("missing masteruser")
            return(False)
        elif "comname" not in input_obj:
            print("missing comname")
            return(False)
        elif "mypass" not in input_obj:
            print("missing mypass")
            return(False)
        else:
            return(True)

def table_creator(top, headers, cur, sql):
    html = """<font face="verdana" color="#ff6600"> """ + top + """ </font>"""
    html = html + "<br>"
    html = html + """<table border="1"><tr>"""
    for head in headers:
        html = html + "<th>" + head + "</th>"
    html = html + "</tr>"
    try:
        cur.execute(sql)
        for item in cur.fetchall():
            html = html + "<tr>"
            for col in item:
                html = html + "<td>"+str(col)+"</td>"
            html = html + "</tr>"
    except psycopg2.errors.UndefinedFunction:
        cur.execute("ROLLBACK")
        pass
    html = html + "</td></tr></table>"
    html = html + "<br>"
    html = html + "<br>"
    return(html)

def lambda_handler(event, context):
    if event["body"]:
        input_validator=check_input(json.loads(event["body"]))
        db_obj = json.loads(event["body"])
    elif event["queryStringParameters"]:
        input_validator=check_input(event["queryStringParameters"])
        db_obj = event["queryStringParameters"]
    else:
        input_validator=False
    if not input_validator:
        return {
            "statusCode": 400,
            "body": "missing input",
            "headers": {
                'Content-Type': 'text/html',
            }
        }

    rdsclient = boto3.client('rds')

    # """Check for inputs and exit if missing."""
    # if "ENDPOINT" in os.environ:
    #     endpoint = os.getenv("ENDPOINT")
    # else:
    #     print("ENDPOINT not found in ENV")
    #
    # if "DBNAME" in os.environ:
    #     dbname = os.getenv("DBNAME")
    # else:
    #     print("DBNAME not found in ENV")
    #
    # if "DBPORT" in os.environ:
    #     rdsport = os.getenv("DBPORT")
    # else:
    #     print("DBPORT not found in ENV")
    #
    # if "MASTERUSER" in os.environ:
    #     masteruser = os.getenv("MASTERUSER")
    # else:
    #     print("MASTERUSER not found in ENV")
    #
    # if "MYPASS" in os.environ:
    #     mypass = os.getenv("MYPASS")
    # else:
    #     print("MYPASS not found in ENV")
    #
    # if "COMNAME" in os.environ:
    #     comname = os.getenv("COMNAME")
    # else:
    #     print("COMNAME not found in ENV")
    #
    # if "BUCKET" in os.environ:
    #     bucket = os.getenv("BUCKET")
    # else:
    #     print("BUCKET not found in ENV")

    rdsname = db_obj["endpoint"].split(".")[0]


    sql1="select count(*) from pg_stat_activity where state='idle';"

      #Size of all databases
    sql2="""SELECT pg_database.datname,
    pg_database_size(pg_database.datname) as "DB_Size",
    pg_size_pretty(pg_database_size(pg_database.datname)) as "Pretty_DB_size"
    FROM pg_database ORDER by 2 DESC limit 5;"""

      #Size only of all databases
    sql3="SELECT pg_database_size(pg_database.datname)  FROM pg_database"

      #Top 10 biggest tables
    sql4="""Select schemaname as table_schema,
       relname as table_name,
       pg_size_pretty(pg_total_relation_size(relid)) as "Total_Size",
       pg_size_pretty(pg_relation_size(relid)) as "Data_Size",
       pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid))
         as "Index_Size"
    from pg_catalog.pg_statio_user_tables
    order by pg_total_relation_size(relid) desc,
            pg_relation_size(relid) desc
    limit 10;"""

      #Duplticate Indexes
    sql5="""SELECT pg_size_pretty(SUM(pg_relation_size(idx))::BIGINT) AS SIZE,
         (array_agg(idx))[1] AS idx1, (array_agg(idx))[2] AS idx2,
         (array_agg(idx))[3] AS idx3, (array_agg(idx))[4] AS idx4
    FROM (
      SELECT indexrelid::regclass AS idx, (indrelid::text ||E'\n'|| indclass::text ||E'\n'|| indkey::text ||E'\n'||
                                           COALESCE(indexprs::text,'')||E'\n' || COALESCE(indpred::text,'')) AS KEY
      FROM pg_index) sub
    GROUP BY KEY HAVING COUNT(*)>1
    ORDER BY SUM(pg_relation_size(idx)) DESC;"""

      #Unused Indexes
    sql6="""SELECT s.schemaname,
         s.relname AS tablename,
         s.indexrelname AS indexname,
         pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size
    FROM pg_catalog.pg_stat_user_indexes s
     JOIN pg_catalog.pg_index i ON s.indexrelid = i.indexrelid
    WHERE s.idx_scan = 0      -- has never been scanned
    AND 0 <>ALL (i.indkey)  -- no index column is an expression
    AND NOT EXISTS          -- does not enforce a constraint
           (SELECT 1 FROM pg_catalog.pg_constraint c
            WHERE c.conindid = s.indexrelid)
    ORDER BY pg_relation_size(s.indexrelid) DESC limit 15;"""

      #Database Age
    sql7="select datname, ltrim(to_char(age(datfrozenxid), '999,999,999,999,999')) age from pg_database where datname not like 'rdsadmin';"

      #Most Bloated Tables
    sql8="""SELECT
    current_database(), schemaname, tablename, /*reltuples::bigint, relpages::bigint, otta,*/
    ROUND((CASE WHEN otta=0 THEN 0.0 ELSE sml.relpages::FLOAT/otta END)::NUMERIC,1) AS tbloat,
    CASE WHEN relpages < otta THEN 0 ELSE bs*(sml.relpages-otta)::BIGINT END AS wastedbytes,
    iname, /*ituples::bigint, ipages::bigint, iotta,*/
    ROUND((CASE WHEN iotta=0 OR ipages=0 THEN 0.0 ELSE ipages::FLOAT/iotta END)::NUMERIC,1) AS ibloat,
    CASE WHEN ipages < iotta THEN 0 ELSE bs*(ipages-iotta) END AS wastedibytes
    FROM (
    SELECT
      schemaname, tablename, cc.reltuples, cc.relpages, bs,
      CEIL((cc.reltuples*((datahdr+ma-
        (CASE WHEN datahdr%ma=0 THEN ma ELSE datahdr%ma END))+nullhdr2+4))/(bs-20::FLOAT)) AS otta,
      COALESCE(c2.relname,'?') AS iname, COALESCE(c2.reltuples,0) AS ituples, COALESCE(c2.relpages,0) AS ipages,
      COALESCE(CEIL((c2.reltuples*(datahdr-12))/(bs-20::FLOAT)),0) AS iotta -- very rough approximation, assumes all cols
    FROM (
      SELECT
        ma,bs,schemaname,tablename,
        (datawidth+(hdr+ma-(CASE WHEN hdr%ma=0 THEN ma ELSE hdr%ma END)))::NUMERIC AS datahdr,
        (maxfracsum*(nullhdr+ma-(CASE WHEN nullhdr%ma=0 THEN ma ELSE nullhdr%ma END))) AS nullhdr2
      FROM (
        SELECT
          schemaname, tablename, hdr, ma, bs,
          SUM((1-null_frac)*avg_width) AS datawidth,
          MAX(null_frac) AS maxfracsum,
          hdr+(
            SELECT 1+COUNT(*)/8
            FROM pg_stats s2
            WHERE null_frac<>0 AND s2.schemaname = s.schemaname AND s2.tablename = s.tablename
          ) AS nullhdr
        FROM pg_stats s, (
          SELECT
            (SELECT current_setting('block_size')::NUMERIC) AS bs,
            CASE WHEN SUBSTRING(v,12,3) IN ('8.0','8.1','8.2') THEN 27 ELSE 23 END AS hdr,
            CASE WHEN v ~ 'mingw32' THEN 8 ELSE 4 END AS ma
          FROM (SELECT version() AS v) AS foo
        ) AS constants
        GROUP BY 1,2,3,4,5
      ) AS foo
    ) AS rs
    JOIN pg_class cc ON cc.relname = rs.tablename
    JOIN pg_namespace nn ON cc.relnamespace = nn.oid AND nn.nspname = rs.schemaname AND nn.nspname <> 'information_schema'
    LEFT JOIN pg_index i ON indrelid = cc.oid
    LEFT JOIN pg_class c2 ON c2.oid = i.indexrelid
    ) AS sml
    ORDER BY wastedbytes DESC LIMIT 10;"""

      #Top 10 biggest tables last vacuumed
    sql9="""SELECT
    schemaname, relname,last_vacuum, cast(last_autovacuum as date), cast(last_analyze as date), cast(last_autoanalyze as date),
    pg_size_pretty(pg_total_relation_size(table_name)) as table_total_size
    from pg_stat_user_tables a, information_schema.tables b where a.relname=b.table_name ORDER BY pg_total_relation_size(table_name) DESC limit 10;"""

      #Memory Parameters
    sql10="""select name, setting, source, context from pg_settings where name like '%mem%' or name ilike '%buff%'; """

      #Performance Parameters
    sql11="select name, setting from pg_settings where name IN ('shared_buffers', 'effective_cache_size', 'work_mem', 'maintenance_work_mem', 'default_statistics_target', 'random_page_cost', 'rds.logical_replication','wal_keep_segments');"

      #pg_stat_statements top queries
      #Top 10 short queries consuming CPU
    sql12="""SELECT substring(query, 1, 50) AS short_query,
                round(total_time::numeric, 2) AS total_time,
                calls,
                round(mean_time::numeric, 2) AS mean,
                round((100 * total_time /
                sum(total_time::numeric) OVER ())::numeric, 2) AS percentage_cpu
    FROM    pg_stat_statements
    ORDER BY total_time DESC
    LIMIT 10;"""

    #Top 10 short queries causing high Read IOPS
    sql13="""SELECT
    left(query, 50) AS short_query
    ,round(total_time::numeric, 2) AS total_time
    ,calls
    ,shared_blks_read
    ,shared_blks_hit
    ,round((100.0 * shared_blks_hit/nullif(shared_blks_hit + shared_blks_read, 0))::numeric,2) AS hit_percent
    FROM  pg_stat_statements
    ORDER BY total_time DESC LIMIT 10;"""

    #Top 10 short queries causing high write IOPS
    sql14="""SELECT
      left(query, 50) AS short_query
     ,round(total_time::numeric, 2) AS total_time
     ,calls
     ,rows
     ,calls*total_time*rows as Volume
     FROM pg_stat_statements
    WHERE
      (query ilike '%update%'
      or query ilike '%insert%'
      or query ilike '%delete%')
      and query not like '%aurora_replica_status%'
      and query not like '%rds_heartbeat%'
    ORDER BY Volume DESC LIMIT 10;"""

    #Top 10 UPDATE/DELETE tables
    sql15="""SELECT relname
    ,round(upd_percent::numeric, 2) AS update_percent
    ,round(del_percent::numeric, 2) AS delete_percent
    ,round(ins_percent::numeric, 2) AS insert_percent
    from (
    SELECT relname
    ,100*cast(n_tup_upd AS numeric) / (n_tup_ins + n_tup_upd + n_tup_del) AS upd_percent
    ,100*cast(n_tup_del AS numeric) / (n_tup_ins+ n_tup_upd + n_tup_del) AS del_percent
    ,100*cast(n_tup_ins AS numeric) / (n_tup_ins + n_tup_upd + n_tup_del) AS ins_percent
    FROM pg_stat_user_tables
    WHERE (n_tup_ins + n_tup_upd + n_tup_del) > 0
    ORDER BY coalesce(n_tup_upd,0)+coalesce(n_tup_del,0) desc ) a limit 10;"""

    #Top 10 Read IO tables
    sql16="""SELECT
    relname
    ,round((100.0 * heap_blks_hit/nullif(heap_blks_hit + heap_blks_read, 0))::numeric,2) AS hit_percent
    ,heap_blks_hit
    ,heap_blks_read
    FROM pg_statio_user_tables
    WHERE (heap_blks_hit + heap_blks_read) >0
    ORDER BY coalesce(heap_blks_hit,0)+coalesce(heap_blks_read,0) desc limit 10;"""

    newline = "\n"
    #Generating HTML file
    html = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">"""
    html = html + "<html>"
    html = html + """<link rel="stylesheet" href="https://unpkg.com/purecss@0.6.2/build/pure-min.css">"""
    html = html + """<body style="font-family:'Verdana'" bgcolor="#F8F8F8">"""
    html = html + """<fieldset>"""
    html = html + """<table><tr> <td width="20"></td> <td>"""
    html = html + """<h1><font face="verdana" color="#0099cc"><center><u>PostgreSQL Health Report For """+ rdsname +"""</u></center></font></h1>"""
    html = html + """<h3><font face="verdana">"""+ datetime.datetime.now().strftime("%c") +"""</h3></color>"""
    html = html + """</fieldset>"""

    html = html + "<br>"
    html = html + """<font face="verdana" color="#ff6600">Instance Details:  </font>"""
    html = html + "<br>"
    html = html + "Postgres Endpoint URL:"+ db_obj["endpoint"]
    html = html + "<br>"

    conn = psycopg2.connect(
        host=db_obj["endpoint"],
        user=db_obj["masteruser"],
        password=db_obj["mypass"],
        port=db_obj["rdsport"])

    if (conn.status != 1):
        print("Not Running")
        return {
            "statusCode": 404,
            "body": "DB Not Running",
            "headers": {
                'Content-Type': 'text/html',
            }
        }

    cur = conn.cursor()
    html = html + "Postgres Engine Version: "
    cur.execute("SELECT version()")
    html = html + cur.fetchone()[0] + newline
    html = html + "<br>"
    html = html + "Maximum Connections : "
    cur.execute("show max_connections")
    html = html + cur.fetchone()[0] + newline
    html = html + "<br>"
    html = html + "Curent Active Connections: "
    cur.execute("select count(*) from pg_stat_activity;")
    html = html + str(cur.fetchone()[0]) + newline
    html = html + "<br>"
    html = html + "Idle Connections : "
    cur.execute(sql1)
    html = html + str(cur.fetchone()[0]) + newline
    html = html + "<br>"
    html = html + "<br>"

    html = html + """<font face="verdana" color="#ff6600">Instance Configuration: </font>"""
    html = html + "<br>"
    html = html + "Publicly Accessible: "
    rds_details = rdsclient.describe_db_instances(DBInstanceIdentifier=rdsname)
    html = html + str(rds_details["DBInstances"][0]["PubliclyAccessible"])
    html = html + "<br>"
    html = html + "EM Monitoring Interval: "
    html = html + str(rds_details["DBInstances"][0]["MonitoringInterval"])
    html = html + "<br>"
    html = html + "Multi AZ Enabled?: "
    html = html + str(rds_details["DBInstances"][0]["MultiAZ"])
    html = html + "<br>"
    html = html + "Allocated Storage (GB): "
    html = html + str(rds_details["DBInstances"][0]["AllocatedStorage"])
    html = html + "<br>"
    html = html + "Backup Retention Period: "
    html = html + str(rds_details["DBInstances"][0]["BackupRetentionPeriod"])
    html = html + "<br>"
    html = html + "Storage Type: "
    html = html + str(rds_details["DBInstances"][0]["StorageType"])
    html = html + "<br>"
    html = html + "DB Instance Class: "
    html = html + str(rds_details["DBInstances"][0]["DBInstanceClass"])
    html = html + "<br>"
    html = html + "<br>"
    #Total Log Size
    rds_log_details = rdsclient.describe_db_log_files(DBInstanceIdentifier=rdsname)
    AGB=1073741824
    total_log_size = 0
    for log in rds_log_details["DescribeDBLogFiles"]:
        total_log_size = total_log_size + log["Size"]
    html = html + """<font face="verdana" color="#ff6600">Total Size of Log Files:  </font>"""
    html = html + str(total_log_size) + " Bytes"
    html = html + "<br>"
    html = html + "<br>"
    html = html + """<font face="verdana" color="#ff6600">Total Size of ALL Databases:  </font>"""

    cur.execute(sql3)
    html = html + str(cur.fetchone()[0]) + " Bytes" + newline
    html = html + "<br>"
    html = html + "<br>"

    cur.execute("SELECT to_char(max(age(datfrozenxid)),'FM9,999,999,999') FROM pg_database;")
    html = html + """<font face="verdana" color="#ff6600">Maximum Used Transaction IDs:</font>""" + str(cur.fetchone()[0])
    html = html + "<br>"
    html = html + "<br>"

    cur.execute("SELECT count(*) from pg_database")
    html = html + table_creator("Top 5 Databases Size ("+str(cur.fetchone()[0]) + "):", ["datname", "db_size", "pretty_db_size"], cur, sql2)

    cur.execute("select count(*) from  pg_stat_user_tables")
    html = html + table_creator("Top 10 Biggest Tables ("+str(cur.fetchone()[0]) + "):", ["table_schema", "table_name", "total_size", "data_size", "index_size"], cur, sql4)

    html = html + table_creator("Duplicate Indexes: ", ["size", "idx1", "total_size", "idx2", "idx3"], cur, sql5)

    html = html + table_creator("Unused Indexes: ", ["schemaname", "tablename", "indexname", "index_size"], cur, sql6)

    html = html + table_creator("Database Age: ", ["datname", "age"], cur, sql7)

    html = html + table_creator("Top 10 Most Bloated Tables: ", ["current_database", "schemaname", "tbloat", "wastedbytes", "iname", "ibloat", "wastedibytes"], cur, sql8)

    html = html + table_creator("Top 10 Biggest Tables Last Vacuumed: ", ["schemaname", "relname", "last_vacuum", "date", "date", "date", "table_total_size"], cur, sql9)

    html = html + table_creator("Top 10 UPDATE/DELETE Tables: ", ["relname", "hit_percent", "delete_percent", "insert_percent"], cur, sql15)

    html = html + table_creator("Top 10 Read IO Tables: ", ["relname", "hit_percent", "heap_blks_hit", "heap_blks_read"], cur, sql16)

    html = html + table_creator("Vacuum Parameters: ", ["name", "setting", "source", "context"], cur, "select name, setting, source, context from pg_settings where name like 'autovacuum%'")

    html = html + table_creator("Memory Parameters: ", ["name", "setting", "source", "context"], cur, sql10)

    html = html + table_creator("Performance Parameters: ", ["name", "setting"], cur, sql11)

    cur.execute("select * FROM pg_extension")
    if "pg_stat_statements" in cur.fetchone():
        html = html + table_creator("Top 10 CPU Consuming SQLs: ", ["short_query", "total_time", "calls", "mean", "percentage_cpu"], cur, sql12)
        html = html + table_creator("Top 10 Read Queries: ", ["short_query", "total_time", "calls", "shared_blks_read", "shared_blks_hit", "hit_percent"], cur, sql13)
        html = html + table_creator("Top 10 Write Queries: ", ["short_query", "total_time", "calls", "rows", "volume"], cur, sql14)

    else:
        html = html + "<br>"
        html = html + """<font face="verdana" color="#ff6600">Postgres extension pg_stat_statements is not installed. Installation of this extension is recommended. </font>"""

    html = html + "<br>"
    html = html + "<br>"
    html = html + "<br>"
    html = html + "</td></tr></table></body></html>"

    filename = "/tmp/" + datetime.datetime.now().strftime("%m-%d-%Y") + "-report.html"
    f = open(filename, "w")
    f.write(html)
    f.close()
    if "bucket" in db_obj:
        s3 = boto3.resource('s3')
        s3.meta.client.upload_file(filename, db_obj["bucket"], datetime.datetime.now().strftime("%m-%d-%Y") + "-report.html")

    return {
        "statusCode": 200,
        "body": html,
        "headers": {
            'Content-Type': 'text/html',
        }
    }
