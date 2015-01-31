(function(window, document, $) {
  StandardWeb.notifications = {};

  $(document).ready(function() {
    if (!StandardWeb.notifications.active) {
      return;
    }

    var $readButton = $('.read');

    $readButton.on('click', function() {
      var $notification = $(this).closest('.notification');

      if (!$notification.hasClass('new')) {
        return false;
      }
      $notification.removeClass('new');

      var notificationId = $notification.data('id');
      $.ajax({
        url: '/notifications/read/' + notificationId,
        type: 'POST'
      })
    });
  });
})(window, document, $);
