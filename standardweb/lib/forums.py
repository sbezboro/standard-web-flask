from flask import url_for

import bbcode

import cgi
import re


_bbcode_parser = bbcode.Parser(replace_links=False)

_emoticon_map = {
    ':\)': 'emoticons/smile.png',
    ':angel:': 'emoticons/angel.png',
    ':angry:': 'emoticons/angry.png',
    '8-\)': 'emoticons/cool.png',
    ":'\(": 'emoticons/cwy.png',
    ':ermm:': 'emoticons/ermm.png',
    ':D': 'emoticons/grin.png',
    '<3': 'emoticons/heart.png',
    ':\(': 'emoticons/sad.png',
    ':O': 'emoticons/shocked.png',
    ':P': 'emoticons/tongue.png',
    ';\)': 'emoticons/wink.png',
    ':alien:': 'emoticons/alien.png',
    ':blink:': 'emoticons/blink.png',
    ':blush:': 'emoticons/blush.png',
    ':cheerful:': 'emoticons/cheerful.png',
    ':devil:': 'emoticons/devil.png',
    ':dizzy:': 'emoticons/dizzy.png',
    ':getlost:': 'emoticons/getlost.png',
    ':happy:': 'emoticons/happy.png',
    ':kissing:': 'emoticons/kissing.png',
    ':ninja:': 'emoticons/ninja.png',
    ':pinch:': 'emoticons/pinch.png',
    ':pouty:': 'emoticons/pouty.png',
    ':sick:': 'emoticons/sick.png',
    ':sideways:': 'emoticons/sideways.png',
    ':silly:': 'emoticons/silly.png',
    ':sleeping:': 'emoticons/sleeping.png',
    ':unsure:': 'emoticons/unsure.png',
    ':woot:': 'emoticons/w00t.png',
    ':wassat:': 'emoticons/wassat.png'
}

emoticon_map = [
    (re.compile(cgi.escape(k)), '<img src="%s"/>' % url_for('static', filename='images/forums/' + v))
    for k, v in _emoticon_map.iteritems()
]


def convert_bbcode(text):
    return _bbcode_parser.format(text)


def _render_size(tag_name, value, options, parent, context):
    if 'size' in options:
        size = int(options.get('size', 1))
    elif len(options) == 1:
        key, val = options.items()[0]

        if val:
            size = val
        elif key:
            size = key
    else:
        size = 1

    return '<font size="%s">%s</font>' % (size, value)



def _render_quote(tag_name, value, options, parent, context):
    name = options.get('quote')
    if name:
        return '<blockquote><span class="quote-username">%s</span>%s</blockquote>' % (name, value)

    return '<blockquote>%s</blockquote>' % value


_bbcode_parser.add_simple_formatter('img', '<img src="%(value)s"/>')
_bbcode_parser.add_simple_formatter('youtube', '<iframe width="516" height="315" src="//www.youtube.com/embed/%(value)s" frameborder="0" allowfullscreen></iframe>')

_bbcode_parser.add_formatter('size', _render_size)
_bbcode_parser.add_formatter('quote', _render_quote)

