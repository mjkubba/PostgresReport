SELECT relname
  ,round(upd_percent::numeric, 2) AS update_percent
  ,round(del_percent::numeric, 2) AS delete_percent
  ,round(ins_percent::numeric, 2) AS insert_percent
  from (
  SELECT relname
  ,100*cast(n_tup_upd AS numeric) / (n_tup_ins + n_tup_upd + n_tup_del) AS upd_percent
  ,100*cast(n_tup_del AS numeric) / (n_tup_ins+ n_tup_upd + n_tup_del) AS del_percent
  ,100*cast(n_tup_ins AS numeric) / (n_tup_ins + n_tup_upd + n_tup_del) AS ins_percent
  FROM pg_stat_user_tables
  WHERE (n_tup_ins + n_tup_upd + n_tup_del) > 0
  ORDER BY coalesce(n_tup_upd,0)+coalesce(n_tup_del,0) desc ) a limit 10;
