#!/usr/local/bin/php
<?php
require_once('config.inc');
require_once('interfaces.inc');
require_once('util.inc');
require_once('plugins.inc');

try {
    $model = new \OPNsense\IPv6HA\IPv6HA();
    if (count($model->performValidation(true))) {
        throw new RuntimeException('Invalid HA settings.');
    }
    $result = [];
    foreach ($model->general->getFlatNodes() as $node) {
        $result[$node->getInternalXMLTagName()] = (string)$node;
    }
    foreach (['enabled', 'maintenance'] as $key) {
        $result[$key] = $result[$key] === '1';
    }
    if (!$result['enabled']) {
        echo json_encode($result, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . "\n";
        exit(0);
    }
    $lan = $result['lan_interface'];
    $wan = $config['interfaces'][$lan]['track6-interface'] ?? '';
    $result['wan_interface'] = $wan;
    $result['lan'] = get_real_interface($lan, 'inet6');
    $result['wan'] = get_real_interface($wan, 'inet6');
    $raModel = new \OPNsense\Radvd\Radvd();
    $entry = null;
    foreach ($raModel->entries->iterateItems() as $candidate) {
        if ((string)$candidate->interface === $lan) {
            $entry = $candidate;
            break;
        }
    }
    if ($entry === null) {
        throw new RuntimeException('Add Router Advertisement settings for the selected LAN first.');
    }
    if (count($raModel->performValidation(true))) {
        throw new RuntimeException('Router Advertisement settings are invalid.');
    }
    if (!$entry->Base6Interface->isEmpty()) {
        throw new RuntimeException('Base6Interface is not supported by dynamic-PD HA; use the tracked LAN prefix.');
    }
    $result['vip'] = (string)$entry->AdvRASrcAddress;
    $matches = [];
    foreach ((new \OPNsense\Interfaces\Vip())->vip->iterateItems() as $vip) {
        if ($vip->mode->isEqual('carp') && (string)$vip->interface === $lan &&
            @inet_pton((string)$vip->subnet) !== false &&
            @inet_pton((string)$vip->subnet) === @inet_pton($result['vip'])) {
            $matches[] = $vip;
        }
    }
    if (count($matches) !== 1) {
        throw new RuntimeException('Select an existing link-local CARP address as the Router Advertisement source.');
    }
    $result['vhid'] = (int)(string)$matches[0]->vhid;
    $result['normal_skew'] = (int)(string)$matches[0]->advskew;
    foreach ((new \OPNsense\Interfaces\Vip())->vip->iterateItems() as $vip) {
        if ($vip->mode->isEqual('carp') && (string)$vip->interface === $lan &&
            (int)(string)$vip->vhid === $result['vhid'] &&
            filter_var((string)$vip->subnet, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
            throw new RuntimeException('The Router Advertisement source shares its VHID with IPv4; use a dedicated IPv6 VHID.');
        }
    }
    // Resolve native defaults without storing another editable copy in the HA model.
    $value = function ($field, $default) use ($entry) {
        return (string)$entry->$field !== '' ? (int)(string)$entry->$field : $default;
    };
    $result['min_interval'] = $value('MinRtrAdvInterval', 200);
    $result['max_interval'] = $value('MaxRtrAdvInterval', 600);
    $result['router_lifetime'] = $value('AdvDefaultLifetime', 3 * $result['max_interval']);
    $result['preferred_lifetime'] = $value('AdvPreferredLifetime', 14400);
    $result['valid_lifetime'] = $value('AdvValidLifetime', 86400);
    $mtus = [];
    $availableInterfaces = function_exists('net_get_interfaces') ? net_get_interfaces() : [];
    foreach ([$result['lan'], $result['wan']] as $device) {
        if (isset($availableInterfaces[$device])) {
            $stats = legacy_interface_stats($device);
            if (!empty($stats['mtu'])) {
                $mtus[] = (int)$stats['mtu'];
            }
        }
    }
    if ((string)$entry->AdvLinkMTU !== '') {
        $mtus[] = (int)(string)$entry->AdvLinkMTU;
    }
    if (!$mtus) {
        throw new RuntimeException('Cannot determine the effective interface MTU.');
    }
    $result['mtu'] = min($mtus);
    if ((string)$entry->RemoveAdvOnExit === 'on' || (string)$entry->DeprecatePrefix === 'on') {
        throw new RuntimeException('Shared CARP HA requires RemoveAdvOnExit and DeprecatePrefix to be Automatic or Off.');
    }
    $ra = [
        'mode' => (string)$entry->mode, 'hop_limit' => (int)(string)$entry->AdvCurHopLimit,
        'preference' => (string)$entry->AdvDefaultPreference,
        'routes' => array_values($entry->routes->getValues()),
        'route_lifetime' => $value('AdvRouteLifetime', 3 * $result['max_interval']),
        'remove_route' => (string)$entry->RemoveRoute === 'on',
        'nat64prefix' => (string)$entry->nat64prefix,
        'rdnss' => [], 'dnssl' => [],
        'rdnss_lifetime' => $value('AdvRDNSSLifetime', 3 * $result['max_interval']),
        'dnssl_lifetime' => $value('AdvDNSSLLifetime', 3 * $result['max_interval']),
    ];
    if ($entry->dns->isEqual('1')) {
        $rdnss = $entry->RDNSS->getValues();
        if (!$rdnss && !empty(service_by_filter(['dns_ports' => '53']))) {
            $rdnss = [$result['vip']];
        } elseif (!$rdnss) {
            $rdnss = $config['system']['dnsserver'] ?? [];
        }
        foreach ($rdnss as $server) {
            if (filter_var($server, FILTER_VALIDATE_IP, FILTER_FLAG_IPV6) && count($ra['rdnss']) < 3) {
                $ra['rdnss'][] = $server;
            }
        }
        $ra['dnssl'] = array_values($entry->DNSSL->getValues());
        if (!$ra['dnssl'] && !empty($config['system']['domain'])) {
            $ra['dnssl'] = [$config['system']['domain']];
        }
    }
    $result['ra'] = $ra;
    if ($result['enabled']) {
        if (($config['interfaces'][$wan]['ipaddrv6'] ?? '') !== 'dhcp6' ||
            !in_array($config['interfaces'][$lan]['ipaddrv6'] ?? '', ['idassoc6', 'track6'], true)) {
            throw new RuntimeException('LAN must track a DHCPv6-PD WAN.');
        }
        if ($entry->enabled->isEqual('1')) {
            throw new RuntimeException('Turn off the selected interface on the system Router Advertisements page; IPv6 HA manages it automatically.');
        }
        if (in_array('radvd', explode(',', $config['hasync']['syncitems'] ?? ''), true)) {
            throw new RuntimeException('Remove Router Advertisements from HA synchronization.');
        }
    }
    echo json_encode($result, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . "\n";
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(1);
}
