## Purpose
Query and report RDS/Aurora Postgres information.   
Generates HTML file \<date>-report.html

### Inputs
Required input:   
EITHER (preferred):    
* secret

OR (not recommended):   
* endpoint
* masteruser
* mypass
* rdsport

if you pass in "secret" the lambda will retrieve the required details from AWS Secrets Manager based on the SecretID  provided

You can either pass the required input by API body or query parameters:
```
curl --location --request GET 'http://127.0.0.1:3000/' \
--header 'Content-Type: application/json' \
--data-raw '{
    "endpoint": "mydb.us-east-1.rds.amazonaws.com",
    "masteruser": "postgres",
    "mypass": "superstrongpassword",
    "rdsport": 5432
}'
```
OR
```
http://127.0.0.1:3000/?endpoint=mydb.us-east-1.rds.amazonaws.com&rdsport=5432&masteruser=postgres&comname=aws&mypass=superstrongpassword
```
### Outputs:
Create S3 Bucket with name (if not there): \<AccountID>-rdsreports   
Save reports to that bucket after each run with name: \<datetime>-report.html

### Local testing:
to start locally:    
`sam local start-api`

### TODO:
* Refactor functions
* Check for and create S3 buckets
* Implement secret retrieval
* limit the IAM to min required
* Work with hanishg@ for test DBs
* Make the html human readable!
