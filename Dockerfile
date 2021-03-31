FROM python:3
COPY postgres/sql/* sql/
COPY postgres/requirements.txt .
COPY postgres/pg_healthcheck_lambda.py .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "./pg_healthcheck_lambda.py" ]
