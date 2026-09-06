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
  <p class="text-muted">{{ t['subtitle'] }}</p>
  <div id="ha-warning" class="alert alert-warning">{{ t['loading_state'] }}</div>
  <div class="ha-summary">
    <div class="ha-card"><div class="ha-label">{{ t['service'] }}</div><div class="ha-value" id="ha-service">—</div></div>
    <div class="ha-card"><div class="ha-label">{{ t['ipv6_carp'] }}</div><div class="ha-value" id="ha-carp">—</div></div>
    <div class="ha-card"><div class="ha-label">{{ t['ipv6_egress_ra'] }}</div><div class="ha-value" id="ha-health">—</div></div>
    <div class="ha-card"><div class="ha-label">{{ t['local_lan_prefix'] }}</div><div class="ha-value" id="ha-prefix">—</div></div>
  </div>
  <ul class="nav nav-tabs" role="tablist">
    <li class="active"><a data-toggle="tab" href="#ha-settings-tab">{{ t['configuration'] }}</a></li>
    <li><a data-toggle="tab" href="#ha-ra-tab">{{ t['ra_configuration'] }}</a></li>
    <li><a data-toggle="tab" href="#ha-status-tab">{{ t['runtime_details'] }}</a></li>
    <li><a data-toggle="tab" href="#ha-log-tab" id="ha-log-link">{{ t['logs'] }}</a></li>
  </ul>
  <div class="tab-content" style="padding-top:20px">
    <div id="ha-settings-tab" class="tab-pane active">
      <div class="alert alert-info">
        {{ t['ha_scope'] }}
      </div>
      {{ partial("layout_partials/base_form", ['fields': generalForm, 'id': 'frm_IPv6HA']) }}
      <div style="padding:16px">
        <button class="btn btn-primary" id="ha-save" type="button">{{ t['save_apply'] }}</button>
        <button class="btn btn-default" id="ha-apply" type="button">{{ t['apply_saved'] }}</button>
        <button class="btn btn-default" id="ha-check" type="button">{{ t['check_saved'] }}</button>
        <span id="ha-action" class="ha-inline-status" role="status"></span>
      </div>
    </div>
    <div id="ha-ra-tab" class="tab-pane">
      <div class="alert alert-info">
        {{ t['ra_help'] }}
        <a href="/ui/radvd/settings">{{ t['router_advertisements_page'] }}</a>
      </div>
      <div id="ha-ra-missing" class="alert alert-danger" style="display:none">{{ t['ra_load_failed'] }}</div>
      <dl class="dl-horizontal">
        <dt>{{ t['ra_interface'] }}</dt><dd id="ha-ra-interface">—</dd>
      </dl>
      <div id="ha-ra-form-wrap">
        {{ partial("layout_partials/base_form", ['fields': radvdForm, 'id': 'frm_RadvdManaged']) }}
        <p class="text-muted" style="padding:0 16px">{{ t['advanced_hint'] }}</p>
        <div style="padding:16px">
          <button class="btn btn-primary" id="ha-ra-save" type="button">{{ t['ra_save_apply'] }}</button>
          <button class="btn btn-default" id="ha-ra-reload" type="button">{{ t['reload'] }}</button>
          <span id="ha-ra-action" class="ha-inline-status" role="status"></span>
        </div>
      </div>
    </div>
    <div id="ha-status-tab" class="tab-pane">
      <table class="table table-striped" id="ha-runtime"><tbody></tbody></table>
      <h4>{{ t['inherited_settings'] }}</h4>
      <table class="table table-striped"><tbody id="ha-inherited"></tbody></table>
      <h4>{{ t['learned_prefixes'] }}</h4>
      <p class="text-muted">{{ t['learned_prefix_help'] }}</p>
      <table class="table table-striped"><thead><tr><th>{{ t['prefix'] }}</th><th>{{ t['history_expiry'] }}</th></tr></thead><tbody id="ha-prefixes"></tbody></table>
    </div>
    <div id="ha-log-tab" class="tab-pane">
      <div class="table-responsive">
        <div class="col-sm-12" style="float:none">
          <div class="hidden">
            <div id="ha-log-filters" class="btn-group">
              <select id="ha-severity-filter" data-title="{{ t['severity'] }}" class="ha-log-filter selectpicker" data-width="180px">
                <option value="Emergency">{{ t['emergency'] }}</option>
                <option value="Alert">{{ t['alert'] }}</option>
                <option value="Critical">{{ t['critical'] }}</option>
                <option value="Error">{{ t['error'] }}</option>
                <option value="Warning">{{ t['warning'] }}</option>
                <option value="Notice" selected>{{ t['notice'] }}</option>
                <option value="Informational">{{ t['informational'] }}</option>
                <option value="Debug">{{ t['debug'] }}</option>
              </select>
              <select id="ha-history-filter" data-title="{{ t['history'] }}" class="ha-log-filter selectpicker" data-width="180px">
                <option selected value="day">{{ t['last_day'] }}</option>
                <option value="week">{{ t['last_week'] }}</option>
                <option value="month">{{ t['last_month'] }}</option>
                <option value="all">{{ t['no_limit'] }}</option>
              </select>
            </div>
          </div>
          <table id="grid-ipv6ha-log" class="table table-condensed table-hover table-striped table-responsive">
            <thead><tr>
              <th data-column-id="timestamp" data-width="11em" data-type="string">{{ t['date'] }}</th>
              <th data-column-id="severity" data-width="110" data-type="string">{{ t['severity'] }}</th>
              <th data-column-id="process_name" data-width="140" data-type="string">{{ t['process'] }}</th>
              <th data-column-id="line" data-type="string" data-formatter="readableLine">{{ t['message'] }}</th>
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
    var tx = {{ t | json_encode() }};
    var busy = false;
    var raBusy = false;
    var radvdUuid = null;

    function backendMessage(value) {
        var messages = {
            'Invalid HA settings.': tx.error_invalid_settings,
            'Add Router Advertisement settings for the selected LAN first.': tx.error_ra_missing,
            'Router Advertisement settings are invalid.': tx.error_ra_invalid,
            'LAN must track a DHCPv6-PD WAN.': tx.error_pd_tracking,
            'Turn off the selected interface on the system Router Advertisements page; IPv6 HA manages it automatically.': tx.error_ra_enabled,
            'Remove Router Advertisements from HA synchronization.': tx.error_ra_sync,
            'Select an existing link-local CARP address as the Router Advertisement source.': tx.error_ipv6_carp
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
            'Service stopped or runtime status is stale': tx.reason_stale
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

    function refresh() {
        request('service/status', 'GET', function (data) {
            var r = data.runtime || {};
            $('#ha-service').text(data.service_running ? (data.fresh ? tx.running : tx.stale) : tx.stopped);
            $('#ha-carp').text(data.fresh ? (r.carp || tx.unknown_state) : '—');
            var uplink = r.uplink_up === true ? tx.connected : (r.uplink_up === false ? tx.disconnected : tx.standby);
            $('#ha-health').text(data.fresh ? (uplink + ' / ' + (r.ra_running ? tx.advertising : tx.silent)) : '—');
            $('#ha-prefix').text(data.fresh ? (r.prefix || tx.no_prefix) : '—');
            var warnings = [];
            if (['running', 'stopped', 'disabled'].indexOf(data.status) === -1) { warnings.push(tx.backend_invalid); }
            if (!data.configuration_valid) { warnings.push(tx.configuration_failed + backendMessage(data.configuration_error)); }
            if (data.enabled && !data.fresh) { warnings.push(tx.service_not_fresh); }
            if (!data.applied) { warnings.push(tx.not_applied); }
            if (data.maintenance) { warnings.push(tx.maintenance_enabled); }
            $('#ha-warning').text(warnings.join(' ')).toggle(warnings.length > 0);
            var table = $('#ha-runtime tbody').empty();
            [[tx.last_update, r.updated ? new Date(r.updated * 1000).toLocaleString() : null],
             [tx.status_age, data.age_seconds], [tx.service_process, r.process_pid], [tx.reason, runtimeReason(r.reason)],
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
        }).always(function () { window.setTimeout(refresh, 5000); });
    }

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
