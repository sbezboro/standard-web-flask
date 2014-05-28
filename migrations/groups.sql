create table `group` (
  id int(11) not null auto_increment,
  server_id int(11) not null,
  uid varchar(32) not null,
  name varchar(20) not null,
  established datetime not null,
  land_count int(11) not null,
  land_limit int(11) not null,
  member_count int(11) not null,

  primary key (id),
  unique key (uid),
  unique key (name),
  foreign key (server_id) references server (id)
) engine=InnoDB default charset=utf8;

alter table playerstats
  add column group_id int(11) default null,
  add foreign key (group_id) references `group` (id);
