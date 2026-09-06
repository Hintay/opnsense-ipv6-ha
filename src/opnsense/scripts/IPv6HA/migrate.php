#!/usr/local/bin/php
<?php
require_once('config.inc');
require_once('interfaces.inc');
require_once('util.inc');

$instance = \OPNsense\Core\Config::getInstance();
$xml = $instance->object();
$general = $xml->OPNsense->IPv6HA->general ?? null;
$hasOldFields = $general !== null && isset($general->mtu);
$hasProbeFields = $general !== null && (isset($general->targets) || isset($general->probe_interval) ||
    isset($general->failure_count) || isset($general->success_count) || isset($general->recovery_hold));
$existing = [
    'enabled' => $general !== null && isset($general->enabled) ? (string)$general->enabled : null,
    'maintenance' => $general !== null && isset($general->maintenance) ? (string)$general->maintenance : null,
    'lan_interface' => $general !== null && isset($general->lan_interface) ? (string)$general->lan_interface : null,
];
if ($general !== null && !$hasOldFields && !$hasProbeFields) {
    exit(0);
}
$path = '/usr/local/etc/ipv6-ha.json';
$legacy = is_file($path) ? json_decode(file_get_contents($path), true, 512, JSON_THROW_ON_ERROR) : null;
$model = new \OPNsense\IPv6HA\IPv6HA();
if ($legacy !== null && ($hasOldFields || $general === null)) {
    // Preserve the applied wire settings, not the dormant old radvd defaults.
    $lan = $legacy['lan_interface'] ?? null;
    if ($lan === null) {
        foreach (array_keys($config['interfaces']) as $interface) {
            if (get_real_interface($interface, 'inet6') === $legacy['lan']) {
                $lan = $interface;
                break;
            }
        }
    }
    if ($lan === null) {
        throw new RuntimeException('Cannot map the legacy LAN.');
    }
    // Keep settings already saved through the MVC page; the runtime file may be older.
    $model->general->lan_interface = $existing['lan_interface'] ?? $lan;
    $model->general->enabled = $existing['enabled'] ?? (!isset($legacy['enabled']) || $legacy['enabled'] ? '1' : '0');
    $model->general->maintenance = $existing['maintenance'] ??
        (!empty($legacy['maintenance']) || is_file('/var/run/ipv6-ha-maintenance') ? '1' : '0');
    $raModel = new \OPNsense\Radvd\Radvd();
    $entry = null;
    foreach ($raModel->entries->iterateItems() as $candidate) {
        if ((string)$candidate->interface === $lan) {
            $entry = $candidate;
            break;
        }
    }
    if ($entry === null || $entry->enabled->isEqual('1')) {
        throw new RuntimeException('Migration needs Router Advertisement settings for the disabled LAN interface.');
    }
    foreach (['mtu' => ['AdvLinkMTU', 1492], 'min_interval' => ['MinRtrAdvInterval', 3],
        'max_interval' => ['MaxRtrAdvInterval', 10], 'router_lifetime' => ['AdvDefaultLifetime', 30],
        'preferred_lifetime' => ['AdvPreferredLifetime', 60], 'valid_lifetime' => ['AdvValidLifetime', 300]] as $key => [$field, $default]) {
        $entry->$field = (string)($legacy[$key] ?? $default);
    }
    $entry->AdvRASrcAddress = $legacy['vip'];
    $entry->mode = 'unmanaged';
    $entry->dns = '0';
    $entry->RemoveAdvOnExit = 'off';
    $entry->DeprecatePrefix = 'off';
    $entry->routes = '';
    $entry->nat64prefix = '';
    $entry->AdvCurHopLimit = '64';
    $entry->AdvDefaultPreference = 'medium';
    if (count($raModel->performValidation(true))) {
        throw new RuntimeException('Migrated Router Advertisement settings are invalid.');
    }
    $raModel->serializeToConfig();
}
if (count($model->performValidation(true))) {
    throw new RuntimeException('Migrated HA configuration is invalid.');
}
$model->serializeToConfig();
// Remove obsolete fields even when restoring a configuration made with 1.0.
foreach (['wan_interface', 'vip', 'vhid', 'normal_skew', 'mtu', 'min_interval', 'max_interval',
    'router_lifetime', 'preferred_lifetime', 'valid_lifetime', 'failed_skew', 'targets', 'probe_interval',
    'failure_count', 'success_count', 'recovery_hold'] as $field) {
    unset($instance->object()->OPNsense->IPv6HA->general->$field);
}
$instance->save(false, 'Update IPv6 HA settings');
