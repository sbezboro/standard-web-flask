(function(window, document, $) {

  StandardWeb.reactComponents.AdminPanel = React.createClass({
    mixins: [StandardWeb.reactMixins.StreamMixin],
    maxLines: 4000,
    streamSource: 'console',

    getInitialState: function() {
      return {
        status: 'connecting',
        lines: [],
        selectedPlayer: null,
        muted: false,
        serverDetails: {
          numPlayers: '-',
          maxPlayers: '-',
          tps: '-',
          load: '-',
          players: []
        }
      };
    },

    componentDidMount: function() {
      this.$outputArea = $('.console', $(React.findDOMNode(this)));
      this.$panel = $(React.findDOMNode(this));

      this.serverId = StandardWeb.admin.serverId;

      $(window).resize(this.handleResize);

      this.handleResize();

      this.connect();
    },

    handleResize: function() {
      this.$panel.height($(window).height() - this.$panel.offset().top);
    },

    handleMuteToggle: function() {
      if (this.state.muted) {
        StandardWeb.sounds.mentionSound.play();
      }

      this.setState({muted: !this.state.muted});
    },

    handleInputEntered: function(input) {
      var data = {};

      if (input[0] == "/") {
        data.command = input.substring(1, input.length);
      } else {
        data.message = input;
      }

      this.state.socket.emit('console-input', data);

      this.addHistory(input);
      this.setState({inputValue: ''});
    },

    handlePlayerSelected: function(player) {
      if (this.state.selectedPlayer && this.state.selectedPlayer.uuid == player.uuid) {
        player = null;
      }

      var callback;
      if (this.isAtBottom()) {
        callback = this.scrollToBottom;
      }

      this.setState({selectedPlayer: player}, callback);
    },

    handleCloseDetail: function() {
      this.setState({selectedPlayer: null});
    },

    handleSetDonator: function() {
      this.state.socket.emit('set-donator', {
        uuid: this.state.selectedPlayer.uuid
      });
    },

    handleConsoleContent: function(data) {
      if (data.line) {
        this.addOutputLine(data.line);
      } else if (data.batch) {
        this.addOutputLines(data.batch);
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

      this.setState({
        serverDetails: {
          numPlayers: data.numPlayers,
          maxPlayers: data.maxPlayers,
          load: data.load,
          tps: data.tps,
          players: players
        }
      });
    },

    socketInitialized: function() {
      this.setState({
        status: 'connected'
      });

      this.addChatMention('server', 'background:#A0A');
      // A player messaging console
      this.addRegexMention('-&gt; me');

      this.state.socket.on('console', this.handleConsoleContent);
      this.state.socket.on('server-status', this.handleServerStatus);
    },

    render: function () {
      return (
        <div className="admin-panel">
          <div className="sub-header">
            <ul>
              <li>
                <div>Players {this.state.serverDetails.numPlayers}/{this.state.serverDetails.maxPlayers}
                </div>
              </li>
              <li>
                <div>TPS {this.state.serverDetails.tps}
                </div>
              </li>
              <li>
                <div>Load {this.state.serverDetails.load}
                </div>
              </li>
            </ul>
          </div>
          <ConsoleArea lines={this.state.lines}
            status={this.state.status}
            selectedPlayer={this.state.selectedPlayer}
            muted={this.state.muted}
            inputValue={this.state.inputValue}
            onMuteToggle={this.handleMuteToggle}
            onInputChange={this.handleInputChange}
            onHistoryUp={this.handleHistoryUp}
            onHistoryDown={this.handleHistoryDown}
            onInputEntered={this.handleInputEntered}
          />
          {this.state.selectedPlayer ? (
            <PlayerDetail player={this.state.selectedPlayer}
              status={this.state.status}
              serverId={this.serverId}
              onCloseDetail={this.handleCloseDetail}
              onSetDonator={this.handleSetDonator}
            />
          ): ''}
          <PlayerArea players={this.state.serverDetails.players}
            status={this.state.status}
            selectedPlayer={this.state.selectedPlayer}
            onPlayerSelected={this.handlePlayerSelected} />
        </div>
      );
    }
  });

  var ConsoleArea = React.createClass({

    componentDidMount: function() {
      $(document).keypress(this.handleRefocus);
    },

    handleRefocus: function() {
      var $focused = $(':focus');
      var $textbox = $(React.findDOMNode(this.refs.inputTextbox));

      if ($textbox != $focused) {
        $textbox.focus();
      }
    },

    handleMuteToggle: function() {
      this.props.onMuteToggle();
    },

    handleInputChange: function(e) {
      this.props.onInputChange(e.target.value);
      e.preventDefault();
    },

    handleInputKeyDown: function(e) {
      if (e.keyCode == 38) { // Up key
        this.props.onHistoryUp();
        e.preventDefault();
      } else if (e.keyCode == 40) { // Down key
        this.props.onHistoryDown();
        e.preventDefault();
      }
    },

    handleInputKeyUp: function(e) {
      if (e.keyCode == 13 && e.target.value) { // Enter
        this.props.onInputEntered(e.target.value);
        e.preventDefault();
      }
    },

    render: function() {
      var muteTooltip;
      if (this.props.muted) {
        muteTooltip = "Unmute notification sounds";
      } else {
        muteTooltip = "Mute notification sounds";
      }

      return (
        <div className={'admin-left ' + (this.props.selectedPlayer ? 'detail-active' : '')}>
          <a href="#" className="mute tooltip" title={muteTooltip} data-tooltip-gravity="e" onClick={this.handleMuteToggle}>
            <i className={'fa ' + (this.props.muted ? 'fa-volume-off' : 'fa-volume-up')}></i>
          </a>
          <div className="console"></div>
          <input className="console-textbox"
            type="text"
            ref="inputTextbox"
            value={this.props.inputValue}
            onChange={this.handleInputChange}
            onKeyDown={this.handleInputKeyDown}
            onKeyUp={this.handleInputKeyUp}
            disabled={this.props.status !== 'connected'}/>
        </div>
      );
    }
  });

  var PlayerArea = React.createClass({

    handlePlayerClick: function(player) {
      this.props.onPlayerSelected(player);
    },

    renderPlayer: function(player) {
      return (
        <PlayerRow key={player.uuid}
          player={player}
          selected={this.props.selectedPlayer && this.props.selectedPlayer.uuid == player.uuid}
          onPlayerClick={this.handlePlayerClick} />
       );
    },

    render: function() {
      return (
        <div className="admin-right">
          <div className="players">{this.props.players.map(this.renderPlayer)}</div>
        </div>
      );
    }
  });

  var PlayerRow = React.createClass({

    handlePlayerClick: function(e) {
      this.props.onPlayerClick(this.props.player);
      e.preventDefault();
    },

    render: function() {
      var player = this.props.player;
      var nicknameAnsi = player.nicknameAnsi;
      var displayName = nicknameAnsi ? nicknameAnsi : player.username;

      return (
        <a href="#" onClick={this.handlePlayerClick}>
          <div className={'player ' + (this.props.selected ? 'selected' : '')}>
            <img className="face-thumb" src={'/face/16/' + player.username + '.png'} />
            <span className="ansi-container" dangerouslySetInnerHTML={{__html: displayName}}></span>
            <span className="rank">{'#' + player.rank}</span>
          </div>
        </a>
      );
    }
  });

  var PlayerDetail = React.createClass({

    handleClose: function(e) {
      this.props.onCloseDetail();
      e.preventDefault();
    },

    handleSetDonator: function(e) {
      this.props.onSetDonator(this.props.player);
      e.preventDefault();
    },

    timeSpentString: function(player) {
      var hours = Math.floor(player.time_spent / 60);
      var minutes = hours > 0 ? (player.time_spent % (hours * 60)) : player.time_spent;

      if (hours) {
        return hours + (hours == 1 ? ' hour ' : ' hours ')
          + minutes + (minutes == 1 ? ' minute ' : ' minutes');
      } else {
        return minutes + (minutes == 1 ? ' minute ' : ' minutes');
      }
    },

    renderTitle: function(title) {
      return <span key={title.name}> {title.name} </span>;
    },

    render: function() {
      var player = this.props.player;

      var username;
      var displayname;

      if (player.nickname) {
        username = <span>{'(' + player.username + ')'}</span>;
        displayname = (
          <span className="ansi-container" dangerouslySetInnerHTML={{__html: player.nicknameAnsi}}></span>
        );
      } else {
        username = '';
        displayname = player.username;
      }

      var location = '[' + player.world + '] ' + player.x + ', ' + player.y + ', ' + player.z;

      return (
        <div className="detail">
          <div className="detail-inner">
            <a className="close" href="#" onClick={this.handleClose}>
              <i className="fa fa-times"></i>
            </a>
            <img className="face" src={'/face/64/' + player.username + '.png'} />
            <h3 className="display-name">
              <a className="link" target="_blank" href={'/' + this.props.serverId + '/player/' + player.username}>
                {displayname}
              </a>
            </h3>
            <div>{username}</div>
            <br/>
            <div className="stats">
              <div>
                <b>Rank</b>
                <span className="stat-value">{player.rank}</span>
              </div>
              <div>
                <b>Time Spent</b>
                <span className="stat-value">{this.timeSpentString(player)}</span>
              </div>
              <div>
                <b>IP Address</b>
                <span className="stat-value">
                  <a href={'http://whatismyipaddress.com/ip/' + player.address}>{player.address}</a>
                </span>
              </div>
            </div>
            <div className="stats">
              <div>
                <b>Health</b>
                <span className="stat-value">{player.health.toFixed(2)}</span>
              </div>
              <div>
                <b>Location</b>
                <span className="stat-value">{location}</span>
              </div>
              <div>
                <b>Titles</b>
                <span className="stat-value">{player.titles.map(this.renderTitle)}</span>
              </div>
            </div>
            <div className="options">
              <a className="btn donator" href="#" onClick={this.handleSetDonator}>Set Donator</a>
              <br/>
            </div>
          </div>
        </div>
      );
    }
  });
})(window, document, $);
