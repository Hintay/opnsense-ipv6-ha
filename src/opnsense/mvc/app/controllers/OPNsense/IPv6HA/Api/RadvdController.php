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

namespace OPNsense\IPv6HA\Api;

use OPNsense\Base\ApiMutableModelControllerBase;
use OPNsense\Base\UserException;
use OPNsense\IPv6HA\I18n;

class RadvdController extends ApiMutableModelControllerBase
{
    protected static $internalModelName = 'radvd';
    protected static $internalModelClass = 'OPNsense\Radvd\Radvd';

    private function managedLan(): string
    {
        $model = new \OPNsense\IPv6HA\IPv6HA();
        return (string)$model->general->lan_interface;
    }

    private function managedNode($uuid = null)
    {
        $lan = $this->managedLan();
        if ($uuid !== null) {
            $node = $this->getModel()->getNodeByReference('entries.' . $uuid);
            return $node !== null && (string)$node->interface === $lan ? $node : null;
        }
        foreach ($this->getModel()->entries->iterateItems() as $node) {
            if ((string)$node->interface === $lan) {
                return $node;
            }
        }
        return null;
    }

    public function getAction()
    {
        if (!$this->request->isGet()) {
            return ['status' => 'failed'];
        }
        $node = $this->managedNode();
        if ($node === null) {
            return ['status' => 'failed', 'message' => I18n::gettext('Router Advertisement settings not found.')];
        }
        return [
            'status' => 'ok',
            'uuid' => $node->getAttribute('uuid'),
            'entries' => $node->getNodes(),
            'managed' => [
                'interface' => $this->managedLan(),
                'native_enabled' => !$node->enabled->isEmpty(),
            ],
        ];
    }

    public function setAction($uuid = null)
    {
        if ($uuid === null || $this->managedNode($uuid) === null) {
            return ['result' => 'failed'];
        }
        return $this->setBase('entries', 'entries', $uuid, [
            'enabled' => '0',
            'interface' => $this->managedLan(),
            'Base6Interface' => '',
        ]);
    }

    protected function setBaseHook($node)
    {
        $max = $node->MaxRtrAdvInterval->asInt();
        $min = $node->MinRtrAdvInterval->asInt();
        $router = $node->AdvDefaultLifetime->isEmpty() ? 3 * $max : $node->AdvDefaultLifetime->asInt();
        // Same HA-friendly defaults export.php applies; RFC 4862 5.5.3(e) caps what a host will honour.
        $preferred = $node->AdvPreferredLifetime->isEmpty() ? 1800 : $node->AdvPreferredLifetime->asInt();
        $valid = $node->AdvValidLifetime->isEmpty() ? 3600 : $node->AdvValidLifetime->asInt();

        if ($min < 3 || $min > 450 || $max < 4 || $max > 600 || $min > 0.75 * $max) {
            throw new UserException(I18n::gettext('Router Advertisement intervals are outside the IPv6 HA limits.'), I18n::gettext('IPv6 HA validation'));
        }
        if ($router < $max || $router > 1800) {
            throw new UserException(I18n::gettext('Router lifetime must be between the maximum interval and 1800 seconds.'), I18n::gettext('IPv6 HA validation'));
        }
        if ($preferred < $max || $preferred > 3600 || $valid < $preferred || $valid > 7200) {
            throw new UserException(I18n::gettext('Prefix lifetimes are outside the IPv6 HA limits.'), I18n::gettext('IPv6 HA validation'));
        }
        if ($node->AdvRASrcAddress->isEmpty()) {
            throw new UserException(I18n::gettext('A link-local CARP source address is required.'), I18n::gettext('IPv6 HA validation'));
        }
        if ((string)$node->RemoveAdvOnExit === 'on' || (string)$node->DeprecatePrefix === 'on') {
            throw new UserException(I18n::gettext('Shutdown advertisement and prefix deprecation must be Automatic or Off for shared CARP.'), I18n::gettext('IPv6 HA validation'));
        }
    }
}
