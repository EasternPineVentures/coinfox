# Governance

CoinFox is an open-source project from **Eastern Pine Intelligence**, the
technical lab from **Eastern Pine Ventures**. Eastern Pine Ventures remains the
company and umbrella identity. Eastern Pine Intelligence is the repo-facing lab
identity for open-source tooling and research.

## Roles

### Contributors

Contributors open useful issues, discussions, docs, tests, and pull requests.

Responsibilities:

- Follow the contribution guide and Code of Conduct.
- Keep source, model, and safety claims transparent.
- Add tests or explain why tests are not possible.
- Use plain English for user-facing changes.

### Trusted Contributors

Trusted Contributors have a track record of useful issues, reviews, docs, or
merged PRs.

Responsibilities:

- Triage issues.
- Review low-risk PRs.
- Mentor new contributors.
- Escalate model, security, or abuse concerns to maintainers.

Trusted Contributor status does not grant automatic merge rights.

### Maintainers

Maintainers are responsible for project direction, release quality, final merge
decisions, and safety calls.

Responsibilities:

- Review and merge pull requests.
- Set roadmap priorities and quality bars.
- Manage CI requirements and release cadence.
- Resolve disputes and enforce the Code of Conduct.
- Own high-risk abuse, security, and model-integrity decisions.

### Project Management Committee

If CoinFox grows beyond a small maintainer group, Eastern Pine Intelligence may
form a project management committee for roadmap, release, security, and
maintainer-nomination decisions.

## Decision Process

- Day-to-day technical changes: maintainer discretion after review.
- Significant architecture changes: issue discussion first, then PR.
- Changes to the public `LONG` / `SHORT` / `NEUTRAL` contract: issue discussion
  first, tests required, replay comparison preferred.
- Security or safety concerns: maintainers may fast-track fixes.
- High-risk community-guard findings: maintainer review before merge or public
  escalation.

## Voting

For ordinary project votes, use lazy consensus:

1. A maintainer opens an issue or discussion with a clear proposal.
2. Contributors have at least 72 hours to comment unless the issue is urgent.
3. If there is no material objection, maintainers may proceed.
4. Material objections require maintainer discussion and a recorded decision.

Security fixes and abuse response may move faster when needed.

## Path To Maintainer

Contributors may be invited to maintainer status based on:

- consistent high-quality contributions;
- reliability in reviews and follow-through;
- alignment with free-first, transparent, safe defaults;
- good judgment around abuse prevention, secrets, and user trust;
- ability to explain changes clearly.

## Abuse Prevention

CoinFox is open source, not open season. The project keeps contribution friction
low for good actors and raises friction for risky behavior.

Maintainers may:

- close or lock spam, credential-harvesting, or unsafe automation requests;
- require extra review for sensitive files such as CI, package metadata, AI
  routing, model logic, and bias output;
- temporarily restrict contributors who repeatedly ignore templates or safety
  rules;
- fast-track fixes for leaked secrets, CI injection, or model-manipulation risk.

No real-money staking or token gate is required for ordinary contribution.
Optional future staking or bounty systems must be documented separately and must
not replace safety review.

## Ecosystem Boundaries

- **Eastern Pine Ventures**: company and umbrella.
- **Eastern Pine Intelligence**: open-source technical lab.
- **CoinFox**: public market intelligence terminal.
- **FoxClaw**: deeper internal/operator intelligence system.
- **Redshift**: simulation, replay, and paper-trading research lane.

CoinFox owns the public product voice. FoxClaw and Redshift may inform research
and context, but they should not blur CoinFox into live execution authority.
