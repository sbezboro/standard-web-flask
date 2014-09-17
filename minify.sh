#!/bin/sh
cd standardweb
uglifyjs static/js/jquery-1.8.3.min.js\
    static/js/jquery.flot.min.js\
    static/js/jquery.placeholder.min.js\
    static/js/jquery.timeago.min.js\
    static/js/jquery.tipsy.min.js\
    static/js/jquery.sceditor.min.js\
    static/js/jquery.sceditor.bbcode.min.js\
    static/js/soundmanager2.min.js\
    static/js/ZeroClipboard.min.js\
    static/js/site.js\
    static/js/graph.js\
    static/js/streams.js\
    static/js/socket.io.min.js\
    static/js/util.js\
    --source-map static/js/all.min.map\
    --source-map-url all.min.map\
    --output static/js/all.min.js\
    --mangle
