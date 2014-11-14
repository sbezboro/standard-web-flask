#!/bin/sh
cd standardweb
uglifyjs static/js/thirdparty/*.js\
    static/js/local/*.js\
    --source-map static/js/all.min.map\
    --source-map-url all.min.map\
    --output static/js/all.min.js\
    --mangle\
    -p 2

