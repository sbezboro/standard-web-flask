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
          path: rtsPrefix + '/socket.io'
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

  var ServerStream = function($outputArea, $textbox, serverId, source) {
    this.socket = null;

    this.commandHistory = [];
    this.commandIndex = -1;

    this.mentionPat = '(&gt;.*|Server<.*?><.*?>]\ .*|Web\ Chat\].*\: .*|To group.*|command:.*)(MENTION_PART)';

    this.$outputArea = $outputArea;
    this.$textbox = $textbox;
    this.source = source;
    this.socket = null;
    this.numLines = 0;
    this.maxLines = 200;

    this.nextMentionSound = 0;
    this.playMentionSound = true;
    this.mentionSound = null;
    this.mentions = [];

    this.focused = true;

    this.isAtBottom = function() {
      return this.$outputArea.get(0).scrollHeight - this.$outputArea.scrollTop() == this.$outputArea.outerHeight();
    };

    this.scrollToBottom = function() {
      this.$outputArea.scrollTop(this.$outputArea.get(0).scrollHeight);
    };

    this.scrollToBottomIfAtBottom = function(callback) {
      if (this.isAtBottom()) {
        callback();

        this.scrollToBottom();
      } else {
        callback();
      }
    };

    this.trimTopLines = function(num) {
      $('li:lt(' + num + ')', this.$outputArea).remove();
    };

    this.addOutputLines = function(batch) {
      var shouldScroll = this.isAtBottom();

      var html = "";
      batch.map(function(line) {
        html += '<li>' + this.postProcessLine(line) + '</li>';
      }.bind(this));

      this.$outputArea.append(html);

      if (this.numLines + batch.length > this.maxLines) {
        this.trimTopLines(this.numLines + batch.length - this.maxLines);
        this.numLines = this.maxLines;
      } else {
        this.numLines += batch.length;
      }

      // Scroll to see the new line of text if the bottom was already visible
      if (shouldScroll) {
        this.scrollToBottom();
      }
    };

    this.addOutputLine = function(line) {
      this.addOutputLines([line]);
    };

    this.postProcessLine = function(line) {
      var playSound = false;

      var i;
      for (i = 0; i < this.mentions.length; ++i) {
        var mention = this.mentions[i];

        if (this.playMentionSound && this.mentionSound
              && !this.focused && line.match(mention.regex)) {
          playSound = true;
        }

        if (mention.style) {
          line = line.replace(mention.regex, '$1<span style="' + mention.style + '">$2</span>');
        }
      }

      var now = new Date().getTime();

      if (playSound && now > this.nextMentionSound) {
        this.mentionSound.play();
        this.nextMentionSound = now + 500;
      }

      return line;
    };

    this.addRegexMention = function(regex, style) {
      this.mentions.push({
        regex: regex,
        style: style
      });
    };

    this.addChatMention = function(string, style) {
      var replacedPat = this.mentionPat.replace('MENTION_PART', string);
      var regex = new RegExp(replacedPat, 'gi');

      this.addRegexMention(regex, style);
    };

    this.setMentionSound = function(mentionSound) {
      this.mentionSound = mentionSound;
    };

    this.messageEntered = function() {
      throw "Method should be implemented by inherited objects!";
    };

    this.socketInitialized = function() {
      throw "Method should be implemented by inherited objects!";
    };

    this.connect = function() {
      this.addOutputLine("Connecting...");

      StandardWeb.realtime.subscribe(this.source, {serverId: serverId}, function(error, socket) {
        if (error) {
          this.addOutputLine("ERROR: connection failure!");
          return;
        }

        this.socket = socket;

        this.$outputArea.empty();
        this.numLines = 0;

        this.socketInitialized();

        socket.on('disconnect', function() {
          this.addOutputLine("ERROR: socket connection lost!");
        }.bind(this));

        socket.on('mc-connection-lost', function() {
          this.addOutputLine("Connection to Minecraft server lost, retrying...");
        }.bind(this));

        socket.on('mc-connection-restored', function() {
          this.addOutputLine("Connection restored!");
        }.bind(this));

        $(document).keypress(function() {
          var focused = $(':focus');
          if (this.$textbox != focused
            && (!focused[0] || focused[0].type == false)) {
            this.$textbox.focus();
          }
        }.bind(this));

        this.$textbox.keydown(function(e) {
          switch (e.which) {
            case 38: //Up
              if (this.commandIndex < this.commandHistory.length - 1) {
                this.commandIndex++;
                this.$textbox.val(this.commandHistory[this.commandIndex]);
              }
              return false;
            case 40: //Down
              if (this.commandIndex > -1) {
                this.commandIndex--;
                this.$textbox.val(this.commandHistory[this.commandIndex]);
              }
              return false;
          }

          return true;
        }.bind(this));

        this.$textbox.keyup(function(e) {
          switch (e.which) {
            case 13: //Enter
              var input = this.$textbox.val();

              if (input) {
                this.messageEntered(socket, input);

                this.$textbox.val('');
                this.scrollToBottom();

                this.commandHistory.unshift(input);
                this.commandIndex = -1;
              }
              break;
          }
        }.bind(this));

        var sendActivity = function(active) {
          socket.emit('user-activity', {
            active: active
          });
        };

        $(window).focus(function() {
          if (!this.focused) {
            sendActivity(true);
          }

          this.focused = true;
        }.bind(this));

        $(window).blur(function() {
          if (this.focused) {
            sendActivity(false);
          }

          this.focused = false;
        }.bind(this));
      }.bind(this));
    }
  };

  var ConsoleStream = function($outputArea, $textbox, serverId) {
    ServerStream.call(this, $outputArea, $textbox, serverId, 'console');

    this.allPlayers = {};

    this.maxLines = 4000;

    this.addChatMention('server', 'background:#A0A');
    // A player messaging console
    this.addRegexMention('-&gt; me');

    $textbox.keydown(function() {
      if ($textbox.val().length >= 53) {
        $textbox.addClass('len-warn');
      } else {
        $textbox.removeClass('len-warn');
      }
    });

    this.socketInitialized = function() {
      var html;

      this.socket.on('console', function(data) {
        if (data.line) {
          this.addOutputLine(data.line);
        } else if (data.batch) {
          this.addOutputLines(data.batch);
        }
      }.bind(this));

      // Update server status display
      this.socket.on('server-status', function(data) {
        var players = data.players;
        var numPlayers = data.numPlayers;
        var maxPlayers = data.maxPlayers;
        var load = data.load;
        var tps = data.tps;

        players = players.sort(function(a, b) {
          a = (a.nickname ? a.nickname : a.username);
          b = (b.nickname ? b.nickname : b.username);

          if (a.toLowerCase() < b.toLowerCase()) return -1;
          if (a.toLowerCase() > b.toLowerCase()) return 1;
          return 0;
        });

        var playersHtml = '';
        for (var i = 0; i < players.length; ++i) {
          var username = players[i].username;
          this.allPlayers[username] = players[i];

          var nicknameAnsi = players[i].nicknameAnsi;

          var displayName = nicknameAnsi ? nicknameAnsi : username;

          html = [
            '<a href="#">',
              '<div class="player" username="' + username + '">',
                '<img class="face-thumb" src="/face/16/' + username + '.png">',
                '<span class="ansi-container">' + displayName + '</span>',
                '<span class="rank">#' + players[i].rank + '</span>',
              '</div>',
            '</a>'
          ].join('');

          playersHtml += html;
        }

        $('.players').html(playersHtml);
        $('.player-count').text(numPlayers + '/' + maxPlayers);
        $('.load').text(load);
        $('.tps').text(tps);

        if (this.onUpdate && typeof this.onUpdate === 'function') {
          this.onUpdate();
        }
      }.bind(this));

      this.socket.on('chat-users', function(data) {
        var users = data.users;

        html = '<b>Chat user count: ' + users.length + '</b>';

        var i;
        for (i = 0; i < users.length; ++i) {
          var username = users[i].username;
          var address = users[i].address;
          var type = users[i].type;
          var active = users[i].active;

          if (username == 'Server') {
            html += [
              '<div class="user">',
                 username + ' [' + type + ']',
              '</div>'
            ].join('');
          } else if (username) {
            html += [
              '<div class="user">',
                '<a href="/player/' + username + '">',
                  '<span><img class="face-thumb" src="/face/16/' + username + '.png">' + username + '</span>',
                  active ? '<img src="/static/images/online.png">': ' ',
                '</a>- ' + address,
               '</div>'
            ].join('');
          } else {
            html += [
              '<div class="user">',
                'Anonymous',
                active ? '<img src="/static/images/online.png">': ' ',
                '- ' + address,
              '</div>'
            ].join('');
          }
        }

        $('.users').html(html);
      });
    }.bind(this);

    this.messageEntered = function(socket, input) {
      var data = {};

      if (input[0] == "/") {
        data = {
          command: input.substring(1, input.length)
        }
      } else {
        data = {
          message: input
        }
      }

      socket.emit('console-input', data);
      $textbox.removeClass('len-warn');
    };

    this.setDonator = function(username) {
      this.socket.emit('set-donator', {
        username: username
      });
    }
  };

  var ChatStream = function($outputArea, $textbox, serverId) {
    ServerStream.call(this, $outputArea, $textbox, serverId, 'chat');

    if (StandardWeb.username) {
      this.addChatMention(StandardWeb.username, 'background:#00ACC4');
    }
    if (StandardWeb.nickname) {
      this.addChatMention(StandardWeb.nickname, 'background:#00ACC4');
    }

    this.renderPlayerTable = function(players, maxPlayers) {
      var tableHtml = "<tr>";

      for (var i = 0; i < maxPlayers; ++i) {
        if (players.length <= i) {
          tableHtml += '<td>&nbsp;</td>';
        } else {
          var username = players[i].username;
          var nickname = players[i].nickname;

          var displayName = (nickname ? nickname : username);

          tableHtml += [
            '<td>',
              '<a href="/player/' + username + '" target="_blank">',
                '<span><img class="face-thumb" src="/face/16/' + username + '.png">' + displayName + '</span>',
              '</a>',
            '</td>'
          ].join('');
        }

        // Three columns per row, same as ingame
        if ((i + 1) % 3 == 0) {
          tableHtml += '</tr><tr>';
        }
      }
      tableHtml += "</tr>";

      $('.players-table').html(tableHtml);
    };

    this.socketInitialized = function() {
      this.socket.on('unauthorized', function() {
        this.addOutputLine("ERROR: you are not authorized!");
      }.bind(this));

      this.socket.on('connection-spam', function() {
        this.addOutputLine("Stop trying to connect so much!");
        this.addOutputLine("Try again in a few minutes...");
      }.bind(this));

      this.socket.on('chat-spam', function() {
        this.addOutputLine("Stop typing so fast!");
      }.bind(this));

      this.socket.on('chat', function(data) {
        if (data.line) {
          this.addOutputLine(data.line);
        } else if (data.batch) {
          this.addOutputLines(data.batch);
        }
      }.bind(this));

      // Renders a table almost identical looking to the tab player table ingame
      this.socket.on('server-status', function(data) {
        var players = data.players;
        var maxPlayers = data.maxPlayers;

        players = players.sort(function(a, b) {
          a = (a.nickname ? a.nickname : a.username);
          b = (b.nickname ? b.nickname : b.username);

          if (a.toLowerCase() < b.toLowerCase()) return -1;
          if (a.toLowerCase() > b.toLowerCase()) return 1;
          return 0;
        });

        this.renderPlayerTable(players, maxPlayers);
      }.bind(this));
    }.bind(this);

    this.messageEntered = function(socket, input) {
      socket.emit('chat-input', {
        message: input
      });
    };

    this.renderPlayerTable([], 90);
  };

  ConsoleStream.prototype = Object.create(ServerStream.prototype);
  ChatStream.prototype = Object.create(ServerStream.prototype);

  StandardWeb.realtime.ConsoleStream = ConsoleStream;
  StandardWeb.realtime.ChatStream = ChatStream;
})(window, document, $);
