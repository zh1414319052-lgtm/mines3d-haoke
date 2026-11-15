# Mines3D

Minesweeper on an n×m×(2–8) grid for Android. Plain Java, com.android.support 28 libraries, OpenGL ES 2,
minSdk 19, targetSdk 36. See README.md and art/mine_scene/PHASE_2_HANDOFF.md.
Each GameActivity owns LoadedGame; BoardDefinition/BoardMoves share the six-neighbor rules
across all six modes. BoardViewport renders exported Blender meshes and picks their actual
triangles. FlatBoardViewport is the compatibility path. Bundle and SessionStore preserve
the game, camera, hints/scans and one-shot explosion phase. Legacy MinesView is not the main UI.

## Build and test
- `local.properties` is machine-specific and excluded from the source archive; export
  `ANDROID_HOME` (the SDK with `platforms;android-36`) on a new machine before running Gradle.
- `./gradlew build` compiles, lints (report in `app/build/reports/`) and runs the JVM unit tests;
  `./gradlew testDebugUnitTest` runs the tests alone.
- Unit tests live in `app/src/test/java` and run against the stub `android.jar` with
  `unitTests.returnDefaultValues = true`; Android classes are mocked or spied with Mockito.

## Target SDK 36 decisions
- Edge-to-edge is mandatory since targetSdk 35 and `windowOptOutEdgeToEdgeEnforcement` is ignored at 36.
  `SystemBarsPadding.apply(this)` is called right after `setContentView` in every activity: it pads
  `android.R.id.content` by the system window insets and paints only the strips behind the transparent
  bars black, so the screens look exactly like the black status/navigation bars the app had before.
  The AppCompat sub-decor cannot do this itself because it is flagged "optional fits system windows".
  The compat system window insets include the display cutout, so a notch on the side in landscape is
  padded as well (verified on the API 36 emulator with the emulated cutout overlay).
- The theme keeps `android:navigationBarColor` black, which still tints the three-button navigation
  scrim on Android 15+ (the attribute is ignored for gesture navigation).
- Predictive back is on by default at targetSdk 36; the app never intercepts back, so nothing else is
  needed. Do not add `enableOnBackInvokedCallback="false"`.
