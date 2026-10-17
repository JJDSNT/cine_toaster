---
id: CT-0109
title: LAN-accessible GUI in production-agent onboarding
type: work
status: review
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
tags: [onboarding, gui, network, mobile]
---

# What

Follow-up authorised by the director: configure LAN-scoped Windows forwarding
for the current server and add read-only startup LAN discovery/diagnostics.
Never silently change OS network rules during an ordinary server launch.

Teach production agents to launch the GUI for trusted-LAN/mobile access and
report a usable LAN URL, rather than only localhost. Keep the CLI's safe
loopback default; document an intentional `--host 0.0.0.0` launch.

# Why

The director wants to inspect the film from a phone. The production guide and
MCP onboarding are actual runtime-facing instructions, unlike repository memory.
Listening in Linux does not by itself establish LAN reachability through WSL NAT.

# Done

- Director explicitly authorised opening the LAN port on 2026-10-16. Created
  Windows portproxy `192.168.100.179:8787 -> 172.28.187.15:8787` and firewall
  rule `CineToaster-LAN-8787`: inbound TCP 8787, that local address, Wi-Fi,
  Private profile, LocalSubnet, edge traversal blocked. Windows LAN HTTP 200.
- Added read-only startup URL discovery and bounded Windows forwarding/listener
  checks, with graceful fallback and regression tests. No automatic firewall
  or forwarding writes; no public/sidecar port changes.
- Initial Windows management queries timed out under full regression load;
  replaced them with faster .NET interface/listener queries, retaining the
  eight-second bound and explicit unavailable warning. Real diagnostic passed.
- Director confirmed actual phone access after briefly reporting an interruption.
  Server restarts during validation may explain the interruption; this was not
  independently established. Final server is left running without further restarts.
- Inspected the served filmmaking guide, MCP instructions and existing host
  option. The host is WSL: Linux IPv4 172.28.187.15, Windows Wi-Fi IPv4
  192.168.100.179 (read-only diagnostics, not portable defaults).
- Updated the filmmaking guide served over MCP, MCP onboarding instructions
  and assistant guide: intentional LAN bind, actual host URL, trusted-network
  limits and no silent firewall/forwarding changes. Added a guide regression.
- Restarted Demo 01 with `--host 0.0.0.0 --assistant --no-refresh`, provider
  `codex-cli`. GUI responds HTTP 200 at the Linux network address and assistant
  info remains available through the main origin.
- Confirmed `wslinfo --networking-mode` = `nat`. No Windows portproxy entry for
  8787; Windows listener for that port is only `127.0.0.1`. The Linux bind alone
  therefore does not establish phone reachability through Windows Wi-Fi.

# To do

1. No further network changes requested; retain the current running server.
2. A jobs-test cleanup race observed in regression remains a separate follow-up,
   not an implemented fix in this LAN slice.

# Decisions

- No authentication exists: LAN access is only for a trusted network. Do not
  expose WAN ports, disable firewalls, or publish provider sidecar ports.
- A bind address (`0.0.0.0`) is not a URL to give the person. Discover the
  computer's LAN address; WSL VM and Windows LAN addresses can differ.
- Windows forwarding/firewall changes require explicit direction/authority;
  follow-up permission covers this specific LAN port, not arbitrary changes.
- OS rules persist after the server stops and may need an authorised update
  after DHCP/WSL address changes. Rollback in elevated PowerShell:
  `netsh interface portproxy delete v4tov4 listenaddress=192.168.100.179 listenport=8787`
  and `Remove-NetFirewallRule -Name CineToaster-LAN-8787`. No unrelated rules
  are changed or removed.

# Validation

- Final focused regression passed: 97 tests including onboarding, CLI, MCP,
  Inception and shared Creation operations. `git diff --check` passed.
- Linux network URL HTTP 200; assistant info HTTP 200. Read-only Windows
  networking checks confirmed the NAT/listener/forwarding limitation above.
- Original onboarding-only pass changed no film record/image or OS network
  setting. The explicitly authorised follow-up added only the rules above;
  GUI and assistant info return HTTP 200 through the Windows LAN URL.
- Eight startup tests (including the actual server output integration) and the
  final 43-test network/onboarding/provider/MCP run passed. Full regression ran
  outside the sandbox after an initial restricted run was stopped because
  required local test resources were unavailable: 1129 tests in 591.0 seconds,
  one error in `test_jobs.CancellationTests.test_retry_starts_a_new_attempt`:
  temporary directory cleanup found `state` nonempty. All 20 jobs tests passed
  in an isolated rerun. The full run is not green; no jobs fix is claimed.
  The final startup integration test was added after the full run started and
  is covered by the final focused run. `git diff --check` passed.
- Final server restart prints the Windows LAN URL and matching forwarding /
  listener diagnostic. GUI and assistant info returned HTTP 200 after restart.
  Real film revision 6 / source digest
  `bf256fe23c37e42403aa62041b4af86f99da0dd123b67b8d69d270cfb529dfc2`
  is unchanged; no images, creative records or approvals were modified.
