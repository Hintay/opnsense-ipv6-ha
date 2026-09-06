<?php
require_once('config.inc');

$cases = [
    ['enabled', '2'], ['maintenance', '2'], ['lan_interface', '../wan'], ['lan_interface', ''],
];
foreach ($cases as [$field, $value]) {
    $model = new \OPNsense\IPv6HA\IPv6HA();
    $model->general->$field = $value;
    if (count($model->performValidation(true)) === 0) {
        throw new RuntimeException('Invalid model accepted: ' . $field);
    }
}
$model = new \OPNsense\IPv6HA\IPv6HA();
if (count($model->performValidation(true)) !== 0) {
    throw new RuntimeException('Current configuration failed validation');
}
echo "PASS: 4 invalid model cases rejected; current node configuration accepted\n";
