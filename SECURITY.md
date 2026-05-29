# Security Policy

CoinFox is an educational market intelligence tool from Eastern Pine
Intelligence. It does not custody funds, place real trades by default, or ask
users for exchange keys.

## Reporting

Please do not open public issues for vulnerabilities, leaked credentials, or
abuse techniques. Use GitHub private vulnerability reporting when available, or
contact a maintainer privately.

Include:

- affected version or commit;
- reproduction steps;
- impact and scope;
- whether any secret, key, account, or user data may have been exposed.

## Scope

In scope:

- secret leaks;
- unsafe automation paths;
- CI or GitHub Actions injection;
- API abuse or denial-of-service weaknesses;
- model or bias manipulation that could mislead users at scale;
- accidental collection of personal identity or private trading data.

Out of scope:

- financial losses from using CoinFox output;
- issues caused by private forks or modified deployments;
- social engineering against maintainers.

## Privacy Defaults

CoinFox should not store personal identity by default. Future feedback learning
should use random anonymous local IDs unless a user explicitly opts into an
account system later.

## Maintainer Response

Security fixes may be fast-tracked by maintainers. Public disclosure should wait
until users have a reasonable path to update or mitigate the issue.
