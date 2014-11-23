(function(window, document, $) {
  StandardWeb.messages = {};

  var $contactList;
  var $messageList;
  var $newMessageInput;
  var $searchResults;
  var searchTimeout;

  function searchContacts(query) {
    var data = {query: query};

    $.ajax({
      url: '/api/v1/contact_query',
      data: data,
      success: function(data) {
        var contacts = data.contacts;

        var html = '';

        var i;
        var contact;
        for (i = 0; i < contacts.length; ++i) {
          contact = contacts[i];

          html += [
            '<a href="/messages/' + contact.username + '">',
              '<div class="contact">',
                contact.player_id ? '<img class="face-thumb" src="/face/16/' + contact.username + '.png" width="16px" height="16px"> ' : ' ',
                contact.displayname_html,
                contact.nickname ? ' (' + contact.username + ')' : '',
              '</div>',
            '</a>'
          ].join('');
        }

        if (query && !html) {
          html = "<h4>No results</h4>";
        }

        $searchResults.html(html);
      }
    });
  }

  $(document).ready(function() {
    if (!$('.messages-section').length) {
      return;
    }

    $contactList = $('.messages-contacts');
    $messageList = $('.message-list');
    $newMessageInput = $('.contact-chooser input[type="text"]');
    $searchResults = $('.search-results');

    $messageList.scrollTop($messageList.prop("scrollHeight"));

    $newMessageInput.on('keyup', function() {
      if (searchTimeout) {
        clearInterval(searchTimeout);
      }

      searchTimeout = setTimeout(function() {
        searchContacts($newMessageInput.val());
      }, 100);
    });

    if ($newMessageInput.val()) {
      searchContacts($newMessageInput.val());
    }

    StandardWeb.realtime.subscribe('messages', function (error, socket) {
      if (error) {
        return;
      }

      socket.on('new', function (data) {
        var messageHtml = data.message_row_html;
        var fromUserId = data.from_user_id;
        var date = data.date;

        // Show new message in current conversation if the message is part of it
        if (fromUserId == StandardWeb.messages.otherUserId) {
          var $newMessage = $(messageHtml);

          $messageList.append($newMessage);
          $messageList.scrollTop($messageList.prop("scrollHeight"));

          StandardWeb.refreshFromnow($newMessage);

          $.ajax({
            url: '/api/v1/mark_messages_read',
            type: 'POST',
            data: {other_user_id: fromUserId}
          });
        }

        // Update the contact involved with this message, and shuffle to the top of the list if necessary
        var $anchor = null;
        $contactList.find('.contact').each(function() {
          if (fromUserId == $(this).data('user-id')) {
            if (fromUserId != StandardWeb.messages.otherUserId) {
              if (!$(this).hasClass('new')) {
                $(this).addClass('new');
              }

              $anchor = $(this).parent();
              $anchor.remove();
            }

            var $time = $(this).find('.time > span');
            $time.html(date);

            StandardWeb.refreshFromnow($anchor);
          }
        });

        if ($anchor) {
          $contactList.prepend($anchor);
        }
      }.bind(this));
    });
  });
})(window, document, $);
