function loadPlayerGraph($elem, serverId, maxPlayers) {
    var offset = new Date().getTimezoneOffset() * 1000 * 60;
    serverId = serverId || 4;
    maxPlayers = maxPlayers || 120;
    
    var data = {};
    
    if ($elem.attr("weekindex")) {
        data['weekIndex'] = $elem.attr("weekindex");
    }
    
    try {
        //data.test = test; 
    } catch(e) {
        _rollbar.push(e);
    }
    
    $.ajax({
        url: "/" + serverId + "/player_graph",
        data: data,
        success: function(data) {
            $elem.removeClass('progress');
            
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
            data.push({data: [[startTime], [endTime]]})
            
            $.plot($elem, data, {
                grid: {hoverable: true, backgroundColor: "#ffffff"},
                colors: ["#7E9BFF", "#F00"],
                series: {lines: { fill: true }},
                xaxes: [{mode: "time", minTickSize: [1, "day"], timeformat: "%b %d"}],
                yaxes: [{min: 0, max: maxPlayers, tickSize: 20, position: "right"}, {min: 0, max: 40}] });
        },
        error: function(data) {
        }
    });
}

function showGraphTooltip(x, y, contents) {
    $('<div id="graph-tooltip">' + contents + '</div>').css( {
        position: 'absolute',
        display: 'none',
        top: y - 12,
        left: x + 14,
        border: '1px solid #666',
        padding: '2px',
        'background-color': '#111',
        'color': '#fff'
    }).appendTo("body").show();
}

$(document).ready(function() {
    var previousPoint = null;
    $(".graph").bind("plothover", function (event, pos, item) {
        if (item) {
            if (previousPoint != item.dataIndex) {
                previousPoint = item.dataIndex;
                
                $("#graph-tooltip").remove();
                var time = item.datapoint[0];
                var count = item.datapoint[1];
                
                showGraphTooltip(item.pageX, item.pageY, count + (count == 1 ? ' player' : ' players'));
            }
        } else {
            $("#graph-tooltip").remove();
            previousPoint = null;
        }
    });
});
