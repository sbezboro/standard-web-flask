(function(window, document, $) {
  StandardWeb.realtime = {
    rtsAuthData: null,
    rtsBaseUrl: null,
    rtsPrefix: null,
    rtsSockets: {},

    init: function (rtsAuthData, rtsBaseUrl, rtsPrefix) {
      this.rtsAuthData = rtsAuthData;
      this.rtsBaseUrl = rtsBaseUrl;
      this.rtsPrefix = rtsPrefix;
    },

    subscribe: function (channel, extra, callback) {
      if (!callback) {
        callback = extra;
        extra = undefined;
      }

      var socket = this.rtsSockets[channel];
      if (socket) {
        if (callback) {
          callback(null, socket);
        }

        callback = null;
      } else {
        socket = io(this.rtsBaseUrl + '/' + channel, {
          path: this.rtsPrefix + '/socket.io'
        });

        socket.on('connect', function () {
          var data = {
            authData: this.rtsAuthData
          };

          var k;
          for (k in extra) {
            if (extra.hasOwnProperty(k)) {
              data[k] = extra[k];
            }
          }

          socket.emit('auth', data);

          socket.on('authorized', function (data) {
            this.rtsSockets[channel] = socket;

            if (callback) {
              callback(null, socket);
            }

            callback = null;
          }.bind(this));

          socket.on('unauthorized', function (data) {
            if (callback) {
              callback('unauthorized', socket);
            }

            callback = null;
          }.bind(this));
        }.bind(this));

        socket.on('connect_failed', function () {
          if (callback) {
            callback('connect_failed', socket);
          }

          callback = null;
        }.bind(this));

        socket.on('error', function () {
          if (callback) {
            callback('error', socket);
          }

          callback = null;
        }.bind(this));
      }
    }
  };
})(window, document, $);
