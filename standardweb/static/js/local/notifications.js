(function(window, document, $) {
  StandardWeb.notifications = {
    loading: false,
    oldestId: null
  };

  var $window;
  var $notificationsSection;

  StandardWeb.notifications.checkOlder = function() {
    if (StandardWeb.notifications.oldestId
        && !StandardWeb.notifications.loading
        && $window.scrollTop() >= $(document).height() - $window.height() - 50) {
      StandardWeb.notifications.loading = true;

      $notificationsSection.append('<div class="loading spinner-progress-bar"></div>');

      $.ajax({
        url: '/notifications/older',
        data: {
          older_than_id: StandardWeb.notifications.oldestId
        },
        success: function(data) {
          StandardWeb.notifications.loading = false;
          StandardWeb.notifications.oldestId = data.oldest_id;

          $('.loading', $notificationsSection).remove();
          $notificationsSection.append(data.html);

          StandardWeb.refreshFromnow($notificationsSection);
          StandardWeb.notifications.checkOlder();
        },
        failure: function() {
          StandardWeb.notifications.loading = false;

          $('.loading', $notificationsSection).remove();
        }
      });
    }
  };

  $(document).ready(function() {
    if (!StandardWeb.notifications.active) {
      return;
    }

    $window = $(window);
    $notificationsSection = $('.notifications-section');

    $(document).on('click', '.read', function() {
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

    $window.scroll(function() {
      StandardWeb.notifications.checkOlder();
    });

    StandardWeb.notifications.checkOlder();
  });
})(window, document, $);
