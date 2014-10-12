(function(window, document, $) {
  $(document).ready(function () {
    var hash = window.location.hash ? window.location.hash.substring(1) : null;

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

          $refreshImage.attr('src', '/static/images/spinner.gif');
          $content.fadeTo(0, 0.25).load('player_list', function() {
            $refreshImage.attr('src', '/static/images/refresh.png');
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

    $('.fromnow').each(function() {
      var val;
      var now = moment();
      var date = moment($.trim($(this).text()));

      if (date.isValid()) {
        if (now.diff(date, 'days') > 365) {
          val = date.format('MMMM D, YYYY');
        } else {
          val = date.fromNow();
        }

        $(this).text(val);
        $(this).attr('title', date.format('LLL'));
      }
    });

    $('.placeholder').placeholder();
    $('.tooltip').tipsy();
  });
})(window, document, $);
