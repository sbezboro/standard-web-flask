(function(window, document, $) {
  $(document).ready(function () {
    var hash = window.location.hash ? window.location.hash.substring(1) : null;

    $('.dropdown .toggle').on('click', function() {
      var $this = $(this);
      var $dropdown = $this.closest('.dropdown');
      var $options = $('.options', $dropdown);

      $dropdown.toggleClass('open');
      $options.toggle();

      return false;
    });

    $(document).on('mouseup', function(e) {
      var $dropdownOptions = $('.dropdown .options');

      if ($dropdownOptions.attr('display') !== 'none') {
        var $dropdown = $dropdownOptions.closest('.dropdown');

        if (!$dropdownOptions.is(e.target) && $dropdownOptions.has(e.target).length === 0) {
          $dropdown.removeClass('open');
          $dropdownOptions.hide();
        }
      }
    });

    $('.extender').on('click', function () {
      var target = '#' + $(this).attr('data-target');
      $(target).toggle();
    });

    $(document).on('click', '.nav-pills a', function () {
      var $anchor = $(this);
      var id = $anchor.attr('href').substring(1);

      var $pill = $(this).closest('li');

      $('.nav-pills li').each(function () {
        var $otherPill = $(this);

        if ($otherPill[0] == $pill[0]) {
          $otherPill.addClass('active');
        } else {
          $otherPill.removeClass('active');
        }
      });

      $('.nav-section').each(function () {
        var $section = $(this);

        if ($section.attr('id') === id) {
          $section.addClass('active');
          $section.removeClass('hidden');
        } else {
          $section.addClass('hidden');
          $section.removeClass('active');
        }
      });

      return false;
    });

    var activePill = $('.nav-pills li.active').length > 0;

    $('.nav-pills li').each(function (index) {
      var $pill = $(this);

      if (!activePill) {
        if (hash) {
          if (hash === $pill.children('a').attr('href').substring(1)) {
            $pill.addClass('active');
          }
        } else if (index == 0) {
          $pill.addClass('active');
        }
      }
    });

    $('.nav-section').each(function (index) {
      var $section = $(this);

      if (activePill) {
        if (!$section.hasClass('active')) {
          $section.addClass('hidden');
        }
      } else if (hash) {
        if (hash != $section.attr('id')) {
          $section.addClass('hidden');
        }
      } else if (index > 0) {
        $section.addClass('hidden');
      }
    });

    $(document).on('click', '.alert > .close', function () {
      $(this).closest('.alert').remove();
    });

    $(document).on('click', 'a.confirm', function () {
      return confirm($(this).attr('data-confirm-message') || 'Are you sure?');
    });

    $('.player-list').each(function() {
      var $playerList = $(this);

      var $refreshButton = $('.refresh-button', $playerList);
      var $refreshImage = $('.refresh-image', $playerList);
      var $content = $('.player-list-players', $playerList);

      var loading = false;

      function refresh() {
        if (!loading) {
          loading = true;

          $refreshImage.attr('src', StandardWeb.cdnDomain + '/static/images/spinner.gif');
          $content.fadeTo(0, 0.25).load('player_list', function() {
            $refreshImage.attr('src', StandardWeb.cdnDomain +'/static/images/refresh.png');
            $content.fadeTo(100, 1);
            loading = false;
          });
        }
      }

      $refreshButton.on('click', refresh);
      refresh();
    });

    $('.clipboard').each(function() {
      var $elem = $(this);

      $elem.tipsy({
        trigger: 'manual',
        gravity: 'w',
        offset: 10
      });

      var clipboard = new ZeroClipboard($elem, {
        moviePath: '/static/flash/ZeroClipboard.swf'
      });

      clipboard.on('complete', function(client, args) {
        $elem.tipsy('hide');
        $elem.attr('original-title', 'Copied!');
        $elem.tipsy('show');

        mixpanel.track('address copied');
      });

      clipboard.on('mouseover', function(client) {
        $elem.attr('original-title', 'Click to copy to clipboard');
        $elem.tipsy('show');
      });

      clipboard.on('mouseout', function(client) {
        $elem.tipsy('hide');
      });
    });

    StandardWeb.realtime.subscribe('messages', function(error, socket) {
      if (error) {
        return;
      }

      socket.on('unread-count', function(data) {
        var count = data.count;

        var $account = $('#account');
        var $messages = $account.find('.messages');
        var $messagesCount = $account.find('.messages .new-count');

        if (count && !$messages.hasClass('new')) {
          $messages.addClass('new');
        } else if (!count && $messages.hasClass('new')) {
          $messages.removeClass('new');
        }

        $messagesCount.html(count);
      }.bind(this));
    });

    StandardWeb.refreshFromnow();

    $('.placeholder').placeholder();
    $('.tooltip').tipsy();
  });
})(window, document, $);
