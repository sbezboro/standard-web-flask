import bbcode

_bbcode_parser = bbcode.Parser(replace_links=False)

_bbcode_parser.add_simple_formatter('img', '<img src="%(value)s"/>')

def _render_size(tag_name, value, options, parent, context):
    size = int(options['size'])
    return '<font size="%d">%s</span>' % (size, value)

_bbcode_parser.add_formatter('size', _render_size)

def convert_bbcode(text):
    return _bbcode_parser.format(text)
