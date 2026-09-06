<?php
require_once('config.inc');
$ha = new \OPNsense\IPv6HA\IPv6HA();
if (!$ha->general->enabled->isEqual('1')) {
    echo "SKIP: IPv6 HA must be configured and enabled for the export integration test\n";
    exit(0);
}
$ra = new \OPNsense\Radvd\Radvd();
foreach ($ra->entries->iterateItems() as $entry) {
    if ((string)$entry->interface === 'lan') {
        $entry->dns = '1';
        $entry->RDNSS = '';
    }
}
// Change only the in-memory configuration; never save or apply it.
$ra->serializeToConfig();
ob_start();
require('/usr/local/opnsense/scripts/IPv6HA/export.php');
$data = json_decode(ob_get_clean(), true);
if (empty($data['ra']['rdnss']) || empty($data['ra']['dnssl'])) {
    throw new RuntimeException('Native automatic DNS settings were not inherited.');
}
echo "PASS: native automatic RDNSS and DNSSL resolve in memory without changing live RA\n";
