<?php
require_once('config.inc');
require_once __DIR__ . '/../src/opnsense/mvc/app/controllers/OPNsense/IPv6HA/IndexController.php';

function fieldsById(array $form): array
{
    $result = [];
    foreach ($form['sections'] as $section) {
        foreach ($section['children'] as $field) {
            if (!empty($field['id'])) {
                $result[$field['id']] = $field;
            }
        }
    }
    return $result;
}

$native = (new \OPNsense\Radvd\SettingsController())->getForm('dialogEntry');
$method = new ReflectionMethod(\OPNsense\IPv6HA\IndexController::class, 'managedRadvdForm');
$method->setAccessible(true);
$managed = $method->invoke(null, $native);
$nativeFields = fieldsById($native);
$managedFields = fieldsById($managed);

foreach (['entries.enabled', 'entries.interface', 'entries.Base6Interface'] as $id) {
    unset($nativeFields[$id]);
    if (isset($managedFields[$id])) {
        throw new RuntimeException('HA-managed Radvd field is still visible: ' . $id);
    }
}
if ($managedFields !== $nativeFields) {
    throw new RuntimeException('The managed form changed fields from the system Radvd form.');
}
if (empty($managedFields['entries.mode']['help']) || empty($managedFields['entries.RDNSS']['help'])) {
    throw new RuntimeException('System Radvd help text was not preserved.');
}
echo "PASS: system Radvd form is reused with only three HA-managed fields hidden\n";
