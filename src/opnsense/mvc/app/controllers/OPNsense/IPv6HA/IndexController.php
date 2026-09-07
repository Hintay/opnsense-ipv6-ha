<?php

/*
 * Copyright (c) 2026 IPv6 HA contributors
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

namespace OPNsense\IPv6HA;

use Phalcon\Translate\InterpolatorFactory;

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

    /**
     * keep core's language selection, but translate views through the plugin catalog first
     */
    protected function setLang()
    {
        parent::setLang();
        $interpolator = new InterpolatorFactory();
        $this->translator = new Translator($interpolator, [
            'directory' => '/usr/local/share/locale',
            'defaultDomain' => 'OPNsense',
            'locale' => [$this->langcode . '.UTF-8'],
        ]);
    }

    public function indexAction()
    {
        $this->view->pick('OPNsense/IPv6HA/index');
        $this->view->generalForm = I18n::translateForm($this->getForm('general'));
        $nativeRadvd = (new \OPNsense\Radvd\SettingsController())->getForm('dialogEntry');
        $this->view->radvdForm = self::managedRadvdForm($nativeRadvd);
    }
}
