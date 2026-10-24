# external/

Read-only reference clones. Rules:

- **Read-only**: never modify files inside a clone; upstream stays pristine.
- **Never a dependency**: nothing in the build, tests, or runtime may import or
  link against anything here.
- **Never vendored/copied**: do not copy code out of these clones into the
  repository; link to it instead.
- **Never committed**: everything in this directory is git-ignored except
  `.gitignore` and this `readme.md`.
- Every clone gets an analysis page at `doc/sources/YYYY-MM-DD-<name>-analysis.md`
  and a row in the index below. The table is the manifest that makes a fresh
  checkout reproducible.

Index:

| Directory | Origin URL | Ref (commit/tag) | Cloned | Why | Analysis page |
|-----------|------------|------------------|--------|-----|---------------|
| `microduck` | https://github.com/pollen-robotics/microduck | `942e58e3aa6dbb28e7037203fff11866122c7567` | 2026-10-24 | The robot's onboard software: Rust daemons, 50 Hz control loop, `robotctl`, architecture docs | [2026-10-24-microduck-analysis](../doc/sources/2026-10-24-microduck-analysis.md) |
| `microduck_rl` | https://github.com/pollen-robotics/microduck_rl | `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` | 2026-10-24 | RL training environments (mjlab/MuJoCo + PPO) that produce the ONNX policies | [2026-10-24-microduck-analysis](../doc/sources/2026-10-24-microduck-analysis.md) |
| `microduck_yocto` | https://github.com/pollen-robotics/microduck_yocto | `91691234f3b518a94ee4391f8567c9486335f507` | 2026-10-24 | Microduck OS: Yocto image for the RK3566, A/B update machinery | [2026-10-24-microduck-analysis](../doc/sources/2026-10-24-microduck-analysis.md) |
| `awesome-microduck` | https://github.com/joeynyc/awesome-microduck | `fcd4948df147e9d353feb78cde4a6de4f19a4676` | 2026-10-24 | Community index of the whole ecosystem: spec summary, projects, coverage | [2026-10-24-microduck-analysis](../doc/sources/2026-10-24-microduck-analysis.md) |
| `IsaacLab` | https://github.com/isaac-sim/IsaacLab | `88f48962e53c003b6eb331d8e70c76515ba724a1` | 2026-10-24 | NVIDIA Isaac Lab 3.0; Microduck training tasks under `source/isaaclab_tasks/isaaclab_tasks/contrib/microduck/` | [2026-10-24-microduck-analysis](../doc/sources/2026-10-24-microduck-analysis.md) |
| `BrickPi` | https://github.com/DexterInd/BrickPi | `0f4b64c03d734f31e07d4d462cc5347ed2fea54a` | 2026-10-24 | BrickPi+ mega-repo: BrickPi.py protocol source of truth, BrickPi_C, firmware; UART protocol facts | [2026-10-24-hardware-libs-capture](../doc/sources/2026-10-24-hardware-libs-capture.md) |
| `BrickPi_Python` | https://github.com/DexterInd/BrickPi_Python | `ff5706c4a07fc661bc29eb485ee6481ec567163a` | 2026-10-24 | Separate (stale) home of the Python lib, for cross-reference | [2026-10-24-hardware-libs-capture](../doc/sources/2026-10-24-hardware-libs-capture.md) |
| `BrickPi_C` | https://github.com/DexterInd/BrickPi_C | `a314daf50d43a156fb18927c31fc392d053bacdc` | 2026-10-24 | README-only stub; kept to confirm the C lib lives in the mega-repo | [2026-10-24-hardware-libs-capture](../doc/sources/2026-10-24-hardware-libs-capture.md) |
| `libfreenect` | https://github.com/OpenKinect/libfreenect | `09a1f098040d00e6070c18174904547ec31d2774` | 2026-10-24 | Kinect v1 driver (C API + python wrapper) used by v1; source for v2 FFI | [2026-10-24-hardware-libs-capture](../doc/sources/2026-10-24-hardware-libs-capture.md) |
| `libfreenect-sys` | https://github.com/xanium4332/libfreenect-sys | `21bdc41fe09b20ec0388ad76b1dca30e434ef6ad` | 2026-10-24 | Raw Rust bindings to libfreenect (2015, needs regen) — v2 `camerad` starting point | [2026-10-24-hardware-libs-capture](../doc/sources/2026-10-24-hardware-libs-capture.md) |
| `libfreenect-rs` | https://github.com/xanium4332/libfreenect-rs | `a5c0eb9f577b2e6392e882cf351db8bcf81f0a63` | 2026-10-24 | Safe Rust wrapper over libfreenect (same author) | [2026-10-24-hardware-libs-capture](../doc/sources/2026-10-24-hardware-libs-capture.md) |
| `rust-i2cdev` | https://github.com/rust-embedded/rust-i2cdev | `39f419b06afcda15ab1a540737175297c4fe2202` | 2026-10-24 | Maintained Linux I2C userspace crate (future peripherals) | [2026-10-24-hardware-libs-capture](../doc/sources/2026-10-24-hardware-libs-capture.md) |
| `serialport-rs` | https://github.com/serialport/serialport-rs | `cb9822a9956f2f828537c33db8604267ab2354df` | 2026-10-24 | The v2 `motord` transport crate (BrickPi UART protocol) | [2026-10-24-hardware-libs-capture](../doc/sources/2026-10-24-hardware-libs-capture.md) |
