(function(window, document, $) {

  StandardWeb.reactComponents.Messages = React.createClass({
    messagesMap: {},

    getInitialState: function() {
      var urlPart = window.location.href.match(/messages\/(.+)$/);
      var selectedUsername = null;
      var mode = 'user';

      if (urlPart) {
        if (urlPart[1] === 'new') {
          mode = 'new-message';
        } else {
          selectedUsername = urlPart[1];
        }
      }

      return {
        selectedUsername: selectedUsername,
        mode: mode,
        contacts: [],
        messages: []
      };
    },

    componentDidMount: function() {
      this.fetchContacts();
      this.fetchMessages(this.state.selectedUsername);

      StandardWeb.realtime.subscribe('messages', function (error, socket) {
        if (error) {
          return;
        }

        socket.on('new', this.handleNewMessage.bind(this));
      }.bind(this));
    },

    addMessage: function(message) {
      this.state.messages.push(message);
      this.setState({messages: this.state.messages});
    },

    fetchContacts: function() {
      $.ajax({
        url: '/messages/contacts.json',
        success: this.handleContacts.bind(this)
      });
    },

    fetchMessages: function(username) {
      if (!username) {
        return;
      }

      $.ajax({
        url: '/messages/' + username + '.json',
        success: this.handleMessages.bind(this)
      });
    },

    handleContacts: function(data) {
      this.setState({
        contacts: data.contacts
      });
    },

    handleMessages: function(data) {
      this.messagesMap[data.username] = data.messages;

      this.setState({
        messages: data.messages,
        selectedUsername: data.username,
        mode: 'user'
      });
    },

    handleContactSelected: function(contact) {
      var existingMessages = this.messagesMap[contact.username] || [];

      this.fetchMessages(contact.username);

      contact.new_message = false;

      window.history.pushState('', '', '/messages/'+ contact.username);
      this.setState({
        selectedUsername: contact.username,
        mode: 'user',
        contacts: this.state.contacts,
        messages: existingMessages
      });
    },

    handleCreateNewMessage: function() {
      window.history.pushState('', '', '/messages/new');
      this.setState({
        selectedUsername: null,
        mode: 'new-message',
        messages: []
      });
    },

    handleNewMessageToUser: function(contact) {
      this.handleContactSelected(contact);
    },

    handleNewMessage: function (data) {
      StandardWeb.sounds.mentionSound.play();

      var message = data.message;
      var messageUsername = message.from_user.username || message.from_user.player.username;

      if (messageUsername === this.state.selectedUsername) {
        $.ajax({
          url: '/messages/mark_read',
          type: 'POST',
          data: {username: messageUsername}
        });

        this.addMessage(message);
      }

      this.updateContactFromMessage(messageUsername, message);
    },

    handleSendMessage: function(value) {
      $.ajax({
        url: '/messages/' + this.state.selectedUsername + '/new',
        type: 'POST',
        data: {body: value},
        success: function(data) {
          if (data.error) {
            // TODO: show error
          } else {
            var i;
            for (i = 0; i < this.state.messages.length; ++i) {
              if (!this.state.messages[i].seen_at) {
                this.state.messages[i].seen_at = new Date();
              }
            }

            this.addMessage(data.message);
          }
        }.bind(this)
      });
    },

    getContact: function(username) {
      var i;
      var contacts = this.state.contacts.slice();

      for (i = 0; i < contacts.length; ++i) {
        if (contacts[i].username === username) {
          return contacts[i];
        }
      }

      return null;
    },

    updateContactFromMessage: function(username, message) {
      var contact = this.getContact(username);

      if (contact) {
          contact.last_message_id = message.id;
          contact.last_message_date = message.sent_at;
          contact.new_message = true;
      } else {
        contact = {
          user: message.user,
          username: username,
          last_message_id: message.id,
          last_message_date: message.sent_at,
          new_message: true
        };

        this.state.contacts.push(contact);
      }

      this.setState({contacts: this.state.contacts});
    },

    render: function() {
      return (
        <div className="messages-section">
          <ContactList contacts={this.state.contacts}
            selectedUsername={this.state.selectedUsername}
            mode={this.state.mode}
            onContactSelected={this.handleContactSelected}
            onCreateNewMessage={this.handleCreateNewMessage}
          />
          <Content selectedUsername={this.state.selectedUsername}
            mode={this.state.mode}
            messages={this.state.messages}
            onSendMessage={this.handleSendMessage}
            onNewMessageToUser={this.handleNewMessageToUser}
          />
        </div>
      );
    }
  });

  var ContactList = React.createClass({

    renderContact: function(contact) {
      return (
        <Contact contact={contact}
          selectedUsername={this.props.selectedUsername}
          onContactSelected={this.handleContactSelected}
        />
      );
    },

    handleCreateNewMessage: function(e) {
      e.preventDefault();
      return this.props.onCreateNewMessage();
    },

    handleContactSelected: function(contact) {
      return this.props.onContactSelected(contact);
    },

    render: function() {
      var contacts = this.props.contacts.sort(function(a, b) {
        return b.last_message_id - a.last_message_id;
      });

      if (this.props.selectedUsername) {
        var i;
        var existing = false;
        for (i = 0; i < contacts.length; ++i) {
          if (contacts[i].username === this.props.selectedUsername) {
            existing = true;
            break;
          }
        }

        if (!existing) {
          contacts.splice(0, 0, {username: this.props.selectedUsername});
        }
      }

      return (
        <div className="messages-contacts">
          <a href="#" onClick={this.handleCreateNewMessage}>
            <div className={'contact ' + (this.props.mode === 'new-message' ? 'active' : '')}>
              <i className="fa fa-plus"></i> New message
            </div>
          </a>
          {contacts.map(this.renderContact)}
        </div>
      );
    }
  });

  var Contact = React.createClass({

    componentDidMount: function() {
      StandardWeb.refreshFromnow($(React.findDOMNode(this)));
    },

    componentDidUpdate: function() {
      StandardWeb.refreshFromnow($(React.findDOMNode(this)));
    },

    handleClick: function(e) {
      e.preventDefault();
      return this.props.onContactSelected(this.props.contact);
    },

    renderName: function() {
      var contact = this.props.contact;

      if (contact.player) {
        return (
          <div className="name">
            <span dangerouslySetInnerHTML={{__html: contact.player.displayname_html}}>
            </span> {contact.player.nickname ? '(' + contact.player.username + ')' : ''}
          </div>
        );
      } else {
        return (
          <div className="name">
            {contact.username}
          </div>
        );
      }
    },

    render: function() {
      var contact = this.props.contact;
      var classes = 'contact';

      if (this.props.selectedUsername === contact.username) {
        classes += ' active';
      }
      if (contact.new_message) {
        classes += ' new';
      }

      return (
        <a href="#" onClick={this.handleClick}>
          <div className={classes}>
            {this.renderName()}
            {contact.last_message_date ? (
              <div className="time fromnow">
               {contact.last_message_date}
              </div>
            ) : ''}
          </div>
        </a>
      );
    }
  });

  var Content = React.createClass({

    handleNewMessageToUser: function(contact) {
      return this.props.onNewMessageToUser(contact);
    },

    handleSendMessage: function(value) {
      return this.props.onSendMessage(value);
    },

    render: function() {
      if (this.props.mode === 'new-message') {
        return (
          <div className="messages-content">
            <NewMessage onNewMessageToUser={this.handleNewMessageToUser} />
          </div>
        );
      } else {
        return (
          <div className="messages-content">
            <MessageList messages={this.props.messages}
              selectedUsername={this.props.selectedUsername}
            />
            <ReplyArea onSendMessage={this.handleSendMessage}/>
          </div>
        );
      }
    }
  });

  var NewMessage = React.createClass({

    searchTimeout: null,

    getInitialState: function() {
      return {
        searchResults: []
      }
    },

    searchContacts: function(query) {
      var data = {query: query};

      $.ajax({
        url: '/api/v1/contact_query',
        data: data,
        success: function(data) {
          this.setState({
            searchResults: data.contacts
          });
        }.bind(this)
      });
    },

    handleChange: function(e) {
      var value = e.target.value;

      if (this.searchTimeout) {
        clearInterval(this.searchTimeout);
      }

      this.searchTimeout = setTimeout(function() {
        this.searchContacts(value);
      }.bind(this), 100);
    },

    handleNewMessageToUser: function(contact) {
      this.props.onNewMessageToUser(contact);
    },

    renderSearchResult: function(contact) {
      return (
        <NewMessageContact contact={contact}
          onNewMessageToUser={this.handleNewMessageToUser}
        />
      );
    },

    render: function() {
      return (
        <div>
          <div className="contact-chooser">
            New message to: <input type="text" autoFocus={true} onChange={this.handleChange}/>
          </div>
          <div className="search-results">
            {this.state.searchResults.map(this.renderSearchResult)}
          </div>
        </div>
      );
    }
  });

  var NewMessageContact = React.createClass({

    handleSearchResultClick: function(e) {
      e.preventDefault();

      this.props.onNewMessageToUser(this.props.contact);
    },

    render: function() {
      var contact = this.props.contact;

      return (
        <a href="#" onClick={this.handleSearchResultClick}>
          <div className="contact">
            {contact.player_id ? (
              <div>
                <img src={'/face/16/' + contact.username + '.png'} className="face-thumb" width="16" height="16" alt={contact.username}>
                </img> <span dangerouslySetInnerHTML={{__html: contact.displayname_html}}/>
                {contact.nickname ? '(' + contact.username + ')' : ''}
              </div>
            ) : (
              <div>{contact.username}</div>
            )}
          </div>
        </a>
      );
    }
  });

  var MessageList = React.createClass({

    componentDidUpdate: function() {
      var $list = $(React.findDOMNode(this.refs.messagesList));
      $list.scrollTop($list.prop("scrollHeight"));
    },

    renderMessage: function(message) {
      return (
        <Message message={message}/>
      );
    },

    render: function() {
      if (this.props.messages.length) {

        var messages = this.props.messages.sort(function(a, b) {
          return a.id - b.id;
        });

        return (
          <div className="message-list" ref="messagesList">
          {messages.map(this.renderMessage)}
          </div>
        );
      } else {
        return (
          <div className="help">
            {this.props.selectedUsername ? 'No messages yet, say hello!' : 'Select a contact from the left or hit "New message"'}
          </div>
        );
      }
    }
  });

  var MessageFrom = React.createClass({

    render: function () {
      if (this.props.self) {
        return (
          <h4>You</h4>
        );
      }

      var fromUser = this.props.fromUser;
      if (fromUser.player) {
        return (
          <h4>
            <a href={'/player/' + fromUser.player.uuid}>
              <img src={'/face/16/' + fromUser.player.username + '.png'} className="face-thumb" width="16" height="16" alt={fromUser.player.username}>
              </img> <span dangerouslySetInnerHTML={{__html: fromUser.player.displayname_html}}></span>
            </a> {fromUser.player.nickname ? '(' + fromUser.player.username + ')' : ''}
          </h4>
        );
      } else {
        return (
          <h4>{fromUser.username}</h4>
        );
      }
    }
  });

  var Message = React.createClass({
    componentDidMount: function() {
      StandardWeb.refreshFromnow($(React.findDOMNode(this)));
    },

    componentDidUpdate: function() {
      StandardWeb.refreshFromnow($(React.findDOMNode(this)));
    },

    render: function() {
      var message = this.props.message;

      var classes = 'message';
      var self = false;

      if (message.from_user.username === StandardWeb.username || (
          message.from_user.player && message.from_user.player.username === StandardWeb.username
        )) {
        classes += ' self';
        self = true;
      } else if (!message.seen_at) {
        classes += ' new';
      }

      return (
        <div className={classes}>
          <div className="time fromnow">
            {message.sent_at}
          </div>
          <MessageFrom fromUser={message.from_user}
            self={self}
          />
          <div className="message-body" dangerouslySetInnerHTML={{__html: message.body_html}}></div>
        </div>
      );
    }
  });

  var ReplyArea = React.createClass({
    handleClick: function(e) {
      var textarea = React.findDOMNode(this.refs.textarea);

      if (textarea.value) {
        this.props.onSendMessage(textarea.value);
        textarea.value = '';

        e.preventDefault();
      }
    },

    handleKeyUp: function(e) {
      if (e.keyCode == 13 && e.target.value) { // Enter
        this.props.onSendMessage(e.target.value);
        e.target.value = '';

        e.preventDefault();
      }
    },

    render: function() {
      return (
        <div className="reply">
          <button className="btn btn-lite" onClick={this.handleClick}>Send</button>
          <div className="textwrapper">
            <textarea placeholder="Enter message"
              autoFocus={true}
              ref="textarea"
              onKeyUp={this.handleKeyUp}
            />
          </div>
        </div>
      );
    }
  });
})(window, document, $);
