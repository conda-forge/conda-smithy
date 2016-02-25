# -*- coding: utf-8 -*-
import mock
import textwrap
import unittest

import six

import conda_smithy.ci_register as ci

class TestEncrypt(unittest.TestCase):

    @mock.patch('conda_smithy.vendored.travis_encrypt.get_public_key')
    def test_encryt_stringlike(self, mymock):
        # sample from http://phpseclib.sourceforge.net/rsa/examples.html
        mymock.return_value = textwrap.dedent(
            '''-----BEGIN PUBLIC KEY-----
            MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCqGKukO1De7zhZj6+H0qtjTkVxwTCpvKe4eCZ0
            FPqri0cb2JZfXJ/DgYSF6vUpwmJG8wVQZKjeGcjDOL5UlsuusFncCzWBQ7RKNUSesmQRMSGkVb1/
            3j+skZ6UtW+5u09lHNsj6tQ51s1SPrCBkedbNf0Tp0GbMJDyR4e9T04ZZwIDAQAB
            -----END PUBLIC KEY-----'''
        )
        slug = 'user/project'
        item = 'BINSTAR_TOKEN="secret"'

        result = ci._encrypt_binstar_token(slug, item)
        self.assertTrue(isinstance(result, six.string_types))

