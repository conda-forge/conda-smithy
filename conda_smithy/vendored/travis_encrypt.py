#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 Matt Martz <matt@sivel.net>
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import six
import base64
import argparse
import requests

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

__version__ = '1.0.0'


def handle_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version',
                        version=__version__)

    parser.add_argument('-r', '--repo', required=True,
                        help='Repository slug (:owner/:name)')
    parser.add_argument('string', help='String to encrypt')

    args = parser.parse_args()
    return args


def get_public_key(repo):
    keyurl = 'https://api.travis-ci.org/repos/{0}/key'.format(repo)
    r = requests.get(keyurl,
                     headers={
                       # If the user-agent isn't defined correctly, we will recieve a 403.
                       'User-Agent': 'Travis/1.0',
                       'Accept': 'application/vnd.travis-ci.2+json',
                       'Content-Type': 'application/json'})
    r.raise_for_status()
    key = r.json()

    return key.get('key')


def encrypt(repo, string):
    public_key = get_public_key(repo)
    key = RSA.importKey(public_key)
    cipher = PKCS1_v1_5.new(key)
    return base64.b64encode(cipher.encrypt(string))


def main():
    args = handle_args()
    encrypted = encrypt(args.repo, args.string)
    six.print_('secure: "{0}"'.format(encrypted))


if __name__ == '__main__':
    main()
