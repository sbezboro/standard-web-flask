insert into veteranstatus (server_id, player_id, rank)
select 2, player_id, rank from veteranstatus_new;

drop table veteranstatus_new;
