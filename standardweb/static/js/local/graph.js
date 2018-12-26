(function(window, document, $) {
  $(document).ready(function() {
    var previousPoint = null;
    var $graphTooltip = $('<div class="graph-tooltip"></div>').appendTo("body").css({
      position: 'absolute',
      border: '1px solid #666',
      padding: '2px',
      'background-color': '#111',
      'color': '#fff'
    }).hide();

    $('.player-graph').each(function() {
      var $graph = $(this);

      var offset = new Date().getTimezoneOffset() * 1000 * 60;
      var serverId = 8;
      var maxPlayers = 100;

      var data = {};

      $graph.bind("plothover", function (event, pos, item) {
        if (item) {
          if (previousPoint != item.dataIndex) {
            previousPoint = item.dataIndex;

            var count = item.datapoint[1];

            $graphTooltip.show();
            $graphTooltip.text(count + (count == 1 ? ' player' : ' players'));
            $graphTooltip.css({
              top: item.pageY - 12,
              left: item.pageX + 14
            });
          }
        } else {
          $graphTooltip.hide();
          previousPoint = null;
        }
      });

      if ($graph.attr("weekindex")) {
        data['weekIndex'] = $graph.attr("weekindex");
      }

      $.ajax({
        url: "/" + serverId + "/player_graph",
        data: data,
        success: function(data) {
          $graph.removeClass('spinner-progress-bar');

          var points = data.points;
          var startTime = data.start_time - offset;
          var endTime = data.end_time - offset;

          var countGraph = [];
          var newGraph = [];

          points.map(function(point) {
            var time = point.time - offset;
            var playerCount = point.player_count;
            var newPlayers = point.new_players;

            countGraph.push([time, playerCount]);
            if (newPlayers >= 0) {
              newGraph.push([time, newPlayers]);
            }
          });

          data = [{data: countGraph}];

          if (newGraph.length) {
            data.push({data: newGraph, yaxis: 2});
          }

          // Make sure the graph shows the start and end time boundaries
          data.push({data: [[startTime], [endTime]]});

          $.plot($graph, data, {
            grid: {hoverable: true, backgroundColor: "#ffffff"},
            colors: ["#7E9BFF", "#F00"],
            series: {lines: { fill: true }},
            xaxes: [{mode: "time", minTickSize: [1, "day"], timeformat: "%b %d"}],
            yaxes: [{min: 0, max: maxPlayers, tickSize: 20, position: "right"}, {min: 0, max: 40}]
          });
        },
        error: function(data) {
        }
      });
    });
  });
})(window, document, $);
