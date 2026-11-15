# Build 21 verification — 2026-11-15

The owner explicitly retains responsibility for device/gameplay acceptance. No phone or emulator was operated for this release.

Passed in this revision:

- assembleRelease and lintRelease: zero errors, 58 warnings.
- APK application ID cos.premy.mines.haoke, version 1.7.1-haoke.2 / 21, minSdk 19; non-debuggable, zipalign and v1/v2/v3 release signatures.
- Certificate exactly matches formal build 20, allowing a normal signed upgrade without intentionally clearing data.
- Final DEX contains both requested Chinese login texts, English equivalents, QQ group 1841958554 and the exact owner-provided common URL. The old password placeholder is absent.
- Shared community helper is called from Home and the online lobby; account/session, game, server and room logic were not changed.
- Shared integration skill frontmatter validation and 21 isolated tool tests passed. New cases cover user-supplied external/common URLs, missing URLs, legacy configurations and no implicit installer upload.

Not runtime-verified: visual layout and keyboard/locale behavior, Android share sheet/copy/browser fallback, installed/missing QQ and QQ-version-specific group card navigation, return-to-game behavior, physical upgrade/data retention, weak-network matches and performance. The QQ URI launches the standard QQ package; players can always use the visible copy-group option if QQ does not support the card action. No automatic sharing or joining is performed.

Historical evidence only: build 20 passed 28 updater JVM checks plus one product feed check; QA.5 passed 32 game JVM checks and 107 backend checks, one physical phone plus emulator cooperation, maximum-board checks and companion-client mode completions. A low-battery phone run stopped around nine minutes and is not a completed 10–15 minute soak. Public two-device full-round, six physical devices, low-end and load testing remain unverified.

Distribution uses the exact owner-provided download/share URL: https://www.haoke.org/software/491ec4cb67f1146b?platform=android . No APK is uploaded to the game site or GitHub. Original user-managed cloud links remain; the owner handles their files. Signed-notification audience remains API 21+, while the APK remains API 19+.
