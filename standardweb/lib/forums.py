import bbcode

_bbcode_parser = bbcode.Parser(replace_links=False)

_bbcode_parser.add_simple_formatter('img', '<img src="%(value)s"/>')


def convert_bbcode(text):
    return _bbcode_parser.format(text)
