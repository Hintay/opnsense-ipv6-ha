<?php
namespace OPNsense\IPv6HA\Api;

use OPNsense\Core\Backend;

class ServiceController extends \OPNsense\Base\ApiControllerBase
{
    private function invoke($action)
    {
        try {
            $output = (new Backend())->configdRun('ipv6ha ' . $action);
        } catch (\Throwable $error) {
            return ['status' => 'failed', 'message' => gettext('Backend unavailable.')];
        }
        $result = json_decode($output, true);
        return is_array($result) ? $result : ['status' => 'failed', 'message' => gettext('Backend unavailable.')];
    }

    public function statusAction()
    {
        $result = $this->invoke('status');
        if (($result['status'] ?? '') === 'ok') {
            if (!($result['enabled'] ?? false)) {
                $result['status'] = 'disabled';
            } else {
                $result['status'] = ($result['service_running'] ?? false) ? 'running' : 'stopped';
            }
            $result['widget'] = [
                'caption_restart' => gettext('Restart'),
                'caption_start' => gettext('Start'),
                'caption_stop' => gettext('Stop'),
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
