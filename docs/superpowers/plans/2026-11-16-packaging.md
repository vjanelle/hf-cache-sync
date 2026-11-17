# Distribution packaging plan

Build the existing standalone executable on each target platform. Package Linux builds as Debian and AppImage artifacts, and build an MSI using WiX on Windows. Add Make targets for installation and Linux packages, a Windows packaging script, and a CI workflow to build and test artifacts on their native platforms. Verify package contents and runnable commands, and retain the existing coverage gate. Builds require locally installed packaging tools; no publishing is implied.
