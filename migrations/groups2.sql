create table group_invite (
  group_id int(11) not null,
  invite varchar(20) not null,

  primary key (group_id, invite),
  foreign key (group_id) references `group` (id)
) engine=InnoDB default charset=utf8;

alter table playerstats
  add column is_leader tinyint(1) default 0,
  add column is_moderator tinyint(1) default 0;

alter table `group`
  add column lock_count int(11) not null;
