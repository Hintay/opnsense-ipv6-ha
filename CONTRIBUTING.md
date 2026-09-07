# Contributing

Bug reports and focused pull requests are welcome.

Before opening a pull request:

1. Describe the affected OPNsense and FreeBSD versions.
2. Keep node-specific addresses, credentials, logs, and packet captures out of the repository.
3. Run the generic Python tests on FreeBSD.
4. Run PHP syntax checks and the OPNsense integration tests when the change affects the MVC layer.
5. Run `python3 tools/i18n.py extract`, `update` and `compile` when user-visible text changes, and keep `locale/zh_CN.po` translated.
6. Use a [Conventional Commit](https://www.conventionalcommits.org/) subject.

Changes that can affect CARP, routing, or Router Advertisements should include a safe test procedure. Do not use production failover tests as the first validation step.
