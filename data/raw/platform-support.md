# Platform support

## Qualified native targets

| Target triple | Host use | Native backend | ABI | Object |
|---|---|---|---|---|
| `x86_64-pc-windows-msvc` | native / cross object | Forge or LLVM | Windows x64 | COFF |
| `x86_64-unknown-linux-gnu` | native / cross object | Forge or LLVM | System V AMD64 | ELF64 |
| `aarch64-unknown-linux-gnu` | native / cross object | LLVM | AAPCS64 | ELF64 |
| `arm64-apple-macos` | native / cross object | LLVM | Darwin AArch64 | Mach-O 64 |
