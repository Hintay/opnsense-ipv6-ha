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

use OPNsense\Core\Config;

/**
 * Fingerprint of every configuration subtree export.php reads, so the UI can tell whether the
 * running service was started from the configuration currently stored in config.xml.
 * Pure in-process XML reading; no process spawn, no file system access beyond the config singleton.
 */
final class SourceHash
{
    /**
     * @return string|null sha256 of the relevant configuration subtrees, null when unreadable
     */
    public static function current(): ?string
    {
        try {
            $config = Config::getInstance()->object();
            $lan = (string)($config->OPNsense->IPv6HA->general->lan_interface ?? '');
            $wan = '';
            if ($lan !== '' && isset($config->interfaces->{$lan})) {
                $wan = (string)($config->interfaces->{$lan}->{'track6-interface'} ?? '');
            }
            $parts = [
                self::render($config->OPNsense->IPv6HA ?? null),
                self::render(self::radvdEntry($config, $lan)),
                self::render($lan !== '' ? ($config->interfaces->{$lan} ?? null) : null),
                self::render($wan !== '' ? ($config->interfaces->{$wan} ?? null) : null),
                self::renderAll(self::interfaceVips($config, $lan)),
                self::render($config->hasync->syncitems ?? null),
                self::renderAll(self::repeated($config->system ?? null, 'dnsserver')),
                self::render($config->system->domain ?? null),
            ];
            return hash('sha256', implode("\n", $parts));
        } catch (\Throwable $error) {
            return null;
        }
    }

    /**
     * The single radvd entry bound to the managed LAN, if any.
     */
    private static function radvdEntry($config, string $lan)
    {
        if ($lan === '' || !isset($config->OPNsense->radvd->entries)) {
            return null;
        }
        foreach ($config->OPNsense->radvd->entries->children() as $entry) {
            if ((string)($entry->interface ?? '') === $lan) {
                return $entry;
            }
        }
        return null;
    }

    /**
     * Every virtual IP attached to the managed LAN; export.php inspects both CARP and IPv4 entries.
     */
    private static function interfaceVips($config, string $lan): array
    {
        $result = [];
        if ($lan === '') {
            return $result;
        }
        foreach (self::repeated($config->virtualip ?? null, 'vip') as $vip) {
            if ((string)($vip->interface ?? '') === $lan) {
                $result[] = $vip;
            }
        }
        return $result;
    }

    /**
     * Repeated child elements of a node, tolerating a missing parent.
     */
    private static function repeated($parent, string $tag): array
    {
        if ($parent === null || !isset($parent->{$tag})) {
            return [];
        }
        $result = [];
        foreach ($parent->{$tag} as $child) {
            $result[] = $child;
        }
        return $result;
    }

    private static function render($node): string
    {
        // Ignore indentation so a reformatted config.xml does not read as a pending change.
        return $node === null ? '' : trim(preg_replace('/>\s+</', '><', (string)$node->asXML()));
    }

    private static function renderAll(array $nodes): string
    {
        $parts = [];
        foreach ($nodes as $node) {
            $parts[] = self::render($node);
        }
        sort($parts);
        return implode('', $parts);
    }
}
