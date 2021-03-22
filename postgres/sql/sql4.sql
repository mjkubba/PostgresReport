Select schemaname as table_schema,
     relname as table_name,
     pg_size_pretty(pg_total_relation_size(relid)) as "Total_Size",
     pg_size_pretty(pg_relation_size(relid)) as "Data_Size",
     pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid))
       as "Index_Size"
  from pg_catalog.pg_statio_user_tables
  order by pg_total_relation_size(relid) desc,
          pg_relation_size(relid) desc
  limit 25;
