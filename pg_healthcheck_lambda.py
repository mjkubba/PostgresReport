import getpass
import datetime
import sys
import boto3
import os
import subprocess

subprocess.call('pip install psycopg2-binary -t /tmp/ --no-cache-dir'.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sys.path.insert(1, '/tmp/')
import psycopg2

def lambda_handler(event, context):
  endpoint = ""
  dbname = ""
  rdsport = ""
  masteruser = ""
  comname = ""
  mypass= ""
  rdsclient = boto3.client('rds')

  """Check for inputs and exit if missing."""
  if "ENDPOINT" in os.environ:
      endpoint = os.getenv("ENDPOINT")
  else:
      print("ENDPOINT not found in ENV")

  if "DBNAME" in os.environ:
      dbname = os.getenv("DBNAME")
  else:
      print("DBNAME not found in ENV")

  if "DBPORT" in os.environ:
      rdsport = os.getenv("DBPORT")
  else:
      print("DBPORT not found in ENV")

  if "MASTERUSER" in os.environ:
      masteruser = os.getenv("MASTERUSER")
  else:
      print("MASTERUSER not found in ENV")

  if "MYPASS" in os.environ:
      mypass = os.getenv("MYPASS")
  else:
      print("MYPASS not found in ENV")

  if "COMNAME" in os.environ:
      comname = os.getenv("COMNAME")
  else:
      print("COMNAME not found in ENV")

  if "BUCKET" in os.environ:
      bucket = os.getenv("BUCKET")
  else:
      print("BUCKET not found in ENV")

  rdsname = endpoint.split(".")[0]


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
     ,calls
     ,round(total_time::numeric, 2) AS total_time
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
  html = html + """<h1><font face="verdana" color="#0099cc"><center><u>PostgreSQL Health Report For """+ comname +"""</u></center></font></h1>"""
  html = html + """<h3><font face="verdana">"""+ datetime.datetime.now().strftime("%c") +"""</h3></color>"""
  html = html + """</fieldset>"""

  html = html + "<br>"
  html = html + """<font face="verdana" color="#ff6600">Instance Details:  </font>"""
  html = html + "<br>"
  html = html + "Postgres Endpoint URL:"+ endpoint+ ""
  html = html + "<br>"

  conn = psycopg2.connect(
      host=endpoint,
      database=dbname,
      user=masteruser,
      password=mypass,
      port=rdsport)

  if (conn.status != 1):
      print("Not Running")
      sys.exit(1)
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
  # print(cur.fetchone())
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
  html = html + """<font face="verdana" color="#ff6600">Top 5 Databases Size ("""+str(cur.fetchone()[0])+"""):</font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>datname</th><th>db_size</th><th>pretty_db_size</th></tr>"""
  cur.execute(sql2)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"
  cur.execute("select count(*) from  pg_stat_user_tables")
  html = html + """<font face="verdana" color="#ff6600">Top 10 Biggest Tables ("""+str(cur.fetchone()[0])+"""):</font>"""
  html = html + "<br>"

  html = html + """<table border="1"><tr><th>table_schema</th><th>table_name</th><th>total_size</th><th>data_size</th><th>index_size</th></tr>"""
  cur.execute(sql4)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td><td>"+str(item[3])+"</td><td>"+str(item[4])+"</td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Duplicate Indexes: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>size</th><th>idx1</th><th>idx2</th><th>idx3</th></tr>"""
  cur.execute(sql5)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td><td>"+str(item[3])+"</td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Unused Indexes: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>schemaname</th><th>tablename</th><th>indexname</th><th>index_size</th></tr>"""
  cur.execute(sql6)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td><td>"+str(item[3])+"</td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Database Age: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>datname</th><th>age</th></tr>"""
  cur.execute(sql7)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Top 10 Most Bloated Tables: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>current_database</th><th>schemaname</th><th>tablename</th><th>tbloat</th><th>wastedbytes</th><th>iname</th><th>ibloat</th><th>wastedibytes</th></tr>"""
  cur.execute(sql8)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td><td>"+str(item[3])+"</td><td>"+str(item[4])+"</td><td>"+str(item[5])+"</td><td>"+str(item[6])+"</td><td>"+str(item[7])+"</td></td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Top 10 Biggest Tables Last Vacuumed: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>schemaname</th><th>relname</th><th>last_vacuum</th><th>date</th><th>date</th><th>date</th><th>table_total_size</th></tr>"""
  try:
      cur.execute(sql9)
      for item in cur.fetchall():
          html = html + "<tr>"
          html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td><td>"+str(item[3])+"</td><td>"+str(item[4])+"</td><td>"+str(item[5])+"</td><td>"+str(item[6])+"</td></td>"
          html = html + "</tr>"
          html = html + "</td></tr></table>"
  except psycopg2.errors.UndefinedFunction:
      cur.execute("ROLLBACK")
      pass
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Top 10 UPDATE/DELETE Tables: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>relname</th><th>hit_percent</th><th>delete_percent</th><th>insert_percent</th></tr>"""
  cur.execute(sql15)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td><td>"+str(item[3])+"</td></td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Top 10 Read IO Tables: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>relname</th><th>hit_percent</th><th>heap_blks_hit</th><th>heap_blks_read</th></tr>"""
  cur.execute(sql16)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td><td>"+str(item[3])+"</td></td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Vacuum Parameters: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>name</th><th>setting</th><th>source</th><th>context</th></tr>"""
  cur.execute("select name, setting, source, context from pg_settings where name like 'autovacuum%'")
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td><td>"+str(item[3])+"</td></td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Memory Parameters: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>name</th><th>setting</th><th>source</th><th>context</th></tr>"""
  cur.execute(sql10)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td><td>"+str(item[2])+"</td><td>"+str(item[3])+"</td></td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  html = html + """<font face="verdana" color="#ff6600">Performance Parameters: </font>"""
  html = html + "<br>"
  html = html + """<table border="1"><tr><th>name</th><th>setting</th></tr>"""
  cur.execute(sql11)
  for item in cur.fetchall():
      html = html + "<tr>"
      html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"</td>"
      html = html + "</tr>"
  html = html + "</td></tr></table>"
  html = html + "<br>"
  html = html + "<br>"

  cur.execute("select * FROM pg_extension")
  if "pg_stat_statements" in cur.fetchone():

      html = html + """<font face="verdana" color="#ff6600">Top 10 CPU Consuming SQLs: </font>"""
      html = html + "<br>"
      html = html + """<table border="1"><tr><th>short_query</th><th>total_time</th><th>calls</th><th>mean</th><th>percentage_cpu</th></tr>"""
      cur.execute(sql12)
      for item in cur.fetchall():
          html = html + "<tr>"
          html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"<td>"+str(item[2])+"</td><td>"+str(item[3])+"</td><td>"+str(item[4])+"</td></td>"
          html = html + "</tr>"
      html = html + "</td></tr></table>"
      html = html + "<br>"
      html = html + "<br>"

      html = html + """<font face="verdana" color="#ff6600">Top 10 Read Queries: </font>"""
      html = html + "<br>"
      html = html + """<table border="1"><tr><th>short_query</th><th>total_time</th><th>calls</th><th>shared_blks_read</th><th>shared_blks_hit</th><th>hit_percent</th></tr>"""
      cur.execute(sql13)
      for item in cur.fetchall():
          html = html + "<tr>"
          html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"<td>"+str(item[2])+"</td><td>"+str(item[3])+"</td><td>"+str(item[4])+"</td><td>"+str(item[5])+"</td></td>"
          html = html + "</tr>"
      html = html + "</td></tr></table>"
      html = html + "<br>"
      html = html + "<br>"

      html = html + """<font face="verdana" color="#ff6600">Top 10 Write Queries: </font>"""
      html = html + "<br>"
      html = html + """<table border="1"><tr><th>short_query</th><th>calls</th><th>total_time</th><th>rows</th><th>volume</th></tr>"""
      cur.execute(sql14)
      for item in cur.fetchall():
          html = html + "<tr>"
          html = html + "<td>"+str(item[0])+"</td><td>"+str(item[1])+"<td>"+str(item[2])+"</td><td>"+str(item[3])+"</td><td>"+str(item[4])+"</td>"
          html = html + "</tr>"
      html = html + "</td></tr></table>"
      html = html + "<br>"
      html = html + "<br>"
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
  s3 = boto3.resource('s3')
  s3.meta.client.upload_file(filename, bucket, datetime.datetime.now().strftime("%m-%d-%Y") + "-report.html")