(function(window, document, $) {
  StandardWeb.Dialog = function() {
    this.$dialog = null;

    this.show = function() {
      $('.modal-dialog').remove();
      this.$dialog = this.buildDialog();

      $('.close', this.$dialog).on('click', function() {
        this.close();
        return false;
      }.bind(this));

      $('body').append(this.$dialog);
    };

    this.close = function() {
      this.$dialog.remove();
    };
  };

  StandardWeb.SimpleDialog = function(text, buttonText) {
    StandardWeb.Dialog.call(this);

    this.text = text;
    this.buttonText = buttonText || 'OK';

    this.buildDialog = function() {
      return $(
        '<div class="modal-dialog">' +
          '<div class="dialog-inner">' +
            '<a href="#" class="close"><i class="fa fa-times"></i></a>' +
            '<p>' + this.text + '</p>' +
            '<div><a href="#" class="btn btn-lite close-dialog">' + this.buttonText + '</a></div>' +
          '</div>' +
        '</div>'
      );
    };
  };

  StandardWeb.InputDialog = function(text, inputLabelText, placeholderText, positiveButtonText, negativeButtonText) {
    StandardWeb.Dialog.call(this);

    this.text = text;
    this.inputLabelText = inputLabelText;
    this.placeholderText = placeholderText;
    this.positiveButtonText = positiveButtonText || 'OK';
    this.negativeButtonText = negativeButtonText || 'Cancel';

    this.positiveCallback = null;
    this.negativeCallback = null;

    this.buildDialog = function() {
      var $dialog = $(
        '<div class="modal-dialog">' +
          '<div class="dialog-inner">' +
            '<a href="#" class="close"><i class="fa fa-times"></i></a>' +
            '<div class="dialog-content">' +
              '<p><b>' + this.text + '</b></p>' +
              '<label>' + this.inputLabelText + '</label> <input type="text" placeholder="' + this.placeholderText + '"/>' +
            '</div>' +
            '<div class="dialog-footer">' +
              '<a href="#" class="btn btn-lite positive">' + this.positiveButtonText + '</a> ' +
              '<a href="#" class="btn btn-lite negative">' + this.negativeButtonText + '</a>' +
            '</div>' +
          '</div>' +
        '</div>'
      );

      $('.btn.positive', $dialog).on('click', function() {
        if (this.positiveCallback) {
          var $input = $('input', $dialog);
          this.positiveCallback($input.val());
        } else {
          this.close();
        }

        return false;
      }.bind(this));

      $('.btn.negative', $dialog).on('click', function() {
        if (this.negativeCallback) {
          this.negativeCallback();
        }

        this.close();
        return false;
      }.bind(this));

      return $dialog;
    };
  };

  StandardWeb.InputDialog.prototype = Object.create(StandardWeb.Dialog.prototype);

})(window, document, $);
