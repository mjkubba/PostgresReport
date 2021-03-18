SELECT pg_database.datname,
  pg_database_size(pg_database.datname) as "DB_Size",
  pg_size_pretty(pg_database_size(pg_database.datname)) as "Pretty_DB_size"
  FROM pg_database ORDER by 2 DESC limit 5;
