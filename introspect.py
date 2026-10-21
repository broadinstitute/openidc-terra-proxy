# Implementation of RFC 7662 introspection endpoint
#
# mod_oauth2 verifies tokens against this endpoint (see oauth2.conf). Google access
# tokens are opaque and Google has no RFC 7662 endpoint, so we translate Google's
# tokeninfo response into an RFC 7662 response.
#
# Served by mod_wsgi (see site.conf). Standard library only.

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKENINFO_URL = 'https://www.googleapis.com/oauth2/v3/tokeninfo'

# Must stay below liboauth2's own 15s timeout for the introspection call.
TOKENINFO_TIMEOUT_S = 10

INACTIVE = {'active': False}


def tokeninfo(access_token):
    """Return Google's tokeninfo for the token, or None if it is not valid."""
    body = urllib.parse.urlencode({
        'access_token': access_token,
        'token_type_hint': 'access_token',
    }).encode()
    request = urllib.request.Request(
        TOKENINFO_URL,
        data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=TOKENINFO_TIMEOUT_S) as response:
            return json.load(response)
    except urllib.error.HTTPError:
        # Google answers invalid or expired tokens with a 4xx; that's routine.
        return None
    except (OSError, ValueError) as e:
        # Network failure, timeout, or a malformed body. Never log the token.
        print('introspect: tokeninfo request failed: %r' % e, file=sys.stderr)
        return None


def introspect(access_token):
    if not access_token:
        return INACTIVE
    info = tokeninfo(access_token)
    if info is None:
        return INACTIVE
    return {
        'active': True,
        'scope': info.get('scope'),
        'sub': info.get('sub'),
        'username': info.get('email'),
        'email': info.get('email'),
        'exp': info.get('exp'),
        'token_type': 'bearer',
        'aud': info.get('aud'),
    }


def application(environ, start_response):
    if environ['REQUEST_METHOD'].upper() != 'POST':
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [b'only POST supported']

    try:
        length = int(environ.get('CONTENT_LENGTH') or 0)
    except ValueError:
        length = 0
    form = urllib.parse.parse_qs(environ['wsgi.input'].read(length).decode('utf-8', 'replace'))
    access_token = form.get('token', [''])[0]

    body = json.dumps(introspect(access_token)).encode()
    start_response('200 OK', [
        ('Content-Type', 'application/json; charset=utf-8'),
        ('Content-Length', str(len(body))),
    ])
    return [body]
