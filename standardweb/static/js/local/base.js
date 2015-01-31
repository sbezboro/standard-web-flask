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

    refreshFromnow: function($rootElement) {
      $rootElement = $rootElement || document;

      $('.fromnow', $rootElement).each(function() {
        var val;
        var now = moment();
        var date = moment($.trim($(this).text()));

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
    }
  };
})(window, document, $);
