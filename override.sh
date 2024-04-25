#!/bin/sh

# I'm an override file.  Put things in here to override the openidc-baseimage
# defaults or add more settings of your own.
#
# Note: This script will be executed *after* the main `run.sh` script, but
# *before* Apache itself is run.

# set ALLOW_HEADERS3
if [ -z "$ALLOW_HEADERS3" ] ; then
    export ALLOW_HEADERS3=
fi

# update ALLOW_METHODS3
if [ -z "$ALLOW_METHODS3" ] ; then
    export ALLOW_METHODS3=
fi

# update AUTH_REQUIRE3
if [ -z "$AUTH_REQUIRE3" ] ; then
    export AUTH_REQUIRE3='Require valid-user'
elif [ "$AUTH_REQUIRE3" = '(none)' ]; then
    export AUTH_REQUIRE3=
fi

# update AUTH_TYPE2
if [ -z "$AUTH_TYPE2" ] ; then
    export AUTH_TYPE2='AuthType oauth2'
elif [ "$AUTH_TYPE2" = 'AuthType oauth20' ] ; then
    export AUTH_TYPE2='AuthType oauth2'
fi

# update AUTH_TYPE3
if [ -z "$AUTH_TYPE3" ] ; then
    export AUTH_TYPE3='AuthType oauth2'
elif [ "$AUTH_TYPE3" = 'AuthType oauth20' ] ; then
    export AUTH_TYPE3='AuthType oauth2'
fi

# update PROXY_PATH3
if [ -z "$PROXY_PATH3" ] ; then
    export PROXY_PATH3=/register
fi

# update PROXY_URL3
if [ -z "$PROXY_URL3" ] ; then
    export PROXY_URL3=http://app:8080/register
fi

if [ -z "$APACHE_HTTPD_TIMEOUT" ] ; then
    export APACHE_HTTPD_TIMEOUT='650'
fi

if [ -z "$APACHE_HTTPD_KEEPALIVE" ] ; then
    export APACHE_HTTPD_KEEPALIVE='On'
fi

if [ -z "$APACHE_HTTPD_KEEPALIVETIMEOUT" ] ; then
    export APACHE_HTTPD_KEEPALIVETIMEOUT='650'
fi
if [ -z "$APACHE_HTTPD_MAXKEEPALIVEREQUESTS" ] ; then
    export APACHE_HTTPD_MAXKEEPALIVEREQUESTS='500'
fi
if [ -z "$APACHE_HTTPD_PROXYTIMEOUT" ] ; then
    export APACHE_HTTPD_PROXYTIMEOUT='650'
fi
if [ -z "$PROXY_TIMEOUT" ] ; then
    export PROXY_TIMEOUT='650'
fi

if [ "$ENABLE_MODSECURITY" = "yes" ]; then
    /usr/sbin/a2enmod security2
    /usr/sbin/a2enmod unique_id
fi

# update FILTER
if [ -z "$FILTER" ] ; then
    export FILTER=
fi

# update FILTER2
if [ -z "$FILTER2" ] ; then
    export FILTER2=
fi

# update FILTER3
if [ -z "$FILTER3" ] ; then
    export FILTER3=
fi

# update INTROSPECT_PATH
if [ -z "$INTROSPECT_PATH" ] ; then
    export INTROSPECT_PATH='/introspect/'
fi

# update ENVIRONMENT
if [ -z "$ENVIRONMENT" ] ; then
    export ENVIRONMENT='dev'
fi

# update ALLOW_EXPRESSION
if [ -z "$ALLOW_EXPRESSION" ] ; then
    export ALLOW_EXPRESSION='true'
fi

# default graceful shutdown timeout
if [ -z "$GRACEFUL_SHUTDOWN_TIMEOUT"]; then
    export GRACEFUL_SHUTDOWN_TIMEOUT=25
fi

