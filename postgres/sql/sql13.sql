SELECT
  left(query, 50) AS short_query
  ,round(total_time::numeric, 2) AS total_time
  ,calls
  ,shared_blks_read
  ,shared_blks_hit
  ,round((100.0 * shared_blks_hit/nullif(shared_blks_hit + shared_blks_read, 0))::numeric,2) AS hit_percent
  FROM  pg_stat_statements
  ORDER BY total_time DESC LIMIT 10;
