# openidc-terra-proxy

> This repo is DSP DevOps-managed, and was built off of [openidc-proxy](https://github.com/broadinstitute/openidc-proxy)'s [tcell_3_1_0](https://github.com/broadinstitute/openidc-proxy/tree/tcell_3_1_0) branch on 10/14/2021 based on [this conversation](https://broadinstitute.slack.com/archives/CADM7MZ35/p1634137067113800).
>
> The `Bump, Tag, and Publish` action in this repo pushes images to `us.gcr.io/broad-dsp-gcr-public/openidc-terra-proxy`, see [here](https://console.cloud.google.com/gcr/images/broad-dsp-gcr-public/us/openidc-terra-proxy?project=broad-dsp-gcr-public).
>
> The README drawing on the openidc-proxy history is below:

This container images extends [OpenIDC BaseImage][1] and adds several features:

* Adds the authnz_ldap module to Apache
* Adds a new `site.conf` config file
* Adds the following configurable environment variables to use the extended functionality of the container image:
  * ALLOW_HEADERS3: The CORS headers to allow for *PROXY_PATH3*.  Default:  None
  * ALLOW_METHODS3: The CORS methods to allow for *PROXY_PATH3*.  Default:  None
  * AUTH_REQUIRE3: An OIDC claim to restrict access on *PROXY_PATH3*.  Default: __Require valid-user__
  * AUTH_TYPE2: The AuthType to use for *PROXY_PATH2*.  Default: __AuthType oauth2__
  * AUTH_TYPE3: The AuthType to use for *PROXY_PATH3*.  Default: __AuthType oauth2__
  * AUTH_LDAP_BIND_DN: The AuthLDAPBindDN to use for *PROXY_PATH*.  Default: None
  * AUTH_LDAP_BIND_DN2: The AuthLDAPBindDN to use for *PROXY_PATH2*.  Default: None
  * AUTH_LDAP_BIND_DN3: The AuthLDAPBindDN to use for *PROXY_PATH3*.  Default: None
  * AUTH_LDAP_BIND_PASSWORD: The AuthLDAPBindPassword to use for *PROXY_PATH*.  Default: None
  * AUTH_LDAP_BIND_PASSWORD2: The AuthLDAPBindPassword to use for *PROXY_PATH2*.  Default: None
  * AUTH_LDAP_BIND_PASSWORD3: The AuthLDAPBindPassword to use for *PROXY_PATH3*.  Default: None
  * AUTH_LDAP_GROUP_ATTR: The AuthLDAPGroupAttribute to use for *PROXY_PATH*.  Default: None
  * AUTH_LDAP_GROUP_ATTR2: The AuthLDAPGroupAttribute to use for *PROXY_PATH2*.  Default: None
  * AUTH_LDAP_GROUP_ATTR3: The AuthLDAPGroupAttribute to use for *PROXY_PATH3*.  Default: None
  * AUTH_LDAP_URL: The AuthLDAPURL to use for *PROXY_PATH*.  Default: None
  * AUTH_LDAP_URL2: The AuthLDAPURL to use for *PROXY_PATH2*.  Default: None
  * AUTH_LDAP_URL3: The AuthLDAPURL to use for *PROXY_PATH3*.  Default: None
  * ENABLE_STACKDRIVER: Set to *yes* to enable Stackdriver Virtual Host. Default: None
  * LDAP_CACHE_TTL: The LDAP cache timeout.  Default: __60__
  * PROXY_PATH3: The Apache `Location` to configure with OAuth2.0 authentication, which will require a valid Google token to access.  Default: __/register__
  * INTROSPECT_PATH: The path to the RFC 7662 introspection endpoint.  Note this must end with a slash. Default: __/introspect/__
  * ENVIRONMENT: The environment that the proxy is running in.  Can be one of the following values: dev, alpha, perf, staging, prod. Default: __dev__
  * ALLOW_EXPRESSION: An [Apache expression!](https://httpd.apache.org/docs/2.4/expr.html) to include for allowing requests.  Note: this check happens *after* the authentication flow so you can access environment oauth variables using epressions like `%{HTTP:OAUTH2_CLAIM_email}`.  Also, it must contain a value (which is why the default is true).  Default: __true__
  * GRACEFUL_SHUTDOWN_TIMEOUT: The time, in seconds, after a SIGWINCH (graceful stop) to send a SIGTERM (immediate stop) to children. Default __15__

[1]: https://github.com/broadinstitute/openidc-baseimage "OpenIDC BaseImage"
