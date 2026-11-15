# Formal build 20 verification — 2026-11-15

The owner explicitly stopped further gameplay/device testing and chose personal acceptance. This scope remains in force for the formal package; no formal device installation, device upgrade or game-session pass is claimed.

This release passed the native signed-update module's 28 JVM checks, covering real exact-byte signature interoperability, tampering, unknown key/schema, expiry, replay, product/channel/certificate identity, compatibility, storage, simultaneous/manual checks, cancellation, reminders and bounded retry policy. A separate test passed against the newly registered Mines3D stable `none` feed using the compiled trust pin and rejected QA/foreign identities. The test fixture's historical validation time is intentional. Release compilation and Android lint passed (zero errors, existing warnings retained). The final artifact was inspected for package/build/minSdk, non-debuggable status, zip alignment and v1/v2/v3 release signatures.

The new icon has a preserved RGBA master, density PNGs, round PNGs and adaptive layers. It was visually inspected as an asset; actual launcher masks on physical devices remain untested. Simplified Chinese and English update/About strings follow the existing first-system-language selector. Device language switching, dialog appearance and update lifecycle on a physical phone were not rerun.

Historical QA.5 evidence, not a claim about formal-package device tests:

- 32 game JVM tests and lint passed before the user stopped testing.
- 107 isolated backend tests passed locally and on the target Linux host.
- One physical phone plus one emulator completed the cooperating room/game/result/restart path, pinch/pan, scan/mark confirmation, rescue, background/resume and host transfer.
- The phone's maximum 15×15×8 board checks passed for corners, inner decks and camera actions without board mutation.
- The emulator plus protocol companions exercised legitimate results in the additional multiplayer modes with 2–6 participants. This was not six physical phones.
- The final QA solo flow runner passed its six modes and maximum-board checks.
- A phone stress run was interrupted around nine minutes by a system overlay at low battery. This is not a completed 10–15 minute soak and the recorded GL callback rate is not measured presentation FPS.

Not verified: a complete public-network two-device match after deployment, six physical devices, weak-network/load limits, low-end phone performance, formal-device installation/upgrade/update UI and a completed sustained phone stress run. The server and protocol are retained; production availability checks do not substitute for those gameplay checks.
