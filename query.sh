#!/bin/bash
cd /home/deploy/standard-web-flask
. ../standard-web-flask/env/bin/activate
python -m standardweb.scripts.query
