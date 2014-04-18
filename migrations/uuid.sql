alter table standardweb_veteranstatus_new engine=innodb;
alter table standardweb_veteranstatus engine=innodb;
alter table standardweb_serverstatus engine=innodb;
alter table standardweb_server engine=innodb;
alter table standardweb_playerstats engine=innodb;
alter table standardweb_playeractivity engine=innodb;
alter table standardweb_mojangstatus engine=innodb;
alter table standardweb_minecraftplayer engine=innodb;
alter table standardweb_killtype engine=innodb;
alter table standardweb_killevent engine=innodb;
alter table standardweb_iptracking engine=innodb;
alter table standardweb_deathtype engine=innodb;
alter table standardweb_deathevent engine=innodb;
alter table registration_registrationprofile engine=innodb;
alter table messages_message engine=innodb;
alter table django_site engine=innodb;
alter table django_session engine=innodb;
alter table django_content_type engine=innodb;
alter table django_admin_log engine=innodb;
alter table djangobb_forum_topic_subscribers engine=innodb;
alter table djangobb_forum_topic engine=innodb;
alter table djangobb_forum_reputation engine=innodb;
alter table djangobb_forum_report engine=innodb;
alter table djangobb_forum_profile engine=innodb;
alter table djangobb_forum_posttracking engine=innodb;
alter table djangobb_forum_post engine=innodb;
alter table djangobb_forum_forum_moderators engine=innodb;
alter table djangobb_forum_forum engine=innodb;
alter table djangobb_forum_category_groups engine=innodb;
alter table djangobb_forum_category engine=innodb;
alter table djangobb_forum_ban engine=innodb;
alter table djangobb_forum_attachment engine=innodb;
alter table auth_user_user_permissions engine=innodb;
alter table auth_user_groups engine=innodb;
alter table auth_user engine=innodb;
alter table auth_permission engine=innodb;
alter table auth_group_permissions engine=innodb;
alter table auth_group engine=innodb;

rename table standardweb_veteranstatus_new to veteranstatus_new;
rename table standardweb_veteranstatus to veteranstatus;
rename table standardweb_serverstatus to serverstatus;
rename table standardweb_server to server;
rename table standardweb_playerstats to playerstats;
rename table standardweb_playeractivity to playeractivity;
rename table standardweb_oresmeltcount to oresmeltcount;
rename table standardweb_orediscoveryevent to orediscoveryevent;
rename table standardweb_orediscoverycount to orediscoverycount;
rename table standardweb_mojangstatus to mojangstatus;
rename table standardweb_minecraftplayer to player;
rename table standardweb_materialtype to materialtype;
rename table standardweb_killtype to killtype;
rename table standardweb_killevent to killevent;
rename table standardweb_killcount to killcount;
rename table standardweb_iptracking to iptracking;
rename table standardweb_deathtype to deathtype;
rename table standardweb_deathevent to deathevent;
rename table standardweb_deathcount to deathcount;

rename table djangobb_forum_topic to forum_topic;
rename table djangobb_forum_post to forum_post;
rename table djangobb_forum_profile to forum_profile;
rename table djangobb_forum_posttracking to forum_posttracking;
rename table djangobb_forum_forum_moderators to forum_moderators;
rename table djangobb_forum_forum to forum;
rename table djangobb_forum_category to forum_category;
rename table djangobb_forum_ban to forum_ban;
rename table djangobb_forum_topic to forum_topic;
rename table djangobb_forum_attachment to forum_attachment;

create table user (
  id int(11) not null auto_increment,
  username varchar(32) default null,
  player_id int(11) default null,
  uuid char(36) default null,
  full_name varchar(100) not null,
  email varchar(75) not null,
  password varchar(128) not null,
  admin tinyint(1) not null,
  last_login datetime not null,
  date_joined datetime not null,
  primary key (id),
  foreign key (player_id) references player (id),
  unique key uuid (uuid)
) engine=innodb DEFAULT charset=latin1;

# must be done after player uuids are populated
insert into user (id, username, player_id, uuid, full_name, email, password, admin, last_login, date_joined)
    select u.id, IF(ISNULL(p.id), u.username, NULL), p.id, uuid, CONCAT(first_name, ' ', last_name), email, password, is_superuser, last_login, date_joined
    from auth_user u
    left join player p on u.username = p.username;