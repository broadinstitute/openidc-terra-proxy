FROM broadinstitute/openidc-baseimage:3.0
ENV MOD_SECURITY_VERSION=2.9.2 \
    LIBOAUTH2_VERSION=1.4.4.1 \
    OAUTH2_VERSION=3.2.2

RUN apt-get update && apt-get upgrade -yq && \
    apt-get install -qy libyajl-dev python libpcre3 libpcre3-dev  git  apache2-dev wget libxml2-dev lua5.1 lua5.1-dev && \
    cd /root && \
    wget https://github.com/SpiderLabs/ModSecurity/releases/download/v${MOD_SECURITY_VERSION}/modsecurity-${MOD_SECURITY_VERSION}.tar.gz && \
    tar -xvzf modsecurity-${MOD_SECURITY_VERSION}.tar.gz && \
    cd modsecurity-${MOD_SECURITY_VERSION} && \
    ./configure --with-apxs=/usr/bin/apxs && \
    make && \
    make install && \
    mkdir -p /var/cache/modsecurity && \
    chmod -R 777 /var/cache/modsecurity && \
    mkdir -p /etc/modsecurity && \
    apt-get -yq autoremove && \
    apt-get -yq clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/* && \
    rm -rf /var/tmp/*

COPY security2.load /etc/apache2/mods-available/security2.load
COPY security2.conf /etc/apache2/mods-available/security2.conf

RUN cd /root && \
    wget https://github.com/SpiderLabs/owasp-modsecurity-crs/archive/v3.0.2.tar.gz && \
    tar -xvzf v3.0.2.tar.gz && \
    cd owasp-modsecurity-crs-3.0.2 && \
    mkdir rulesworking && \
    mkdir rulesfinal && \
    cp -rfp rules/REQUEST-921-PROTOCOL-ATTACK.conf \
      rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf \
      rules/REQUEST-931-APPLICATION-ATTACK-RFI.conf \
      rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf \
      rules/REQUEST-941-APPLICATION-ATTACK-XSS.conf \
      rules/REQUEST-942-APPLICATION-ATTACK-SQLI.conf \
      rules/RESPONSE-951-DATA-LEAKAGES-SQL.conf rulesworking/ && \
      util/join-multiline-rules/join.py rulesworking/*.conf > rulesfinal/rules.conf && \
      cp -rfp rulesfinal/* /etc/modsecurity && \
      cp -rfp rules/*.data /etc/modsecurity/

COPY modsecurity.conf /etc/modsecurity/modsecurity.conf
COPY unicode.mapping /etc/modsecurity/unicode.mapping

COPY site.conf stackdriver.conf /etc/apache2/sites-available/
COPY override.sh /etc/apache2/
COPY mpm_event.conf /etc/apache2/conf-available/
RUN a2dismod mpm_prefork && \
    a2enmod mpm_event && \
    a2enmod proxy_fcgi && \
    a2enconf mpm_event

RUN rm -f /root/modsecurity-${MOD_SECURITY_VERSION}.tar.gz
RUN rm -rf /root/modsecurity-${MOD_SECURITY_VERSION}

RUN cd /root && wget https://us.static.tcell.insight.rapid7.com/downloads/apacheagent/apache24_tcellagent-3.1.0-linux-x86_64.tgz && \ 
    tar -xzf apache24_tcellagent-3.1.0-linux-x86_64.tgz && \
    mkdir /etc/apache2/modules && \
    cp -rfp apache_tcellagent-3.1.0-linux-x86_64/ubuntu/mod_agenttcell.so /etc/apache2/modules/mod_agenttcell.so && \
    chown -R www-data:www-data /var/log/apache2 && chmod -R 777 /var/log/apache2

COPY tcell.load /etc/apache2/mods-available/tcell.load
RUN a2enmod authnz_ldap

COPY install-oauth2.sh /tmp/install-oauth2.sh
RUN chmod +x /tmp/install-oauth2.sh && \
    apt-get update -y && \
    apt-get install -y libhiredis0.13 && \
    /tmp/install-oauth2.sh
COPY oauth2.load /etc/apache2/mods-available/oauth2.load
COPY oauth2.conf /etc/apache2/mods-available/oauth2.conf
RUN a2enmod oauth2

RUN apt-get update && apt-get upgrade -yq && \
    apt-get -qy install php-fpm libapache2-mod-fcgid php-curl && \
    a2enconf php7.2-fpm

COPY www.conf /etc/php/7.2/fpm/pool.d/www.conf
COPY run-php-fpm.sh /tmp/run-php-fpm.sh
RUN chmod +x /tmp/run-php-fpm.sh && \
    mkdir -p /etc/service/php-fpm && \
    mv /tmp/run-php-fpm.sh /etc/service/php-fpm/run

COPY introspect.php /app/introspect/index.php