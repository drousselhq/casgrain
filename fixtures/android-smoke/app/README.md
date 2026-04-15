# Android smoke fixture app

This Gradle project is the minimal real Android app for the first Casgrain Android smoke slice.

Contract:
- package id: `hq.droussel.casgrain.smoke`
- launchable main activity: `hq.droussel.casgrain.smoke.MainActivity`
- button accessibility identifier: `tap-button`
- counter label accessibility identifier: `count-label`
- initial visible state: `Count: 0`
- post-tap visible state: `Count: 1`

Build a debug APK from this directory with a local Android toolchain:

```bash
gradle assembleDebug
```

The default smoke harness expects the resulting APK at:

```text
fixtures/android-smoke/app/build/outputs/apk/debug/app-debug.apk
```

Or override that path at runtime with `CASGRAIN_ANDROID_SMOKE_APK`.
