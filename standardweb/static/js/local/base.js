(function(window, document, $) {
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
    }
  };
})(window, document, $);
