"""Generate postgres report based on the provided input."""
# pg_health_check.py
# Author: MJ Kubba <mjkubba@amazon.com>
# based on work of Vivek Singh
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import datetime
import boto3
import json
import base64
from botocore.exceptions import ClientError
import psycopg2
session = boto3.session.Session()
aws_region = session.region_name


def check_input(input_obj):
    """Check for inputs and create Object."""
    if "sid" in input_obj:
        return(True)
    else:
        return(False)


def get_secret(secret_name):
    """Get secret from secret managerand return database object."""
    obj = {}
    client = session.client(service_name='secretsmanager', region_name=aws_region)
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            return("Secret Not Found: " + secret_name, False)
    else:
        if 'SecretString' in get_secret_value_response:
            tmp_obj = json.loads(get_secret_value_response['SecretString'])
            obj["endpoint"] = tmp_obj["host"]
            obj["mypass"] = tmp_obj["password"]
            obj["masteruser"] = tmp_obj["username"]
            obj["rdsport"] = tmp_obj["port"]
            if "dbname" in tmp_obj:
                obj["dbname"] = tmp_obj["dbname"]
            if "dbClusterIdentifier" in tmp_obj:
                obj["id"] = tmp_obj["dbClusterIdentifier"]
                obj["type"] = "aurora"
            elif "dbInstanceIdentifier" in tmp_obj:
                obj["id"] = tmp_obj["dbInstanceIdentifier"]
                obj["type"] = "rds"

            return(False, obj)

        else:
            tmp_obj = json.loads(base64.b64decode(get_secret_value_response
                                                  ['SecretBinary']))
            obj["endpoint"] = tmp_obj["host"]
            obj["mypass"] = tmp_obj["password"]
            obj["masteruser"] = tmp_obj["username"]
            obj["rdsport"] = tmp_obj["port"]
            if "dbname" in tmp_obj:
                obj["dbname"] = tmp_obj["dbname"]
            if "dbClusterIdentifier" in tmp_obj:
                obj["id"] = tmp_obj["dbClusterIdentifier"]
                obj["type"] = "aurora"
            elif "dbInstanceIdentifier" in tmp_obj:
                obj["id"] = tmp_obj["dbInstanceIdentifier"]
                obj["type"] = "rds"
            return(False, obj)


def table_creator(top, headers, cur, sqlname):
    """Create html table around the database return."""
    sql = open('sql/' + sqlname + '.sql', 'r').read().lstrip().replace('\n', '')
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


def get_obj(event):
    """Get the event object."""
    if "body" in event and event["body"]:
        if isinstance(event["body"], str):
            parsed_event = json.loads(event["body"])
        else:
            parsed_event = event["body"]
        if "sid" in parsed_event:
            err_check, db_obj = get_secret(parsed_event["sid"])
            return(err_check, db_obj)
        else:
            return(False, event)
    elif "queryStringParameters" in event and event["queryStringParameters"]:
        if "sid" in event["queryStringParameters"]:
            err_check, db_obj = get_secret(event["queryStringParameters"]
                                                ["sid"])
            return(err_check, db_obj)
        else:
            return(False, event["queryStringParameters"])


def s3_create_upload(filename):
    """Create and upload html to S3 bucket."""
    s3 = boto3.resource('s3', region_name=aws_region)
    s3client = boto3.client('s3', region_name=aws_region)
    accountID = boto3.client('sts').get_caller_identity().get('Account')
    bucket_name = "rds-reports-"+aws_region+"-"+accountID
    bucket_exist = True
    try:
        s3.meta.client.head_bucket(Bucket=bucket_name)
        print("Bucket Exists")
    except ClientError as e:
        if int(e.response['Error']['Code']) == 403:
            print("Private Bucket. Forbidden Access!")
            pass
        else:
            print("Bucket Does Not Exist!")
            print(str(e))
            bucket_exist = False
            pass
    if not bucket_exist:
        if aws_region == "us-east-1":
            s3client.create_bucket(Bucket=bucket_name, ACL='private')
        else:
            location = {"LocationConstraint": aws_region}
            s3client.create_bucket(
                Bucket=bucket_name,
                ACL='private',
                CreateBucketConfiguration=location
            )
            s3client.put_bucket_encryption(Bucket=bucket_name, ServerSideEncryptionConfiguration={'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256', }}]})

    s3.meta.client.upload_file(filename, bucket_name,
                               filename.split("tmp/")[1])


def lambda_handler(event, context):
    """Handle the lambda event."""
    err_check = False
    input_validator = False
    if "body" in event and event["body"]:
        if isinstance(event["body"], str):
            input_validator = check_input(json.loads(event["body"]))
        else:
            input_validator = check_input(event["body"])
        err_check, db_obj = get_obj(event)
    elif "queryStringParameters" in event and event["queryStringParameters"]:
        input_validator = check_input(event["queryStringParameters"])
        err_check, db_obj = get_obj(event)
    else:
        input_validator = False
    if err_check:
        return {
            "statusCode": 400,
            "body": err_check,
            "headers": {
                'Content-Type': 'text/html',
            }
        }
    if not input_validator:
        return {
            "statusCode": 400,
            "body": "missing input",
            "headers": {
                'Content-Type': 'text/html',
            }
        }

    rdsclient = boto3.client('rds', region_name=aws_region)
    rdsname = db_obj["endpoint"].split(".")[0]

    if db_obj["type"] == "rds":
        rds_details = rdsclient.describe_db_instances(DBInstanceIdentifier=db_obj["id"])
    elif db_obj["type"] == "aurora":
        rds_cluster = rdsclient.describe_db_clusters(DBClusterIdentifier=db_obj["id"])
        for cluster_instance in rds_cluster["DBClusters"][0]["DBClusterMembers"]:
                if cluster_instance["IsClusterWriter"]:
                    db_obj["dbinstance"] = cluster_instance["DBInstanceIdentifier"]
        rds_details = rdsclient.describe_db_instances(DBInstanceIdentifier=db_obj["dbinstance"])

    newline = "\n"
    # Generating HTML file
    html = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">"""
    html = html + "<html>"
    html = html + """<link rel="stylesheet" href="https://unpkg.com/purecss@0.6.2/build/pure-min.css">"""
    html = html + """<body style="font-family:'Verdana'" bgcolor="#F8F8F8">"""
    html = html + """<fieldset>"""
    html = html + """<table><tr> <td width="20"></td> <td>"""
    html = html + """<h1><font face="verdana" color="#0099cc"><center><u>PostgreSQL Health Report For """ + rdsname + """</u></center></font></h1>"""
    html = html + """<h3><font face="verdana">""" + datetime.datetime.now().strftime("%c") + """</h3></color>"""
    html = html + """</fieldset>"""

    html = html + "<br>"
    html = html + """<font face="verdana" color="#ff6600">Instance Details:  </font>"""
    html = html + "<br>"
    html = html + "Postgres Instance Name: " + rds_details["DBInstances"][0]["DBInstanceIdentifier"]
    html = html + "<br>"
    html = html + "Postgres Endpoint URL:" + db_obj["endpoint"]
    html = html + "<br>"
    conn = {}
    if "dbname" in db_obj:
        try:
            conn = psycopg2.connect(
                host=db_obj["endpoint"],
                user=db_obj["masteruser"],
                password=db_obj["mypass"],
                dbname=db_obj["dbname"],
                port=db_obj["rdsport"])
        except psycopg2.OperationalError as e:
            return {
                "statusCode": 400,
                "body": str(e),
                "headers": {
                    'Content-Type': 'text/html',
                }
            }
    else:
        try:
            conn = psycopg2.connect(
                host=db_obj["endpoint"],
                user=db_obj["masteruser"],
                password=db_obj["mypass"],
                port=db_obj["rdsport"])
        except psycopg2.OperationalError as e:
            return {
                "statusCode": 400,
                "body": str(e),
                "headers": {
                    'Content-Type': 'text/html',
                }
            }
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
    sql1 = open('sql/sql1.sql', 'r').read().replace('\n', '')
    cur.execute(sql1)
    html = html + str(cur.fetchone()[0]) + newline
    html = html + "<br>"
    html = html + "<br>"

    html = html + """<font face="verdana" color="#ff6600">Instance Configuration: </font>"""
    html = html + "<br>"
    html = html + "Publicly Accessible: "
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
    # Total Log Size
    if db_obj["type"] == "rds":
        rds_log_details = rdsclient.describe_db_log_files(DBInstanceIdentifier=db_obj["id"])
    elif db_obj["type"] == "aurora":
        rds_log_details = rdsclient.describe_db_log_files(DBInstanceIdentifier=db_obj["dbinstance"])

    total_log_size = 0
    for log in rds_log_details["DescribeDBLogFiles"]:
        total_log_size = total_log_size + log["Size"]
    html = html + """<font face="verdana" color="#ff6600">Total Size of Log Files:  </font>"""
    html = html + str(total_log_size) + " Bytes"
    html = html + "<br>"
    html = html + "<br>"
    html = html + """<font face="verdana" color="#ff6600">Total Size of ALL Databases:  </font>"""

    sql3 = open('sql/sql3.sql', 'r').read().replace('\n', '')
    cur.execute(sql3)
    html = html + str(cur.fetchone()[0]) + " Bytes" + newline
    html = html + "<br>"
    html = html + "<br>"

    cur.execute("SELECT to_char(max(age(datfrozenxid)),'FM9,999,999,999') FROM pg_database;")
    html = html + """<font face="verdana" color="#ff6600">Maximum Used Transaction IDs:</font>""" + str(cur.fetchone()[0])
    html = html + "<br>"
    html = html + "<br>"

    cur.execute("SELECT count(*) from pg_database")

    html = html + table_creator("Top 25 Databases Size ("+str(cur.fetchone()[0]) + "):", ["datname", "db_size", "pretty_db_size"], cur, "sql2")

    cur.execute("select count(*) from  pg_stat_user_tables")
    html = html + table_creator("Top 25 Biggest Tables ("+str(cur.fetchone()[0]) + "):", ["table_schema", "table_name", "total_size", "data_size", "index_size"], cur, "sql4")

    html = html + table_creator("Duplicate Indexes: ", ["size", "idx1", "total_size", "idx2", "idx3"], cur, "sql5")

    html = html + table_creator("Unused Indexes: ", ["schemaname", "tablename", "indexname", "index_size"], cur, "sql6")

    html = html + table_creator("Database Age: ", ["datname", "age"], cur, "sql7")

    html = html + table_creator("Top 25 Most Bloated Tables: ", ["current_database", "schemaname", "tablename", "tbloat", "wastedbytes", "iname", "ibloat", "wastedibytes"], cur, "sql8")

    html = html + table_creator("Top 25 Biggest Tables Last Vacuumed: ", ["schemaname", "relname", "last_vacuum", "date", "date", "date", "table_total_size"], cur, "sql9")

    html = html + table_creator("Top 25 UPDATE/DELETE Tables: ", ["relname", "hit_percent", "delete_percent", "insert_percent"], cur, "sql15")

    html = html + table_creator("Top 25 Read IO Tables: ", ["relname", "hit_percent", "heap_blks_hit", "heap_blks_read"], cur, "sql16")

    html = html + table_creator("Vacuum Parameters: ", ["name", "setting", "source", "context"], cur, "sql17")

    html = html + table_creator("Memory Parameters: ", ["name", "setting", "source", "context"], cur, "sql10")

    html = html + table_creator("Performance Parameters: ", ["name", "setting"], cur, "sql11")

    cur.execute("select * FROM pg_extension")
    if "pg_stat_statements" in str(cur.fetchall()):
        html = html + table_creator("Top 25 CPU Consuming SQLs: ", ["short_query", "total_time", "calls", "mean", "percentage_cpu"], cur, "sql12")
        html = html + table_creator("Top 25 Read Queries: ", ["short_query", "total_time", "calls", "shared_blks_read", "shared_blks_hit", "hit_percent"], cur, "sql13")
        html = html + table_creator("Top 25 Write Queries: ", ["short_query", "total_time", "calls", "rows", "volume"], cur, "sql14")

    else:
        html = html + "<br>"
        html = html + """<font face="verdana" color="#ff6600">Postgres extension pg_stat_statements is not installed. Installation of this extension is recommended. </font>"""

    html = html + "<br>"
    html = html + "<br>"
    html = html + "<br>"
    html = html + "</td></tr></table></body></html>"

    filename = "/tmp/" + datetime.datetime.now().strftime("%m-%d-%Y-T%H:%M:%S") + rdsname + "-report.html"
    f = open(filename, "w")
    f.write(html)
    f.close()

    s3_create_upload(filename)

    return {
        "statusCode": 200,
        "body": html,
        "headers": {
            'Content-Type': 'text/html',
        }
    }


def flask_controller():
    """Handle the flask event."""
    if request.data:
        event = {"body": {"sid": request.get_json(force=True)["sid"]}}
    elif request.args:
        if "sid" in request.args:
            event = {"body": {"sid": request.args.get('sid')}}
    return(lambda_handler(event, "test")["body"])


if __name__ == "__main__":
    from flask import Flask
    from flask import request
    app = Flask(__name__)
    app.add_url_rule("/", "flask_controller", flask_controller)
    app.run()


#  pylama:ignore=E501,C901
