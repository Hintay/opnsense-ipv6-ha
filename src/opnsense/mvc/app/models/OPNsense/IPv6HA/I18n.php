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

/**
 * Gettext helper for the os-ipv6-ha textdomain. The locale itself is already
 * selected by core's ControllerRoot::setLang().
 */
final class I18n
{
    public const DOMAIN = 'os-ipv6-ha';

    /**
     * translate a single message through the plugin catalog
     * @param string $msgid untranslated English text
     * @return string translation, or $msgid when the catalog has none
     */
    public static function gettext(string $msgid): string
    {
        static $bound = false;
        if (!$bound) {
            bindtextdomain(self::DOMAIN, '/usr/local/share/locale');
            bind_textdomain_codeset(self::DOMAIN, 'UTF-8');
            $bound = true;
        }
        return $msgid === '' ? $msgid : dgettext(self::DOMAIN, $msgid);
    }

    /**
     * translate the user facing texts of a getForm() result
     * @param array $form form definition as returned by getForm()
     * @return array same structure with translated texts
     */
    public static function translateForm(array $form): array
    {
        return self::walk($form);
    }

    private static function walk(array $node): array
    {
        foreach ($node as $key => $value) {
            if (is_array($value)) {
                $node[$key] = self::walk($value);
            } elseif (is_string($value) && $value !== '' &&
                    in_array($key, ['label', 'help', 'hint', 'tab_descr'], true)) {
                $node[$key] = self::gettext($value);
            }
        }
        return $node;
    }
}
