## Purpose
Query and report RDS/Aurora Postgres information Every 6 hours.   
Generates HTML file \<date>-report.html   

### Inputs
#### SAM template
* stack-name: the new stack name
* s3-bucket: Bucket where the SAM package will be uploaded
* capabilities CAPABILITY_IAM: needed for creating the role
* parameter-overrides:
  * securityGroup: the security group for the lambda function
  * subnet1: a private subnet where the function can reach the target DB
  * subnet2: a 2nd private subnet where the function can reach the target DB
  * region: AWS region where the lambda need to be deployed
  * secid: the secrets manager secretID where the DB details stored

#### Lambda
Required input (handled by EventBridge):     
* sid

The lambda will retrieve the required details from AWS Secrets Manager based on the SecretID provided

If you want to invoke the lambda directly outside the scheduled event you can attach an ALB or API gateway.   
You can either pass the required input by API body or query parameters:
```
curl --location --request GET 'http://127.0.0.1:3000/' \
--header 'Content-Type: application/json' \
--data-raw '{
  "sid": "demo-postgres"
  }'
```
OR
```
http://127.0.0.1:3000/?sid=demo-postgres
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
`sam build && sam deploy --stack-name <NEWSTACKNAME> --s3-bucket <EXISTINGS3BUCKET> --capabilities CAPABILITY_IAM --parameter-overrides securityGroup=sg-1234567890 subnets=subnet-1111111111111 --region <REGION> secid=<secretID>`

### TODO:
* ~~Refactor functions~~
* ~~Check for and create S3 buckets~~
* ~~Implement secret retrieval~~
* ~~limit the IAM to min required~~
* ~~Work with hanishg@ for test DBs~~
* ~~Add other regions~~
* Make the html human readable!
