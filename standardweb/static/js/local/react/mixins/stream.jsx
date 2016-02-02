(function(window, document, $) {
  StandardWeb.reactMixins.StreamMixin = {

    mentionPat: '(&gt;(?!.+&lt;).*|Server] .*|Web Chat].*: .*|To group.*|command:.*)(MENTION_PART)',
    numLines: 0,
    mentions: [],
    nextMentionSoundTime: 0,
    focused: true,
    commandIndex: -1,
    commandHistory: [],

    addOutputLine: function(line) {
      return this.addOutputLines([line]);
    },

    sendActivity: function(isActive) {
      this.state.socket.emit('user-activity', {
        active: isActive
      });
    },

    isAtBottom: function() {
      return this.$outputArea.get(0).scrollHeight - this.$outputArea.scrollTop() == this.$outputArea.outerHeight();
    },

    scrollToBottom: function() {
      this.$outputArea.scrollTop(this.$outputArea.get(0).scrollHeight);
    },

    scrollToBottomIfAtBottom: function(callback) {
      if (this.isAtBottom()) {
        callback();

        this.scrollToBottom();
      } else {
        callback();
      }
    },

    handleServerStatus: function(data) {
      var players = data.players.sort(function (a, b) {
        a = (a.nickname ? a.nickname : a.username);
        b = (b.nickname ? b.nickname : b.username);

        if (a.toLowerCase() < b.toLowerCase()) return -1;
        if (a.toLowerCase() > b.toLowerCase()) return 1;
        return 0;
      });

      var users = data.users.sort(function (a, b) {
        if (a.username.toLowerCase() < b.username.toLowerCase()) return -1;
        if (a.username.toLowerCase() > b.username.toLowerCase()) return 1;
        return 0;
      });

      this.setState({
        serverDetails: {
          numPlayers: data.numPlayers,
          maxPlayers: data.maxPlayers,
          load: data.load,
          tps: data.tps,
          users: users,
          players: players
        }
      });
    },

    addHistory: function(input) {
      this.commandHistory.unshift(input);
      this.commandIndex = -1;
    },

    handleHistoryUp: function() {
      if (this.commandIndex < this.commandHistory.length - 1) {
        this.commandIndex++;
        this.setState({inputValue: this.commandHistory[this.commandIndex]});
      }
    },

    handleHistoryDown: function() {
      if (this.commandIndex > -1) {
        this.commandIndex--;
        this.setState({inputValue: this.commandHistory[this.commandIndex]});
      }
    },

    handleMuteToggle: function() {
      if (this.state.muted) {
        StandardWeb.sounds.mentionSound.play();
      }

      this.setState({muted: !this.state.muted});
    },

    handleInputChange: function(inputValue) {
      this.setState({inputValue: inputValue});
    },

    handleInputEntered: function(input) {
      this.emitInput(input);

      this.addHistory(input);
      this.setState({inputValue: ''});

      this.scrollToBottom();
    },

    handleStreamContent: function(data) {
      if (data.line) {
        this.addOutputLine(data.line);
      } else if (data.batch) {
        this.addOutputLines(data.batch);
      }
    },

    trimTopLines: function(num) {
      $('li:lt(' + num + ')', this.$outputArea).remove();
    },

    addOutputLines: function(lines) {
      var shouldScroll = this.isAtBottom();

      // HTML hack since using React to render thousands of lines every time is very slow
      var htmlLines = lines.map(function(line) {
        return '<li>' + this.postProcessLine(line) + '</li>';
      }.bind(this));

      this.$outputArea.append(htmlLines.join(''));

      if (this.numLines + lines.length > this.maxLines) {
        this.trimTopLines(this.numLines + lines.length - this.maxLines);
        this.numLines = this.maxLines;
      } else {
        this.numLines += lines.length;
      }

      // Scroll to see the new line of text if the bottom was already visible
      if (shouldScroll) {
        this.scrollToBottom();
      }
    },

    postProcessLine: function(line) {
      var playSound = false;

      var i;
      for (i = 0; i < this.mentions.length; ++i) {
        var mention = this.mentions[i];

        if (!this.state.muted && StandardWeb.sounds.mentionSound
              && !this.focused && line.match(mention.regex)) {
          playSound = true;
        }

        if (mention.style) {
          line = line.replace(
            mention.regex,
            '$1<span style="' + mention.style + '">$2</span>'
          );
        }
      }

      var now = new Date().getTime();

      if (playSound && now > this.nextMentionSoundTime) {
        this.nextMentionSoundTime = now + 1000;
        StandardWeb.sounds.mentionSound.play();
      }

      line = line.replace(
        /(.+: )(.+)( issued server command)/,
        '$1<span style="color: #00b1ff">$2</span><span style="color: #9fe7ff">$3</span>'
      );

      line = line.replace(
        /(WARN)\]/,
        '<span style="color: #ffde81">$1</span>]'
      );

      line = line.replace(
        /(ERROR)\]/,
        '<span style="color: #bb0500">$1</span>]'
      );

      return line;
    },

    addRegexMention: function(regex, style) {
      this.mentions.push({
        regex: regex,
        style: style
      });
    },

    addChatMention: function(string, style) {
      var replacedPat = this.mentionPat.replace('MENTION_PART', string);
      var regex = new RegExp(replacedPat, 'gi');

      this.addRegexMention(regex, style);
    },

    connect: function() {
      StandardWeb.realtime.subscribe(this.streamSource, {serverId: this.serverId}, function(error, socket) {
        if (error) {
          this.setState({status: 'connection-failure'});
          this.addOutputLine("ERROR: connection failure!");
          return;
        }

        this.setState({
          status: 'connected',
          socket: socket
        });

        this.socketInitialized();

        socket.on('disconnect', function() {
          this.setState({status: 'disconnected'});
          this.addOutputLine("ERROR: socket connection lost!");
        }.bind(this));

        socket.on('mc-connection-lost', function() {
          this.setState({status: 'mc-connection-lost'});
          this.addOutputLine("Connection to Minecraft server lost, retrying...");
        }.bind(this));

        $(window).focus(function() {
          if (!this.focused) {
            this.sendActivity(true);
          }

          this.focused = true;
        }.bind(this));

        $(window).blur(function() {
          if (this.focused) {
            this.sendActivity(false);
          }

          this.focused = false;
        }.bind(this));
      }.bind(this));
    }
  };
})(window, document, $);
