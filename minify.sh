#!/bin/sh
cd standardweb
uglifyjs static/js/jquery-1.8.3.js\
    static/js/jquery.flot.js\
    static/js/jquery.placeholder.js\
    static/js/jquery.timeago.js\
    static/js/jquery.tipsy.js\
    static/js/jquery.sceditor.min.js\
    static/js/jquery.sceditor.bbcode.min.js\
    static/js/soundmanager2.js\
    static/js/ZeroClipboard.js\
    static/js/graph.js\
    static/js/streams.js\
    static/js/socket.io.js\
    static/js/util.js\
    --source-map static/js/all.min.map\
    --source-map-url all.min.map\
    --output static/js/all.min.js\
    --mangle
