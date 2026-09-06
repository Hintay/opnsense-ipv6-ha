<?php
namespace OPNsense\IPv6HA;

class IndexController extends \OPNsense\Base\IndexController
{
    private static function managedRadvdForm(array $form): array
    {
        $managed = ['entries.enabled', 'entries.interface', 'entries.Base6Interface'];
        foreach ($form['sections'] as &$section) {
            $section['children'] = array_values(array_filter(
                $section['children'],
                static fn($field) => !in_array($field['id'] ?? '', $managed, true)
            ));
        }
        unset($section);
        return $form;
    }

    public function indexAction()
    {
        $this->view->pick('OPNsense/IPv6HA/index');
        $translations = I18n::catalog($this->langcode);
        $this->view->t = $translations;
        $this->view->generalForm = I18n::translateForm($this->getForm('general'), $this->langcode);
        $nativeRadvd = (new \OPNsense\Radvd\SettingsController())->getForm('dialogEntry');
        $this->view->radvdForm = self::managedRadvdForm($nativeRadvd);
    }
}
