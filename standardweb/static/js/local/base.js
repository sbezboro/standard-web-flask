(function(window, document, $) {
  function csrfSafeMethod(method) {
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
  }

  function sameOrigin(url) {
    var host = document.location.host;
    var protocol = document.location.protocol;
    var sr_origin = '//' + host;
    var origin = protocol + sr_origin;
    return (url == origin || url.slice(0, origin.length + 1) == origin + '/') ||
        (url == sr_origin || url.slice(0, sr_origin.length + 1) == sr_origin + '/') ||
        !(/^(\/\/|http:|https:).*/.test(url));
  }

  if (typeof Object.create === 'undefined') {
    Object.create = function (o) {
      function F() {
      }

      F.prototype = o;
      return new F();
    };
  }

  $.ajaxSetup({
    cache: false
  });

  window.StandardWeb = {
    userId: null,
    username: null,
    nickname: null,
    cdnDomain: null,
    reactComponents: {},
    reactMixins: {},
    sounds: {},
    originalTitle: document.title,
    numNewMessages: 0,
    numNewNotifications: 0,

    refreshFromnow: function($rootElement) {
      $rootElement = $rootElement || document;

      $('.fromnow', $rootElement).each(function() {
        var val;
        var now = moment();
        var date = moment($.trim($(this).text()));

        if (!date.isValid()) {
          date = moment($.trim($(this).attr('title')));
        }

        if (date.isValid()) {
          if (now.diff(date, 'days') > 365) {
            val = date.format('MMMM D, YYYY');
          } else {
            val = date.fromNow();
          }

          $(this).text(val);
          $(this).attr('title', date.format('LLL'));
        }
      });
    },

    loadSound: function(id, path) {
      return soundManager.createSound({
        id: id,
        url: path
      });
    },

    loadSounds: function() {
      soundManager.setup({
        url: '/static/flash/',
        flashVersion: 9,
        debugMode: false,
        preferFlash: false,

        onready: function() {
          StandardWeb.sounds.mentionSound = StandardWeb.loadSound('mention', '/static/sound/mention.wav');
        }
      });
    },

    on: function(channel, event, callback) {
      this.subscribe(channel, function(error, socket) {
        socket.on(event, function(data) {
          callback(data);
        });
      });
    },

    setCSRFToken: function(token) {
      $.ajaxSetup({
        beforeSend: function(xhr, settings) {
          if (!csrfSafeMethod(settings.type) && sameOrigin(settings.url)) {
            xhr.setRequestHeader("X-CSRFToken", token);
          }
        }
      });
    },

    alertManager: { // Default in case alert manager is not present on page
      addAlert: function() {}
    },

    refreshTitleNotificationCount: function() {
      var count = this.numNewMessages + this.numNewNotifications;

      if (count) {
        document.title = '(' + count + ') ' + this.originalTitle;
      } else {
        document.title = this.originalTitle;
      }
    },

    setNewItemCount: function(count, type) {
      var $account = $('.header-account');
      var $items = $account.find('.' + type);
      var $itemsCount = $account.find('.' + type + ' .count');

      if (count && !$items.hasClass('new')) {
        $items.addClass('new');
      } else if (!count && $items.hasClass('new')) {
        $items.removeClass('new');
      }

      $itemsCount.html(count);
    },

    setNumNewMessages: function(count) {
      this.numNewMessages = count;

      this.setNewItemCount(count, 'messages');

      this.refreshTitleNotificationCount();
    },

    setNumNewNotifications: function(count) {
      this.numNewNotifications = count;

      this.setNewItemCount(count, 'notifications');

      this.refreshTitleNotificationCount();
    }
  };

  setInterval(function () {
    StandardWeb.refreshFromnow();
  }, 30000);
})(window, document, $);
