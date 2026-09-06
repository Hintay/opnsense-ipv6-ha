<?php

function ipv6ha_configure()
{
    return ['bootup' => ['ipv6ha_configure_do'], 'local' => ['ipv6ha_configure_do'],
        'ipv6ha' => ['ipv6ha_configure_do'], 'radvd' => ['ipv6ha_configure_do'],
        'newwanip' => ['ipv6ha_wake']];
}

function ipv6ha_configure_do($verbose = false)
{
    mwexecf('/usr/local/opnsense/scripts/IPv6HA/control.py apply');
}

function ipv6ha_wake($verbose = false)
{
    if (is_file('/var/run/ipv6_ha.child.pid')) {
        mwexecf('/bin/pkill -USR1 -F /var/run/ipv6_ha.child.pid');
    }
}

function ipv6ha_services()
{
    $model = new \OPNsense\IPv6HA\IPv6HA();
    if (!$model->general->enabled->isEqual('1')) {
        return [];
    }
    return [['name' => 'ipv6_ha', 'description' => gettext('IPv6 HA'),
        'pidfile' => '/var/run/ipv6_ha.pid',
        'php' => ['start' => ['ipv6ha_configure_do'], 'restart' => ['ipv6ha_configure_do']]]];
}

function ipv6ha_syslog()
{
    return ['ipv6ha' => ['facility' => ['ipv6-ha']]];
}

// Deliberately omit XMLRPC synchronization: interface choices and priorities are node-local.
