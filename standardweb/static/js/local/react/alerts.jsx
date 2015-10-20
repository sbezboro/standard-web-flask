(function(window, document, $) {

  StandardWeb.reactComponents.AlertManager = React.createClass({
    getInitialState: function() {
      return {
        alerts: []
      };
    },

    addAlert: function(category, message) {
      var alerts = this.state.alerts.slice();
      alerts.push([category, message]);

      this.setState({
        alerts: alerts
      });
    },

    handleAlertClose: function(index) {
      var alerts = this.state.alerts.slice();
      alerts.splice(index, 1);

      this.setState({
        alerts: alerts
      });
    },

    renderAlert: function(alert, i) {
      return (
        <Alert message={alert[1]}
          level={alert[0]}
          index={i}
          onClose={this.handleAlertClose}
        />
      );
    },

    render: function() {
      var alerts = this.state.alerts.map(this.renderAlert);
      return <div>{alerts}</div>;
    }
  });

  var Alert = React.createClass({

    handleClose: function() {
      this.props.onClose(this.props.index);
    },

    render: function() {
      return (
        <div className={'alert ' + this.props.level}>
          <span dangerouslySetInnerHTML={{ __html: this.props.message }}></span>
          <a className="close" onClick={this.handleClose}>&times;</a>
        </div>
      );
    },
  });
})(window, document, $);
