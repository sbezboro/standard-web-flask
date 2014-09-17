(function(window, document, $) {
  if (typeof Object.create === 'undefined') {
    Object.create = function (o) {
      function F() {
      }

      F.prototype = o;
      return new F();
    };
  }

  $.ajaxSetup({
    cache: false
  });
})(window, document, $);
