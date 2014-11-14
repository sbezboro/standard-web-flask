(function(window, document, $) {
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
  });
})(window, document, $);