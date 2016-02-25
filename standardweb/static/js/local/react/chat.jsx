(function(window, document, $) {

  StandardWeb.reactComponents.LiveChat = React.createClass({
    mixins: [StandardWeb.reactMixins.StreamMixin],

    maxLines: 200,
    streamSource: 'chat',

    getInitialState: function() {
      return {
        status: 'connecting',
        muted: false,
        serverDetails: {
          maxPlayers: 100,
          players: [],
          users: []
        }
      };
    },

    componentDidMount: function() {
      this.$outputArea = $('.chat', $(React.findDOMNode(this)));
      $(document).keypress(this.handleRefocus);

      this.serverId = StandardWeb.chat.serverId;

      this.connect();
    },

    emitInput: function(input) {
      var data = {
        message: input
      };

      this.state.socket.emit('chat-input', data);
    },

    handleUnauthorized: function() {
      this.addOutputLine("ERROR: you are not authorized!");
    },

    handleConnectionSpam: function() {
      this.addOutputLine("Stop trying to connect so much!");
      this.addOutputLine("Try again in a few minutes...");
    },

    handleChatSpam: function() {
      this.addOutputLine("Stop typing so fast!");
    },

    socketInitialized: function() {
      if (StandardWeb.username) {
        this.addChatMention(StandardWeb.username, 'background:#00ACC4');
      }
      if (StandardWeb.nickname) {
        this.addChatMention(StandardWeb.nickname, 'background:#00ACC4');
      }

      this.state.socket.on('unauthorized', this.handleUnauthorized);
      this.state.socket.on('connection-spam', this.handleConnectionSpam);
      this.state.socket.on('chat-spam', this.handleChatSpam);
      this.state.socket.on('chat', this.handleStreamContent);
      this.state.socket.on('server-status', this.handleServerStatus);
    },

    render: function () {
      return (
        <div>
          <h2>Live Server Chat</h2>
          <div className="live-chat">
            <ChatArea status={this.state.status}
              muted={this.state.muted}
              inputValue={this.state.inputValue}
              onMuteToggle={this.handleMuteToggle}
              onInputChange={this.handleInputChange}
              onHistoryUp={this.handleHistoryUp}
              onHistoryDown={this.handleHistoryDown}
              onInputEntered={this.handleInputEntered}
            />
          </div>
          <UserTable users={this.state.serverDetails.users}
            title='Web chat users'
          />
          <UserTable users={this.state.serverDetails.players}
            title='Players online'
          />
        </div>
      );
    }
  });

  var ChatArea = React.createClass({
    mixins: [StandardWeb.reactMixins.StreamAreaMixin],

    render: function() {
      var muteTooltip;
      if (this.props.muted) {
        muteTooltip = "Unmute mention sounds";
      } else {
        muteTooltip = "Mute mention sounds";
      }

      return (
        <div>
          <a href="#" className="mute tooltip" title={muteTooltip} data-tooltip-gravity="e" onClick={this.handleMuteToggle}>
            <i className={'fa ' + (this.props.muted ? 'fa-volume-off' : 'fa-volume-up')}></i>
          </a>
          <div className="chat"></div>
          <input className="chat-textbox"
            type="text"
            maxlength="80"
            ref="inputTextbox"
            value={this.props.inputValue}
            onChange={this.handleInputChange}
            onKeyDown={this.handleInputKeyDown}
            onKeyUp={this.handleInputKeyUp}/>
        </div>
      );
    }
  });

  var UserTable = React.createClass({

    renderCell: function(cellNum, user) {
      if (!user) {
        return (<div key={'cell-' + cellNum}> </div>);
      }

      var username = user.username;
      var nickname = user.nickname;
      var address = user.address;

      var displayName = (nickname ? nickname : username);

      var activeClass = '';
      if (user.hasOwnProperty('active')) {
        activeClass = user.active ? 'active': 'inactive'
      }

      return (
        <div key={'cell-' + cellNum} className={'col-1-4 player-cell ' + activeClass}>
          <a href={'/' + StandardWeb.chat.serverId + '/player/' + username} target="_blank">
            <span><img className="face-thumb" src={'/face/16/' + username + '.png'}/>{displayName}</span>
          </a>
          <span className="address">{address ? address : ''}</span>
        </div>
      );
    },

    render: function() {
      var cells = [];

      var i;
      for (i = 0; i < this.props.users.length; ++i) {
        cells.push(
          this.renderCell(i, this.props.users[i])
        );
      }

      if (cells.length == 0) {
        return <div></div>;
      }

      return (
        <div>
          <h3>{this.props.title}</h3>
          <div className="players-table grid flush">
            {cells}
          </div>
        </div>
      );
    }
  });
})(window, document, $);
