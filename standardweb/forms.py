from standardweb.lib import csrf

from flask import request

from flask_wtf import Form
from wtforms import HiddenField, PasswordField, SelectField, TextField, TextAreaField
from wtforms.validators import DataRequired, Length
from wtforms.widgets import HTMLString, html_params, Select

from urlparse import urljoin
from urlparse import urlparse


def _is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))

    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


def _get_redirect_target():
    for target in request.args.get('next'), request.referrer:
        if not target:
            continue

        if _is_safe_url(target):
            return target

    return ''


# from https://github.com/industrydive/wtforms_extended_selectfield/blob/master/wtforms_extended_selectfield.py
class ExtendedSelectWidget(Select):
    """
    Add support of choices with ``optgroup`` to the ``Select`` widget.
    """
    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        if self.multiple:
            kwargs['multiple'] = True
        html = ['<select %s>' % html_params(name=field.name, **kwargs)]
        for item1, item2 in field.choices:
            if isinstance(item2, (list,tuple)):
                group_label = item1
                group_items = item2
                html.append('<optgroup %s>' % html_params(label=group_label))
                for inner_val, inner_label in group_items:
                    html.append(self.render_option(inner_val, inner_label, inner_val == field.data))
                html.append('</optgroup>')
            else:
                val = item1
                label = item2
                html.append(self.render_option(val, label, val == field.data))
        html.append('</select>')
        return HTMLString(''.join(html))


class ExtendedSelectField(SelectField):
    """
    Add support of ``optgroup`` grouping to default WTForms' ``SelectField`` class.

    Here is an example of how the data is laid out.

        (
            ('Fruits', (
                ('apple', 'Apple'),
                ('peach', 'Peach'),
                ('pear', 'Pear')
            )),
            ('Vegetables', (
                ('cucumber', 'Cucumber'),
                ('potato', 'Potato'),
                ('tomato', 'Tomato'),
            )),
            ('other','None Of The Above')
        )

    It's a little strange that the tuples are (value, label) except for groups which are (Group Label, list of tuples)
    but this is actually how Django does it too https://docs.djangoproject.com/en/dev/ref/models/fields/#choices

    """
    widget = ExtendedSelectWidget()

    def pre_validate(self, form):
        """
        Don't forget to validate also values from embedded lists.
        """
        for item1,item2 in self.choices:
            if isinstance(item2, (list, tuple)):
                group_label = item1
                group_items = item2
                for val,label in group_items:
                    if val == self.data:
                        return
            else:
                val = item1
                label = item2
                if val == self.data:
                    return
        raise ValueError(self.gettext('Not a valid choice!'))


class BaseForm(Form):
    csrf_token = HiddenField()

    def __init__(self, *args, **kwargs):
        super(BaseForm, self).__init__(*args, **kwargs)

        if not self.csrf_token.data:
            self.csrf_token.data = csrf.get_token()


# inspired by http://flask.pocoo.org/snippets/63/
class RedirectForm(BaseForm):
    next = HiddenField()

    def __init__(self, *args, **kwargs):
        super(RedirectForm, self).__init__(*args, **kwargs)

        if not self.next.data:
            self.next.data = _get_redirect_target()


class LoginForm(RedirectForm):
    username = TextField('Minecraft Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class NewTopicForm(BaseForm):
    title = TextField('Title', validators=[DataRequired()])
    body = TextAreaField('Body', validators=[DataRequired()])


class PostForm(BaseForm):
    body = TextAreaField('Body', validators=[DataRequired()])


class MoveTopicForm(BaseForm):
    destination = ExtendedSelectField('Destination', validators=[DataRequired()])


class ForumSearchForm(BaseForm):
    query = TextField('Post contains', validators=[DataRequired(), Length(min=3)])
    forum_id = ExtendedSelectField('Forum')
    sort_by = SelectField('Sort by', validators=[DataRequired()])
