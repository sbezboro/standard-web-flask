create table title (
  id int(11) not null auto_increment,
  name varchar(20) not null,
  displayname varchar(40) not null,
  created datetime not null,
  primary key (id),
  unique key (name)
) engine=InnoDB default charset=utf8;

create table player_title (
  player_id int(11) not null,
  title_id int(11) not null,
  primary key (player_id, title_id),
  foreign key (player_id) references player (id),
  foreign key (title_id) references title (id)
) engine=InnoDB default charset=utf8;
