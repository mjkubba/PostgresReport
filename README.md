## Purpose
Query and report RDS/Aurora Postgres information.   
Generates HTML file \<date>-report.html

### inputs
required input:
* endpoint (-e)
* masteruser (-u)
* password (-s)
* port (-p)
* company (-c)
* database name (-d)

you can pass the inputs from the environment variables, inline or in an interactive way:    
```
# env
ENDPOINT=mjtest.asdasd.us-east-1.rds.amazonaws.com
DBNAME=mjtestdb
DBPORT=5432
MASTERUSER=postgres
MYPASS=mypass
COMNAME=aws
```
or

```
# python3 pg_health_check.py -e mjtest.asdasd.us-east-1.rds.amazonaws.com -u postgres -p 5432 -s mypass -c aws -d mjtestdb
```

or   
```
# python3 pg_health_check.py
RDS/Aurora PostgreSQL Endpoint URL: mjtest.asdasd.us-east-1.rds.amazonaws.com
Database Name: mjtestdb
Port: 5432
RDS Master User Name: postgres
Password: mypass
Company Name: aws
```

### TODO:
* refactor to functions
* convert to lambda friendly
* create Cloudformation
* work with hanishg@ for test DBs
