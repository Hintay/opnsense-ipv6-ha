<style>
  .ha-summary {display:flex; flex-wrap:wrap; gap:14px; margin:16px 0;}
  .ha-card {flex:1; min-width:160px; padding:16px 20px; border:1px solid #ddd; border-radius:4px;}
  .ha-card .ha-label {font-size:13px; color:#666; margin-bottom:8px;}
  .ha-card .ha-value {font-size:23px; font-weight:600; overflow-wrap:anywhere;}
  #ha-runtime td {overflow-wrap:anywhere;}
  .ha-inline-status {margin-left:12px;}
  #ha-log-filters {margin-left:8px;}
</style>
<div class="content-box" style="padding:20px">
  <p class="text-muted">{{ lang._('The active firewall provides IPv6 service. If the public IPv6 prefix changes after failover, devices must reconnect their IPv6 sessions.') }}</p>
  <div id="ha-warning" class="alert alert-warning">{{ lang._('Loading local status…') }}</div>
  <div class="ha-summary">
    <div class="ha-card"><div class="ha-label">{{ lang._('Service') }}</div><div class="ha-value" id="ha-service">—</div></div>
    <div class="ha-card"><div class="ha-label">{{ lang._('IPv6 CARP') }}</div><div class="ha-value" id="ha-carp">—</div></div>
    <div class="ha-card"><div class="ha-label">{{ lang._('Uplink and Router Advertisements') }}</div><div class="ha-value" id="ha-health">—</div></div>
    <div class="ha-card"><div class="ha-label">{{ lang._('Local LAN prefix') }}</div><div class="ha-value" id="ha-prefix">—</div></div>
  </div>
  <ul class="nav nav-tabs" role="tablist">
    <li class="active"><a data-toggle="tab" href="#ha-settings-tab">{{ lang._('High availability') }}</a></li>
    <li><a data-toggle="tab" href="#ha-ra-tab">{{ lang._('Router Advertisements') }}</a></li>
    <li><a data-toggle="tab" href="#ha-status-tab">{{ lang._('Runtime details') }}</a></li>
    <li><a data-toggle="tab" href="#ha-log-tab" id="ha-log-link">{{ lang._('Logs') }}</a></li>
  </ul>
  <div class="tab-content" style="padding-top:20px">
    <div id="ha-settings-tab" class="tab-pane active">
      <div class="alert alert-info">
        {{ lang._('Select the LAN to manage and pause advertisements on this node when needed.') }}
      </div>
      {{ partial("layout_partials/base_form", ['fields': generalForm, 'id': 'frm_IPv6HA']) }}
      <div style="padding:16px">
        <button class="btn btn-primary" id="ha-save" type="button">{{ lang._('Save and apply') }}</button>
        <button class="btn btn-default" id="ha-apply" type="button">{{ lang._('Apply saved configuration') }}</button>
        <button class="btn btn-default" id="ha-check" type="button">{{ lang._('Check saved configuration') }}</button>
        <span id="ha-action" class="ha-inline-status" role="status"></span>
      </div>
    </div>
    <div id="ha-ra-tab" class="tab-pane">
      <div class="alert alert-info">
        {{ lang._('Configure the Router Advertisements sent to clients on the selected interface.') }}
        <a href="/ui/radvd/settings">{{ lang._('Open the system Router Advertisements page') }}</a>
      </div>
      <div id="ha-ra-missing" class="alert alert-danger" style="display:none">{{ lang._('Router Advertisement settings were not found for the selected interface. Add the interface on the system Router Advertisements page first.') }}</div>
      <dl class="dl-horizontal">
        <dt>{{ lang._('Interface') }}</dt><dd id="ha-ra-interface">—</dd>
      </dl>
      <div id="ha-ra-form-wrap">
        {{ partial("layout_partials/base_form", ['fields': radvdForm, 'id': 'frm_RadvdManaged']) }}
        <p class="text-muted" style="padding:0 16px">{{ lang._('Enable advanced mode at the top of the page to show the remaining settings.') }}</p>
        <div style="padding:16px">
          <button class="btn btn-primary" id="ha-ra-save" type="button">{{ lang._('Save and apply Router Advertisements') }}</button>
          <button class="btn btn-default" id="ha-ra-reload" type="button">{{ lang._('Reload') }}</button>
          <span id="ha-ra-action" class="ha-inline-status" role="status"></span>
        </div>
      </div>
    </div>
    <div id="ha-status-tab" class="tab-pane">
      <table class="table table-striped" id="ha-runtime"><tbody></tbody></table>
      <h4>{{ lang._('Current Router Advertisement parameters') }}</h4>
      <table class="table table-striped"><tbody id="ha-inherited"></tbody></table>
      <h4>{{ lang._('Known prefixes') }}</h4>
      <p class="text-muted">{{ lang._('During takeover, the current prefix is advertised and older known prefixes are marked no longer preferred.') }}</p>
      <table class="table table-striped"><thead><tr><th>{{ lang._('Prefix') }}</th><th>{{ lang._('Expires') }}</th></tr></thead><tbody id="ha-prefixes"></tbody></table>
    </div>
    <div id="ha-log-tab" class="tab-pane">
      <div class="table-responsive">
        <div class="col-sm-12" style="float:none">
          <div class="hidden">
            <div id="ha-log-filters" class="btn-group">
              <select id="ha-severity-filter" data-title="{{ lang._('Severity') }}" class="ha-log-filter selectpicker" data-width="180px">
                <option value="Emergency">{{ lang._('Emergency') }}</option>
                <option value="Alert">{{ lang._('Alert') }}</option>
                <option value="Critical">{{ lang._('Critical') }}</option>
                <option value="Error">{{ lang._('Error') }}</option>
                <option value="Warning">{{ lang._('Warning') }}</option>
                <option value="Notice" selected>{{ lang._('Notice') }}</option>
                <option value="Informational">{{ lang._('Informational') }}</option>
                <option value="Debug">{{ lang._('Debug') }}</option>
              </select>
              <select id="ha-history-filter" data-title="{{ lang._('History') }}" class="ha-log-filter selectpicker" data-width="180px">
                <option selected value="day">{{ lang._('Last day') }}</option>
                <option value="week">{{ lang._('Last week') }}</option>
                <option value="month">{{ lang._('Last month') }}</option>
                <option value="all">{{ lang._('No limit') }}</option>
              </select>
            </div>
          </div>
          <table id="grid-ipv6ha-log" class="table table-condensed table-hover table-striped table-responsive">
            <thead><tr>
              <th data-column-id="timestamp" data-width="11em" data-type="string">{{ lang._('Date') }}</th>
              <th data-column-id="severity" data-width="110" data-type="string">{{ lang._('Severity') }}</th>
              <th data-column-id="process_name" data-width="140" data-type="string">{{ lang._('Process') }}</th>
              <th data-column-id="line" data-type="string" data-formatter="readableLine">{{ lang._('Message') }}</th>
              <th data-column-id="rnum" data-type="numeric" data-visible="false" data-identifier="true"></th>
            </tr></thead>
            <tbody></tbody>
            <tfoot><tr><td></td></tr></tfoot>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
$(function () {
    'use strict';
    var tx = {
        advertising: '{{ lang._('Advertising') }}',
        applied_converging: '{{ lang._('Applied; waiting for convergence') }}',
        automatic: '{{ lang._('Automatic') }}',
        backend_invalid: '{{ lang._('The service did not return a valid status.') }}',
        backend_unavailable: '{{ lang._('Unable to read or operate the service. Check permissions and connectivity.') }}',
        check_passed: '{{ lang._('Check passed') }}',
        connected: '{{ lang._('Connected') }}',
        current_advskew: '{{ lang._('Current advskew') }}',
        default_router_lifetime: '{{ lang._('Default router lifetime') }}',
        disconnected: '{{ lang._('Disconnected') }}',
        effective_mtu: '{{ lang._('Link MTU') }}',
        error_busy: '{{ lang._('Another operation is in progress.') }}',
        error_invalid_settings: '{{ lang._('The high availability settings are invalid.') }}',
        error_ipv6_carp: '{{ lang._('Configure a link-local IPv6 CARP address and select it as the Router Advertisement source.') }}',
        error_pd_tracking: '{{ lang._('The selected LAN must use a DHCPv6-PD prefix from its uplink.') }}',
        error_ra_enabled: '{{ lang._('Turn off this interface on the system Router Advertisements page before enabling IPv6 HA.') }}',
        error_ra_invalid: '{{ lang._('The Router Advertisement settings are invalid.') }}',
        error_ra_missing: '{{ lang._('Add Router Advertisement settings for the selected LAN first.') }}',
        error_ra_sync: '{{ lang._('Remove Router Advertisements from high availability configuration synchronization.') }}',
        failed_prefix: '{{ lang._('Failed: ') }}',
        high: '{{ lang._('High') }}',
        ipv6_vhid: '{{ lang._('CARP VHID') }}',
        lan_ipv6_address: '{{ lang._('LAN IPv6 address') }}',
        last_update: '{{ lang._('Last update') }}',
        loading: '{{ lang._('Loading…') }}',
        log_advertisements: '{{ lang._('Router Advertisements') }}',
        log_role: '{{ lang._('CARP state') }}',
        log_separator: '{{ lang._('; ') }}',
        low: '{{ lang._('Low') }}',
        maintenance_enabled: '{{ lang._('Maintenance mode is enabled on this node.') }}',
        maximum_ra_interval: '{{ lang._('Maximum advertisement interval') }}',
        medium: '{{ lang._('Medium') }}',
        minimum_ra_interval: '{{ lang._('Minimum advertisement interval') }}',
        mode_assist: '{{ lang._('Assisted (DHCPv6 + SLAAC)') }}',
        mode_managed: '{{ lang._('Managed (DHCPv6)') }}',
        mode_router: '{{ lang._('Router only') }}',
        mode_stateless: '{{ lang._('Stateless (SLAAC + DHCPv6 options)') }}',
        mode_unmanaged: '{{ lang._('Unmanaged (SLAAC)') }}',
        no: '{{ lang._('No') }}',
        no_prefix: '{{ lang._('No valid prefix') }}',
        normal_advskew: '{{ lang._('Normal advskew') }}',
        not_applied: '{{ lang._('The saved configuration is not applied, or the service is still starting.') }}',
        off: '{{ lang._('Off') }}',
        on: '{{ lang._('On') }}',
        prefix: '{{ lang._('Prefix') }}',
        prefix_preferred_lifetime: '{{ lang._('Prefix preferred lifetime') }}',
        prefix_valid_lifetime: '{{ lang._('Prefix valid lifetime') }}',
        processing: '{{ lang._('Processing…') }}',
        ra_missing_uuid: '{{ lang._('No Router Advertisement settings are loaded.') }}',
        ra_saved: '{{ lang._('Router Advertisement settings saved and applied') }}',
        ra_saving: '{{ lang._('Saving Router Advertisement settings…') }}',
        ra_source: '{{ lang._('Advertisement source address') }}',
        reason: '{{ lang._('Details') }}',
        reason_carp_disabled: '{{ lang._('CARP administratively disabled') }}',
        reason_carp_wait: '{{ lang._('Waiting for a stable CARP role') }}',
        reason_lan_carp: '{{ lang._('LAN or CARP unavailable') }}',
        reason_maintenance: '{{ lang._('IPv6 HA maintenance enabled') }}',
        reason_no_pd: '{{ lang._('No delegated prefix on the uplink') }}',
        reason_pd_missing: '{{ lang._('Expected exactly one live LAN /64 inside current PD') }}',
        reason_pd_not_gua: '{{ lang._('Delegated prefix is not global unicast') }}',
        reason_ready: '{{ lang._('Uplink, PD and route ready') }}',
        reason_route_missing: '{{ lang._('IPv6 default route is not using the selected uplink') }}',
        reason_standby: '{{ lang._('Standby; waiting for CARP takeover') }}',
        reason_stopped: '{{ lang._('Service stopped') }}',
        reason_wan_down: '{{ lang._('Uplink is not ready') }}',
        running: '{{ lang._('Running') }}',
        saved_applied: '{{ lang._('Saved configuration applied') }}',
        service_not_fresh: '{{ lang._('The service is not running; local IPv6 failover readiness cannot be confirmed.') }}',
        service_process: '{{ lang._('Service process') }}',
        silent: '{{ lang._('Silent') }}',
        standby: '{{ lang._('Standby') }}',
        status_age: '{{ lang._('Status age (seconds)') }}',
        stopped: '{{ lang._('Stopped') }}',
        tracked_wan: '{{ lang._('Uplink interface') }}',
        unknown_reason: '{{ lang._('unknown reason') }}',
        unknown_state: '{{ lang._('Unknown') }}',
        yes: '{{ lang._('Yes') }}'
    };
    var busy = false;
    var raBusy = false;
    var radvdUuid = null;
    var POLL_INTERVAL = 10000;
    var POLL_MAX_INTERVAL = 60000;
    var pollDelay = POLL_INTERVAL;
    var pollTimer = null;

    function backendMessage(value) {
        var messages = {
            'Invalid HA settings.': tx.error_invalid_settings,
            'Add Router Advertisement settings for the selected LAN first.': tx.error_ra_missing,
            'Router Advertisement settings are invalid.': tx.error_ra_invalid,
            'LAN must track a DHCPv6-PD WAN.': tx.error_pd_tracking,
            'Turn off the selected interface on the system Router Advertisements page; IPv6 HA manages it automatically.': tx.error_ra_enabled,
            'Remove Router Advertisements from HA synchronization.': tx.error_ra_sync,
            'Select an existing link-local CARP address as the Router Advertisement source.': tx.error_ipv6_carp,
            'Another operation is in progress.': tx.error_busy
        };
        return messages[value] || value || tx.unknown_reason;
    }

    function request(path, method, done) {
        return $.ajax({url: '/api/ipv6ha/' + path, type: method, dataType: 'json', timeout: 45000})
            .done(done).fail(function (xhr) {
                var response = xhr.responseJSON || {};
                $('#ha-warning').text(backendMessage(response.message || tx.backend_unavailable)).show();
                $('#ha-service').text(tx.unknown_state);
                $('#ha-health').text(tx.unknown_state);
            });
    }

    function row(label, value) {
        return $('<tr>').append($('<th>').text(label), $('<td>').text(value == null ? '—' : value));
    }

    function runtimeReason(value) {
        var reasons = {
            'Uplink, PD and route ready': tx.reason_ready,
            'Standby; waiting for CARP takeover': tx.reason_standby,
            'Waiting for a stable CARP role': tx.reason_carp_wait,
            'Uplink is not running': tx.reason_wan_down,
            'Expected exactly one live LAN /64 inside current PD': tx.reason_pd_missing,
            'IPv6 default route is not the tracked uplink': tx.reason_route_missing,
            'LAN or CARP unavailable': tx.reason_lan_carp,
            'CARP administratively disabled': tx.reason_carp_disabled,
            'IPv6 HA maintenance enabled': tx.reason_maintenance,
            'Service stopped': tx.reason_stopped,
            'No delegated prefix on the uplink': tx.reason_no_pd,
            'Delegated prefix is not global unicast': tx.reason_pd_not_gua
        };
        return reasons[value] || value || tx.unknown_reason;
    }

    function decodeLogEntities(value) {
        var names = {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'"};
        return String(value == null ? '' : value).replace(
            /&(?:#([0-9]{1,7})|#x([0-9a-f]{1,6})|(amp|lt|gt|quot|apos));/gi,
            function (match, decimal, hexadecimal, name) {
                if (name) { return names[name.toLowerCase()]; }
                var codepoint = parseInt(decimal || hexadecimal, hexadecimal ? 16 : 10);
                if (!Number.isFinite(codepoint) || codepoint > 0x10ffff ||
                    (codepoint >= 0xd800 && codepoint <= 0xdfff)) {
                    return match;
                }
                return String.fromCodePoint(codepoint);
            }
        );
    }

    function readableLogLine(value) {
        value = decodeLogEntities(value);
        try {
            var item = JSON.parse(value);
            if (item && typeof item === 'object' && item.carp !== undefined) {
                return [tx.log_role + ': ' + (item.carp || tx.unknown_state),
                        tx.log_advertisements + ': ' + (item.ra_running ? tx.advertising : tx.silent),
                        tx.prefix + ': ' + (item.prefix || tx.no_prefix),
                        tx.reason + ': ' + runtimeReason(item.reason)].join(tx.log_separator);
            }
        } catch (ignore) {
            // Existing plain-text events need no conversion.
        }
        return value;
    }

    function stopPolling() {
        if (pollTimer !== null) {
            window.clearTimeout(pollTimer);
            pollTimer = null;
        }
    }

    // Poll only while the tab is visible; back off on failure so a broken backend is not hammered.
    function schedulePoll() {
        stopPolling();
        if (!document.hidden) {
            pollTimer = window.setTimeout(refresh, pollDelay);
        }
    }

    function refresh() {
        stopPolling();
        request('service/status', 'GET', function (data) {
            var r = data.runtime || {};
            var live = data.service_running === true;
            pollDelay = POLL_INTERVAL;
            $('#ha-service').text(live ? tx.running : tx.stopped);
            $('#ha-carp').text(live ? (r.carp || tx.unknown_state) : '—');
            var uplink = r.uplink_up === true ? tx.connected : (r.uplink_up === false ? tx.disconnected : tx.standby);
            $('#ha-health').text(live ? (uplink + ' / ' + (r.ra_running ? tx.advertising : tx.silent)) : '—');
            $('#ha-prefix').text(live ? (r.prefix || tx.no_prefix) : '—');
            var warnings = [];
            if (['running', 'stopped', 'disabled'].indexOf(data.status) === -1) { warnings.push(tx.backend_invalid); }
            if (data.enabled && !live) { warnings.push(tx.service_not_fresh); }
            if (!data.applied) { warnings.push(tx.not_applied); }
            if (data.maintenance) { warnings.push(tx.maintenance_enabled); }
            $('#ha-warning').text(warnings.join(' ')).toggle(warnings.length > 0);
            var table = $('#ha-runtime tbody').empty();
            [[tx.last_update, r.updated ? new Date(r.updated * 1000).toLocaleString() : null],
             [tx.status_age, r.age_seconds], [tx.service_process, r.process_pid], [tx.reason, runtimeReason(r.reason)],
             [tx.current_advskew, r.skew], [tx.lan_ipv6_address, r.address],
             [tx.saved_applied, data.applied ? tx.yes : tx.no]]
                .forEach(function (entry) { table.append(row(entry[0], entry[1])); });
            var prefixes = $('#ha-prefixes').empty();
            Object.keys(r.learned_prefixes || {}).sort().forEach(function (prefix) {
                prefixes.append(row(prefix, new Date(r.learned_prefixes[prefix] * 1000).toLocaleString()));
            });
            var inherited = $('#ha-inherited').empty();
            var source = data.inherited || {};
            [['lan_interface', 'LAN'], ['wan_interface', tx.tracked_wan], ['vip', tx.ra_source],
             ['vhid', tx.ipv6_vhid], ['normal_skew', tx.normal_advskew], ['mtu', tx.effective_mtu],
             ['min_interval', tx.minimum_ra_interval], ['max_interval', tx.maximum_ra_interval],
             ['router_lifetime', tx.default_router_lifetime], ['preferred_lifetime', tx.prefix_preferred_lifetime],
             ['valid_lifetime', tx.prefix_valid_lifetime]]
                .forEach(function (item) { inherited.append(row(item[1], source[item[0]])); });
        }).fail(function () {
            pollDelay = Math.min(pollDelay * 2, POLL_MAX_INTERVAL);
        }).always(schedulePoll);
    }

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            stopPolling();
        } else {
            pollDelay = POLL_INTERVAL;
            refresh();
        }
    });

    var severityValues = $('#ha-severity-filter option').map(function () { return this.value; }).get();
    var logGrid = $('#grid-ipv6ha-log').UIBootgrid({
        search: '/api/diagnostics/log/core/ipv6ha',
        options: {
            sorting: false,
            rowSelect: false,
            selection: false,
            virtualDOM: true,
            rowCount: [50, 100, 200, 500, 1000],
            formatters: {
                readableLine: function (column, rowData) {
                    // Decode the diagnostics API once, then render as text to prevent HTML injection.
                    return $('<span>').text(readableLogLine(rowData.line || ''))[0];
                }
            },
            requestHandler: function (logRequest) {
                var selected = $('#ha-severity-filter').val();
                var severityIndex = severityValues.indexOf(selected);
                if (severityIndex >= 0) {
                    logRequest.severity = severityValues.slice(0, severityIndex + 1);
                }
                var offsets = {day: 86400, week: 604800, month: 2678400};
                var history = $('#ha-history-filter').val();
                if (offsets[history]) {
                    logRequest.validFrom = Date.now() / 1000 - offsets[history];
                }
                return logRequest;
            }
        },
        tabulatorOptions: {index: 'rnum'}
    });
    $('#ha-log-filters').detach().insertAfter('#grid-ipv6ha-log-header .search');
    $('.ha-log-filter').on('change', function () { $('#grid-ipv6ha-log').bootgrid('reload'); });

    function loadRadvd() {
        $('#ha-ra-action').text(tx.loading);
        return mapDataToFormUI({'frm_RadvdManaged': '/api/ipv6ha/radvd/get'}).done(function (collected) {
            var data = collected.frm_RadvdManaged || {};
            radvdUuid = data.status === 'ok' ? data.uuid : null;
            $('#ha-ra-interface').text(data.managed ? data.managed.interface : '—');
            $('#ha-ra-missing').toggle(!radvdUuid);
            $('#ha-ra-form-wrap').toggle(!!radvdUuid);
            $('#ha-ra-action').text('');
            localizeRadvdOptions();
        });
    }

    function localizeRadvdOptions() {
        var optionSets = {
            'entries.mode': {
                'router': tx.mode_router, 'unmanaged': tx.mode_unmanaged, 'managed': tx.mode_managed,
                'assist': tx.mode_assist, 'stateless': tx.mode_stateless
            },
            'entries.AdvDefaultPreference': {'low': tx.low, 'medium': tx.medium, 'high': tx.high},
            'entries.DeprecatePrefix': {'': tx.automatic, 'on': tx.on, 'off': tx.off},
            'entries.RemoveAdvOnExit': {'': tx.automatic, 'on': tx.on, 'off': tx.off},
            'entries.RemoveRoute': {'': tx.automatic, 'on': tx.on, 'off': tx.off}
        };
        Object.keys(optionSets).forEach(function (id) {
            $('[id="' + id + '"] option').each(function () {
                var label = optionSets[id][this.value];
                if (label) { $(this).text(label); }
            });
        });
        $('.selectpicker').selectpicker('refresh');
    }

    function action(name, done) {
        if (busy) { return; }
        busy = true;
        $('#ha-apply, #ha-check, #ha-save').prop('disabled', true);
        $('#ha-action').text(tx.processing);
        request('service/' + name, 'POST', function (data) {
            $('#ha-action').text(data.status === 'ok' ? (name === 'check' ? tx.check_passed : tx.applied_converging) : (tx.failed_prefix + backendMessage(data.message)));
            if (data.status === 'ok' && done) { done(); }
        }).always(function () {
            busy = false;
            $('#ha-apply, #ha-check, #ha-save').prop('disabled', false);
            updateServiceControlUI('ipv6ha');
        });
    }

    function saveRadvd() {
        if (raBusy) { return; }
        if (!radvdUuid) {
            $('#ha-ra-action').text(tx.ra_missing_uuid);
            return;
        }
        raBusy = true;
        $('#ha-ra-save, #ha-ra-reload').prop('disabled', true);
        $('#ha-ra-action').text(tx.ra_saving);
        function finish() {
            raBusy = false;
            $('#ha-ra-save, #ha-ra-reload').prop('disabled', false);
        }
        saveFormToEndpoint('/api/ipv6ha/radvd/set/' + radvdUuid, 'frm_RadvdManaged', function () {
            request('service/reconfigure', 'POST', function (data) {
                $('#ha-ra-action').text(data.status === 'ok' ? tx.ra_saved : (tx.failed_prefix + backendMessage(data.message)));
                if (data.status === 'ok') { loadRadvd(); }
            }).always(finish);
        }, false, function () {
            $('#ha-ra-action').text(tx.failed_prefix + tx.unknown_reason);
            finish();
        });
    }

    var haLoad = mapDataToFormUI({'frm_IPv6HA': '/api/ipv6ha/settings/get'});
    var raLoad = loadRadvd();
    updateServiceControlUI('ipv6ha');
    $.when(haLoad, raLoad).done(function () {
        formatTokenizersUI();
        $('.selectpicker').selectpicker('refresh');
    });
    $('#ha-save').on('click', function () {
        if (!busy) { saveFormToEndpoint('/api/ipv6ha/settings/set', 'frm_IPv6HA', function () { action('reconfigure', loadRadvd); }); }
    });
    $('#ha-apply').on('click', function () { action('reconfigure', loadRadvd); });
    $('#ha-check').on('click', function () { action('check'); });
    $('#ha-ra-save').on('click', saveRadvd);
    $('#ha-ra-reload').on('click', loadRadvd);
    $('#ha-log-link').on('shown.bs.tab', function () { $('#grid-ipv6ha-log').bootgrid('reload'); });
    refresh();
});
</script>
