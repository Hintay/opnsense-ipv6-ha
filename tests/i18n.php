<?php
require_once __DIR__ . '/../src/opnsense/mvc/app/models/OPNsense/IPv6HA/I18n.php';

$english = \OPNsense\IPv6HA\I18n::catalog('en_US');
$chinese = \OPNsense\IPv6HA\I18n::catalog('zh_CN');
if ($english['configuration'] !== 'High availability' || $chinese['configuration'] !== '高可用') {
    throw new RuntimeException('Locale catalog selection failed.');
}
$form = ['sections' => [['children' => [['label' => 'Enable IPv6 HA', 'help' => 'Provide IPv6 service on the selected LAN from the active firewall.']]]]];
$translated = \OPNsense\IPv6HA\I18n::translateForm($form, 'zh_CN');
if ($translated['sections'][0]['children'][0]['label'] !== '启用 IPv6 高可用' ||
    $translated['sections'][0]['children'][0]['help'] !== '由当前活动节点为所选 LAN 提供 IPv6 服务。') {
    throw new RuntimeException('Form translation failed.');
}
if ($chinese['reason'] !== '详情' || $chinese['inherited_settings'] !== '当前路由通告参数' ||
    $chinese['error_ipv6_carp'] !== '请先配置链路本地 IPv6 CARP 地址，并将其选为路由通告源地址。' ||
    isset($chinese['log_help']) || str_contains($chinese['subtitle'], '·')) {
    throw new RuntimeException('User-facing wording regression.');
}
if (\OPNsense\IPv6HA\I18n::translateForm($form, 'fr_FR') !== $form) {
    throw new RuntimeException('Unknown locale did not fall back to English.');
}
echo "PASS: English and Simplified Chinese UI catalogs\n";
