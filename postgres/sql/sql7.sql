select datname,
         ltrim(to_char(age(datfrozenxid), '999,999,999,999,999')) age
         from pg_database where datname not like 'rdsadmin';
