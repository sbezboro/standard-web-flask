(function(window, document, $) {
  StandardWeb.reactMixins.StreamAreaMixin = {

    componentDidMount: function() {
      $(document).keypress(this.handleRefocus);
    },

    handleRefocus: function() {
      var $focused = $(':focus');
      var $textbox = $(React.findDOMNode(this.refs.inputTextbox));

      if ($textbox != $focused) {
        $textbox.focus();
      }
    },

    handleMuteToggle: function(e) {
      this.props.onMuteToggle();
      e.preventDefault();
    },

    handleInputChange: function(e) {
      this.props.onInputChange(e.target.value);
      e.preventDefault();
    },

    handleInputKeyDown: function(e) {
      if (e.keyCode == 38) { // Up key
        this.props.onHistoryUp();
        e.preventDefault();
      } else if (e.keyCode == 40) { // Down key
        this.props.onHistoryDown();
        e.preventDefault();
      }
    },

    handleInputKeyUp: function(e) {
      if (e.keyCode == 13 && e.target.value) { // Enter
        this.props.onInputEntered(e.target.value);
        e.preventDefault();
      }
    }
  };
})(window, document, $);
