if (typeof Object.create === 'undefined') {
  Object.create = function (o) {
    function F() {}
    F.prototype = o;
    return new F();
  };
}

$(document).ready(function() {
  var hash = window.location.hash ? window.location.hash.substring(1) : null;

  $('.extender').on('click', function() {
    var target = '#' + $(this).attr('data-target');
    $(target).toggle();
  });

  $(document).on('click', '.nav-pills a', function() {
    var $anchor = $(this);
    var id = $anchor.attr('href').substring(1);

    var $pill = $(this).closest('li');

    $('.nav-pills li').each(function() {
      var $otherPill = $(this);

      if ($otherPill[0] == $pill[0]) {
        $otherPill.addClass('active');
      } else {
        $otherPill.removeClass('active');
      }
    });

    $('.nav-section').each(function() {
      var $section = $(this);

      if ($section.attr('id') === id) {
        $section.addClass('active');
        $section.removeClass('hidden');
      } else {
        $section.addClass('hidden');
        $section.removeClass('active');
      }
    });
  });

  var activePill = $('.nav-pills li.active').length > 0;

  $('.nav-pills li').each(function(index) {
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

  $('.nav-section').each(function(index) {
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

  $(document).on('click', '.alert > .close', function() {
    $(this).closest('.alert').remove();
  });

  $("abbr.timeago").timeago();
  $(".placeholder").placeholder();
  $(".tooltip").tipsy();
});

$.ajaxSetup ({
  cache: false
});
