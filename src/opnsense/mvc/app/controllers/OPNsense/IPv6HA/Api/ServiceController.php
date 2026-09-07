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

use OPNsense\Core\Backend;
use OPNsense\IPv6HA\I18n;
use OPNsense\IPv6HA\IPv6HA;
use OPNsense\IPv6HA\SourceHash;

class ServiceController extends \OPNsense\Base\ApiControllerBase
{
    private function invoke($action)
    {
        try {
            $output = (new Backend())->configdRun('ipv6ha ' . $action);
        } catch (\Throwable $error) {
            return ['status' => 'failed', 'message' => I18n::gettext('Backend unavailable.')];
        }
        $result = json_decode($output, true);
        return is_array($result) ? $result : ['status' => 'failed', 'message' => I18n::gettext('Backend unavailable.')];
    }

    public function statusAction()
    {
        $result = $this->invoke('status');
        if (($result['status'] ?? '') === 'ok') {
            // The backend reports the configuration it is running; intent comes from the saved model.
            $model = new IPv6HA();
            $enabled = (string)$model->general->enabled === '1';
            $result['enabled'] = $enabled;
            $result['maintenance'] = (string)$model->general->maintenance === '1';
            $running = !empty($result['service_running']);
            $saved = SourceHash::current();
            $result['applied'] = $enabled
                ? ($running && $saved !== null && ($result['runtime']['source_hash'] ?? null) === $saved)
                : !$running;
            $result['status'] = !$enabled ? 'disabled' : ($running ? 'running' : 'stopped');
            $result['widget'] = [
                'caption_restart' => I18n::gettext('Restart'),
                'caption_start' => I18n::gettext('Start'),
                'caption_stop' => I18n::gettext('Stop'),
            ];
        }
        return $result;
    }

    public function startAction()
    {
        $this->throwReadOnly();
        return $this->request->isPost() ? $this->invoke('start') : ['status' => 'failed'];
    }

    public function restartAction()
    {
        $this->throwReadOnly();
        return $this->request->isPost() ? $this->invoke('restart') : ['status' => 'failed'];
    }

    public function stopAction()
    {
        $this->throwReadOnly();
        return $this->request->isPost() ? $this->invoke('stop') : ['status' => 'failed'];
    }

    public function reconfigureAction()
    {
        $this->throwReadOnly();
        return $this->request->isPost() ? $this->invoke('apply') : ['status' => 'failed'];
    }

    public function checkAction()
    {
        return $this->request->isPost() ? $this->invoke('check') : ['status' => 'failed'];
    }
}
