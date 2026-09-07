#!/usr/local/bin/php
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

require_once('config.inc');
require_once('util.inc');

// Make sure the model section exists with current defaults and drop fields that older
// releases stored in config.xml but that are now inherited from the native radvd model.
$instance = \OPNsense\Core\Config::getInstance();
$instance->lock();
try {
    $model = new \OPNsense\IPv6HA\IPv6HA();
    if (count($model->performValidation(true))) {
        throw new RuntimeException('Migrated HA configuration is invalid.');
    }
    $model->serializeToConfig();
    $general = $instance->object()->OPNsense->IPv6HA->general ?? null;
    if ($general !== null) {
        foreach (['wan_interface', 'vip', 'vhid', 'normal_skew', 'mtu', 'min_interval', 'max_interval',
            'router_lifetime', 'preferred_lifetime', 'valid_lifetime', 'failed_skew', 'targets',
            'probe_interval', 'failure_count', 'success_count', 'recovery_hold'] as $field) {
            unset($general->$field);
        }
    }
    $instance->save(['description' => 'IPv6 HA: update settings']);
} finally {
    $instance->unlock();
}
