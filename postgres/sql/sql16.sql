SELECT
  relname
  ,round((100.0 * heap_blks_hit/nullif(heap_blks_hit + heap_blks_read, 0))::numeric,2) AS hit_percent
  ,heap_blks_hit
  ,heap_blks_read
  FROM pg_statio_user_tables
  WHERE (heap_blks_hit + heap_blks_read) >0
  ORDER BY coalesce(heap_blks_hit,0)+coalesce(heap_blks_read,0) desc limit 10;
