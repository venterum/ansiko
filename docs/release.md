# Release notes

## Versions

The Python package and the Android app share `0.3.0`. Bump `server/pyproject.toml`,
`server/ansiko/__init__.py`, `android/app/build.gradle.kts` (`versionName` and
`versionCode`) together. `versionCode` must increase for every APK delivered to a phone.

## Server

```sh
cd server
python -m pytest
python -m ruff check ansiko tests
python -m pip wheel . -w /tmp/ansiko-wheel --no-deps
```

The wheel must contain `ansiko/resources/boards/...` and
`ansiko/resources/widgets/...`; `tests/test_resources.py` and the CI workflow check this.
The top-level `boards/` and `widgets/` directories are the editable source; after changing
them run:

```sh
python scripts/sync_bundled.py
```

## Android signing

Never commit a keystore or its passwords. Create one outside the repository and point
`android/keystore.properties` at it:

```properties
storeFile=/root/.ansiko/ansiko-release.jks
storePassword=...
keyAlias=ansiko
keyPassword=...
```

`android/keystore.properties` is ignored by git. Generate the key once and keep a
backup; losing it means future APKs cannot update an installed release.

```sh
cd android
ANDROID_HOME=/opt/android-sdk ./gradlew clean assembleRelease
```

Without `keystore.properties`, `assembleRelease` produces an unsigned APK; that is
expected for CI and for local debug builds.

The `Release` GitHub workflow runs on tags matching `v*`. Configure these repository
secrets before tagging: `ANDROID_KEYSTORE_BASE64` (base64 of the `.jks`),
`ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`. It builds a
signed APK, verifies it, and publishes the APK, wheel and SHA-256 file as release assets.

## Verify the APK

```sh
APK=app/build/outputs/apk/release/app-release.apk
/opt/android-sdk/build-tools/37.0.0/apksigner verify --print-certs "$APK"
/opt/android-sdk/build-tools/37.0.0/aapt2 dump badging "$APK" | head -1
sha256sum "$APK"
```

Install the APK over an existing build with `adb install -r`, or publish it as a GitHub
Release asset. The settings screen shows the installed version, so a screenshot proves
which build is on the phone.

## Always-on limits

`MainActivity` asks to be shown over the lock screen and to turn the screen on, and it
starts after `BOOT_COMPLETED` when a server address is saved. Android 10+ can block
background activity launches; for a dedicated phone either allow Ansiko to start in the
background (vendor settings vary), open it once after boot, or enable the optional kiosk
mode. Kiosk mode uses Android screen pinning and can be exited with the system gesture.

## Checklist

- [ ] `python scripts/sync_bundled.py` was run after board/widget edits
- [ ] `pytest`, `ruff check`, Android unit tests and `assembleRelease` pass
- [ ] `versionCode` was increased
- [ ] APK signature and SHA-256 were checked
- [ ] README and `docs/` match the shipped behavior
