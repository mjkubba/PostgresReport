SELECT
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
  ORDER BY Volume DESC LIMIT 25;
