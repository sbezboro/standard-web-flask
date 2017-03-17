from standardweb.lib import csrf

from flask import request

from flask_wtf import Form
from wtforms import BooleanField, HiddenField, FileField, PasswordField, SelectField, TextField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from wtforms.widgets import HTMLString, html_params, Select

from urlparse import urljoin
from urlparse import urlparse


VALID_IMAGE_UPLOAD_EXTENSIONS = frozenset(['jpg', 'jpeg', 'gif', 'png'])
MAX_UPLOAD_FILE_SIZE = 1024 * 1024 * 5  # 5MB


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


class ImageUploadForm(BaseForm):
    image = FileField('Image (optional)')

    def validate_image(self, field):
        if field.data and not isinstance(field.data, basestring):
            extension = field.data.filename.rsplit('.', 1)[1]
            content = field.data.stream.read()
            length = len(content)

            if extension.lower() not in VALID_IMAGE_UPLOAD_EXTENSIONS:
                raise ValidationError('Must be an image file')

            if length > MAX_UPLOAD_FILE_SIZE:
                raise ValidationError('File must be smaller than %dMB' % (MAX_UPLOAD_FILE_SIZE / 1024 / 1024))

            field.data.content = content


# inspired by http://flask.pocoo.org/snippets/63/
class RedirectForm(BaseForm):
    next = HiddenField()

    def __init__(self, *args, **kwargs):
        super(RedirectForm, self).__init__(*args, **kwargs)

        if not self.next.data:
            self.next.data = RedirectForm._get_redirect_target()

    @classmethod
    def _is_safe_url(cls, target):
        ref_url = urlparse(request.host_url)
        test_url = urlparse(urljoin(request.host_url, target))

        return test_url.scheme in ('http', 'https') and \
            ref_url.netloc == test_url.netloc

    @classmethod
    def _get_redirect_target(cls):
        target = request.args.get('next')

        if target and cls._is_safe_url(target):
            return target

        return ''


class LoginForm(RedirectForm):
    username = TextField('Minecraft Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class AddMFAForm(BaseForm):
    token = TextField('Verification code', validators=[DataRequired(), Length(
        min=6, max=6, message='Value must be 6 numbers long'
    )])


class VerifyMFAForm(RedirectForm):
    token = TextField('Verification code', validators=[DataRequired(), Length(
        min=6, max=6, message='Value must be 6 numbers long'
    )])


class RemoveMFAForm(BaseForm):
    pass

class VerifyEmailForm(BaseForm):
    password = PasswordField('Choose a password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm password', validators=[DataRequired()])


class ForgotPasswordForm(BaseForm):
    email = TextField('Email', validators=[DataRequired()])


class ResetPasswordForm(BaseForm):
    password = PasswordField('New password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm password', validators=[DataRequired()])


class NewTopicForm(ImageUploadForm):
    title = TextField('Title', validators=[DataRequired()])
    body = TextAreaField('Body', validators=[DataRequired()])
    email_all = BooleanField('Email all users', validators=[Optional()])
    subscribe = BooleanField('Get emailed about replies in this topic', validators=[Optional()])


class PostForm(ImageUploadForm):
    body = TextAreaField('Body', validators=[DataRequired()])
    subscribe = BooleanField('Get emailed about replies in this topic', validators=[Optional()])


class MoveTopicForm(BaseForm):
    destination = ExtendedSelectField('Destination', validators=[DataRequired()])


class ForumSearchForm(BaseForm):
    query = TextField('Topic title or post contents', validators=[Optional(), Length(min=3)])
    user_id = TextField('User', validators=[Optional()])
    forum_id = ExtendedSelectField('Forum', validators=[Optional()], default='')
    sort_by = SelectField('Sort by', validators=[Optional()], default='')


class ProfileSettingsForm(BaseForm):
    full_name = TextField('Name', validators=[Optional()])
    email = TextField('Email', validators=[DataRequired()])


def generate_notification_settings_form(preferences):
    class F(BaseForm):
        pass

    for preference in preferences:
        setattr(F, '%s_email' % preference.name, BooleanField())
        setattr(F, '%s_ingame' % preference.name, BooleanField())

    return F()


class ChangePasswordForm(BaseForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_new_password = PasswordField('Confirm New Password', validators=[DataRequired()])
