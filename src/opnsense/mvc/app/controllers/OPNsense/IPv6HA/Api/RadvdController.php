<?php
namespace OPNsense\IPv6HA\Api;

use OPNsense\Base\ApiMutableModelControllerBase;
use OPNsense\Base\UserException;

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
            return ['status' => 'failed', 'message' => gettext('Router Advertisement settings not found.')];
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
        $preferred = $node->AdvPreferredLifetime->isEmpty() ? 14400 : $node->AdvPreferredLifetime->asInt();
        $valid = $node->AdvValidLifetime->isEmpty() ? 86400 : $node->AdvValidLifetime->asInt();

        if ($min < 3 || $min > 450 || $max < 4 || $max > 600 || $min > 0.75 * $max) {
            throw new UserException(gettext('Router Advertisement intervals are outside the IPv6 HA limits.'), gettext('IPv6 HA validation'));
        }
        if ($router < $max || $router > 1800) {
            throw new UserException(gettext('Router lifetime must be between the maximum interval and 1800 seconds.'), gettext('IPv6 HA validation'));
        }
        if ($preferred < $max || $preferred > 3600 || $valid < $preferred || $valid > 7200) {
            throw new UserException(gettext('Prefix lifetimes are outside the IPv6 HA limits.'), gettext('IPv6 HA validation'));
        }
        if ($node->AdvRASrcAddress->isEmpty()) {
            throw new UserException(gettext('A link-local CARP source address is required.'), gettext('IPv6 HA validation'));
        }
        if ((string)$node->RemoveAdvOnExit === 'on' || (string)$node->DeprecatePrefix === 'on') {
            throw new UserException(gettext('Shutdown advertisement and prefix deprecation must be Automatic or Off for shared CARP.'), gettext('IPv6 HA validation'));
        }
    }
}
