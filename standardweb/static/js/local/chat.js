(function(window, document, $) {
  StandardWeb.chat = {};

  $(document).ready(function() {
    var $chat = $('.chat-area');

    if (!$chat.length) {
      return;
    }

    var $chatTextbox = $('input[type="text"]');

    var chatStream = new StandardWeb.realtime.ChatStream($chat, $chatTextbox, StandardWeb.chat.serverId);
    chatStream.connect();

    soundManager.setup({
      url: '/static/flash/',
      flashVersion: 9,
      debugMode: false,
      preferFlash: false,
      onready: function() {
        var mentionSound = soundManager.createSound({
          id: 'mention',
          url: '/static/sound/mention.wav'
        });

        chatStream.setMentionSound(mentionSound);
      }
    });
  });
})(window, document, $);
