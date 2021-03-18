select name, setting, source, context from pg_settings where name like '%mem%' or name ilike '%buff%'; 
