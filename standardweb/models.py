from standardweb import db
from standardweb.lib import helpers as h

from pbkdf2 import pbkdf2_bin

import base64
import binascii
import hashlib
import os

class User(db.Model):
    __tablename__ = 'auth_user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30))
    email = db.Column(db.String(75))
    password = db.Column(db.String(128))
    is_superuser = db.Column(db.Boolean)

    def check_password(self, password):
        algorithm, iterations, salt, hash_val = self.password.split('$', 3)
        expected = self._make_password(password, salt=salt, iterations=int(iterations))

        return h.safe_str_cmp(self.password, expected)

    def _make_password(self, password, salt=None, iterations=None):
        if not salt:
            salt = binascii.b2a_hex(os.urandom(15))

        if not iterations:
            iterations = 10000

        hash_val = pbkdf2_bin(bytes(password), bytes(salt), iterations, keylen=32, hashfunc=hashlib.sha256)
        hash_val = hash_val.encode('base64').strip()
        return '%s$%s$%s$%s' % ('pbkdf2_sha256', iterations, salt, hash_val)
