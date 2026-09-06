# OPNsense IPv6 高可用

[English](README.md)

OPNsense IPv6 HA 用于协调 CARP 主备节点上的路由通告，适用于上游提供动态 DHCPv6 前缀委派（PD）的网络。活动节点通告当前获得的前缀，备用节点保持静默，并记录角色切换后可能需要撤销的旧前缀。

这是社区维护的插件，不属于 OPNsense 官方插件集合。

1.0 版本面向运行于 FreeBSD 15 amd64 的 OPNsense 26.7。

## 功能

- 跟随 CARP 角色变化和本机动态上游事件。
- 支持 PPPoE，以及其他能够向 OPNsense 提供 DHCPv6-PD 的上游。
- 直接使用 OPNsense 已有的路由通告配置，不保存第二份参数。
- 角色切换后撤销近期观察到的旧前缀。
- 提供 OPNsense MVC 页面、服务控制、API、访问权限和系统日志表格。
- 界面支持英文和简体中文。
- 不探测公网 IPv6，也不管理拨号会话。

## 适用范围与限制

动态 PD 无法实现保持连接的无缝切换。接管节点可能获得不同的前缀，已有 IPv6 连接会中断，客户端也可能需要一段时间才能采用新前缀。

插件只控制路由通告。CARP、DHCPv6-PD、防火墙规则、状态同步、路由和上游连接必须预先在两台节点上正常工作。没有外部防护时，网络分区仍可能产生两个 CARP `MASTER`。

## 使用条件

- 两台 OPNsense 已正确配置 CARP。
- 每台节点接管后都能通过动态上游获得 DHCPv6-PD。
- LAN IPv6 跟踪该上游接口。
- LAN 上配置专用的链路本地 IPv6 CARP 地址。
- LAN 已有路由通告条目，并关闭其中的**启用**选项。
- XMLRPC 配置同步中不包含路由通告。
- 已安装 `radvd`；安装包会将其作为依赖处理。

如果 PPPoE 需要随 CARP 角色连接或断开，请在 OPNsense 中配置。插件不会建立、维持或终止 PPPoE 会话。

## 安装

从 GitHub Release 下载 `os-ipv6-ha-1.0.pkg` 并复制到防火墙。`os-ipv6-ha-1.0.pkg.dgst` 是可选的，可用于校验下载文件：

```sh
FILE=os-ipv6-ha-1.0.pkg
for METHOD in md5 sha1 sha256 sha512; do
  openssl dgst "-${METHOD}" "$FILE" | sed 's/([^)]*)//g'
done | diff -u "$FILE.dgst" -
```

安装插件：

```sh
pkg add -f ./os-ipv6-ha-1.0.pkg
```

两台节点都需要安装。建议先配置备用节点，再配置活动节点。

## 配置

1. 打开**服务 → IPv6 HA**。
2. 选择跟踪委派前缀的 LAN。
3. 检查同一页面中的路由通告设置。
4. 分别在两台节点保存配置。
5. 两台节点的**检查配置**均通过后，再启用 IPv6 高可用。

插件配置有意保存在各节点本地，不加入 XMLRPC 同步。

只有同时满足以下条件，插件才会发送路由通告：

- 所选 IPv6 CARP 地址为 `MASTER`；
- 上游接口可用；
- LAN 只有一个属于当前委派前缀的可用 `/64` 地址；
- IPv6 默认路由使用该上游接口；
- 本机维护模式已关闭。

服务会立即响应 CARP 和上游事件。30 秒看门狗仅用于补偿遗漏的本机事件，不会探测公网连通性。

## 日常操作

```sh
configctl ipv6ha status
configctl ipv6ha check
configctl ipv6ha apply
pkg check -s os-ipv6-ha
```

日志可在插件页面和 `/var/log/ipv6ha/` 中查看。

本机维护模式只停止当前节点的路由通告，不改变 CARP 或上游设置。停止插件服务的影响范围相同。

## 升级与卸载

使用 `pkg add -f` 安装新版。插件设置和路由通告设置会保留。

卸载前应确认其他路由器已经提供所需的 IPv6 服务。卸载会停止插件，并保持 OPNsense 路由通告条目处于关闭状态：

```sh
pkg delete -y os-ipv6-ha
```

## 构建

推荐使用 OPNsense 官方插件构建环境。也可以在 FreeBSD/OPNsense 上运行独立构建器：

```sh
python3 tools/build.py
```

生成的安装包位于 `dist/`。在普通 FreeBSD 构建机上，需要设置 `OPNSENSE_VERSION`，以便在安装包清单中记录目标 OPNsense 依赖。

## 开发

通用测试位于 `tests/`。部分集成测试依赖完整的 OPNsense MVC 环境，应在隔离的 OPNsense 测试系统中执行。

贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)，漏洞报告方式见 [SECURITY.md](SECURITY.md)。

## 许可证

BSD 2-Clause，详见 [LICENSE](LICENSE)。
