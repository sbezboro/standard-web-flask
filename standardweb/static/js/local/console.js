(function(window, document, $) {
  StandardWeb.console = {};

  var $notificationCheckBox;
  var $console;
  var $detail;

  var $navHeader;

  var $close;
  var $displayName;
  var $username;
  var $image;
  var $link;
  var $ip;
  var $rank;
  var $timeSpent;
  var $health;
  var $location;
  var $titles;
  var $donatorBtn;

  var consoleStream;
  var currentUsername;

  function resize() {
    var baseHeight = $(window).height() - $(".header").outerHeight() - $(".sub-header").outerHeight();
    var consoleHeight = baseHeight - 30;
    var detailHeight = baseHeight - 22;
    var playersHeight = baseHeight - 150;

    if ($navHeader.is(':visible')) {
      consoleHeight -= $navHeader.outerHeight();
      detailHeight -= $navHeader.outerHeight();
      playersHeight -= $navHeader.outerHeight();
    }

    $console.height(consoleHeight);
    $detail.height(detailHeight);
    $(".players").height(playersHeight);
    $(".users").height(138);
  }

  var updatePlayerDetail = function(username) {
    var player = consoleStream.allPlayers[username];
    if (!player) {
        return;
    }

    var href = '/' + StandardWeb.console.serverId + '/player/' + username;

    if (player.nickname) {
      $displayName.html('<span class="ansi-container">' + player.nicknameAnsi + '</span>');
      $username.html('(' + username + ')');
    } else {
      $displayName.html(username);
      $username.html('&nbsp');
    }

    $link.attr('href', href);

    var hours = Math.floor(player.time_spent / 60);
    var minutes = hours > 0 ? (player.time_spent % (hours * 60)) : player.time_spent;

    var timeSpent;

    if (hours) {
      timeSpent = hours + (hours == 1 ? ' hour ' : ' hours ')
        + minutes + (minutes == 1 ? ' minute ' : ' minutes');
    } else {
      timeSpent = minutes + (minutes == 1 ? ' minute ' : ' minutes');
    }

    $ip.html(player.address);
    $rank.html(player.rank);
    $timeSpent.html(timeSpent);
    $health.html(player.health.toFixed(2));
    $location.html('[' + player.world + '] ' + player.x + ', ' + player.y + ', ' + player.z);

    var titleNames = [];
    player.titles.map(function(title) {
      titleNames.push(title.display_name);
    });

    if (!titleNames.length) {
      $titles.html('None');
    } else {
      $titles.html(titleNames.join(', '));
    }

    if (username != currentUsername) {
      currentUsername = username;

      $image.attr('src', '/face/64/' + username + '.png');
    }

    $detail.show();
  };

  $(document).ready(function() {
    $console = $('.console');

    if (!$console.length) {
      return;
    }

    $navHeader = $(".nav-header");
    $notificationCheckBox = $('.console-notification');
    $detail = $('.detail');

    $close = $detail.find('.close');
    $displayName = $detail.find('.display-name');
    $username = $detail.find('.username');
    $image = $detail.find('.face');
    $link = $detail.find('.link');
    $ip = $detail.find('.ip');
    $rank = $detail.find('.rank');
    $timeSpent = $detail.find('.time-spent');
    $health = $detail.find('.health');
    $location = $detail.find('.location');
    $titles = $detail.find('.titles');
    $donatorBtn = $detail.find('.donator');

    var $consoleTextbox = $('.console-textbox');

    consoleStream = new StandardWeb.realtime.ConsoleStream($console, $consoleTextbox, StandardWeb.console.serverId);
    consoleStream.connect();

    resize();

    $(window).resize(function() {
      resize();
      consoleStream.scrollToBottom();
    });

    consoleStream.onUpdate = function() {
      if (currentUsername) {
        updatePlayerDetail(currentUsername);
        $('.player[username="' + currentUsername + '"]').addClass('selected');
      }
    };

    $notificationCheckBox.on('click', function(e) {
      var enabled = $(this).is(':checked');
      consoleStream.playMentionSound = enabled;
    });

    $(document).on('click', '.player', function(e) {
      var username = $(this).attr('username');

      $('.player.selected').removeClass('selected');
      $(this).addClass('selected');
      consoleStream.scrollToBottomIfAtBottom(function() {
        updatePlayerDetail(username);
      });
    });

    $image.on('load', function(e) {
      $image.fadeTo(0, 1);
    });

    $donatorBtn.on('click', function(e) {
      consoleStream.setDonator(currentUsername);
    });

    $close.on('click', function(e) {
      currentUsername = null;

      $('.player.selected').removeClass('selected');

      consoleStream.scrollToBottomIfAtBottom(function() {
        $detail.hide();
      });
    });

    soundManager.setup({
      url: '/static/flash/',
      flashVersion: 9,
      debugMode: false,
      preferFlash: false,
      onready: function() {
        var mentionSound = soundManager.createSound({
          id: 'mention',
          url: '/static/sound/mention.wav'
        });

        consoleStream.setMentionSound(mentionSound);
      }
    });
  });
})(window, document, $);
