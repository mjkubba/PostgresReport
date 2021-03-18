## Purpose
Query and report RDS/Aurora Postgres information.   
Generates HTML file \<date>-report.html

### Inputs
Required input:   
EITHER (preferred):    
* sid

OR (not recommended):   
* endpoint
* masteruser
* mypass
* rdsport

if you pass in "sid" the lambda will retrieve the required details from AWS Secrets Manager based on the SecretID  provided

You can either pass the required input by API body or query parameters:
```
curl --location --request GET 'http://127.0.0.1:3000/' \
--header 'Content-Type: application/json' \
--data-raw '{
  "sid": "demo-postgres"
  }'

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
http://127.0.0.1:3000/?sid=demo-postgres

http://127.0.0.1:3000/?endpoint=mydb.us-east-1.rds.amazonaws.com&rdsport=5432&masteruser=postgres&mypass=superstrongpassword
```
## Networking:
This lambda need to be in a VPC that able to connect to the target Database, in a private subnet that have access to the internet or have the following endpoints enabled:
* STS
* S3
* RDS
* Secrets Manager

### Outputs:
Create S3 Bucket with name (if not there): \<AccountID>-rdsreports   
Save reports to that bucket after each run with name: \<datetime>-\<rdsName>report.html

### Local testing:
to start locally:    
`sam build && sam local start-api`

### Using SAM to Deploy
`sam build && sam deploy --stack-name <NEWSTACKNAME> --s3-bucket <EXISTINGS3BUCKET> --capabilities CAPABILITY_IAM --parameter-overrides securityGroup=sg-1234567890 subnets=subnet-1111111111111 --region <REGION>`

### TODO:
* ~~Refactor functions~~
* ~~Check for and create S3 buckets~~
* ~~Implement secret retrieval~~
* ~~limit the IAM to min required~~
* ~~Work with hanishg@ for test DBs~~
* ~~Add other regions~~
* Make the html human readable!
