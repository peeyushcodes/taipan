"""
Taipan Package Manager — tpkg (v2)
====================================
Real package manager for Taipan with local registry support.

Commands:
  tpkg init                  Initialize a new Taipan package in current directory
  tpkg install <package>     Install a package from registry
  tpkg uninstall <package>   Remove an installed package
  tpkg list                  List installed packages
  tpkg search <query>        Search local registry
  tpkg info <package>        Show package information
  tpkg publish               Publish current package to local registry
  tpkg update                Update all packages
  tpkg build                 Build current package (verify syntax)

Registry:
  ~/.taipan/registry/       Local package registry
  ~/.taipan/packages/       Installed packages cache
"""

import sys
import os
import json
import shutil
import zipfile
import hashlib
from pathlib import Path
from datetime import datetime


# ── Constants ─────────────────────────────────────────────────────────────────
TAIPAN_HOME    = Path.home() / ".taipan"
REGISTRY_DIR    = TAIPAN_HOME / "registry"      # Published packages
INSTALLED_DIR   = TAIPAN_HOME / "packages"     # Installed packages
PEEK_META       = TAIPAN_HOME / "peek_meta.json"

BUILTIN_PKGS = {
    "math", "string", "file", "json", "time",
    "collections", "network", "ai",
}

COLORS = {
    "reset":  "\033[0m",
    "bold":   "\033[1m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "blue":   "\033[94m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "purple": "\033[95m",
    "gray":   "\033[90m",
}


def c(color: str, text: str) -> str:
    """Colorize text for terminal output."""
    if sys.platform == "win32":
        os.system("")
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def _ensure_dirs():
    """Ensure all needed directories exist."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    INSTALLED_DIR.mkdir(parents=True, exist_ok=True)


def _load_meta() -> dict:
    """Load tpkg metadata."""
    _ensure_dirs()
    if PEEK_META.exists():
        try:
            return json.loads(PEEK_META.read_text(encoding="utf-8"))
        except Exception:
            return {"installed": {}, "sources": {}}
    return {"installed": {}, "sources": {}}


def _save_meta(meta: dict):
    """Save tpkg metadata."""
    _ensure_dirs()
    PEEK_META.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def _banner():
    print(c("purple", """
  =========================================
     Taipan Package Manager (tpkg) v2.0
  =========================================
"""))


def _load_manifest(dir_path: Path) -> dict:
    """Load a Taipan package manifest from a directory."""
    manifest_file = dir_path / "taipan.toml"
    if manifest_file.exists():
        try:
            import tomllib
            return tomllib.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback to JSON manifest
    manifest_file = dir_path / "manifest.json"
    if manifest_file.exists():
        try:
            return json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_manifest(dir_path: Path, manifest: dict):
    """Save a Taipan package manifest."""
    manifest_file = dir_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _find_pkg_versions(pkg_name: str) -> list[str]:
    """Find all published versions of a package in the registry."""
    pkg_dir = REGISTRY_DIR / pkg_name
    if not pkg_dir.exists():
        return []
    versions = []
    for vdir in pkg_dir.iterdir():
        if vdir.is_dir():
            versions.append(vdir.name)
    return sorted(versions, key=lambda v: [int(x) for x in v.split(".")])


def _latest_version(pkg_name: str) -> str | None:
    """Get the latest version of a package."""
    versions = _find_pkg_versions(pkg_name)
    return versions[-1] if versions else None


def _pkg_manifest(pkg_name: str, version: str) -> dict:
    """Get manifest for a specific package version."""
    pkg_dir = REGISTRY_DIR / pkg_name / version
    return _load_manifest(pkg_dir)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_init(project_name: str | None = None):
    """Initialize a new Taipan package in a directory."""
    if project_name:
        cwd = Path.cwd() / project_name
        cwd.mkdir(exist_ok=True)
    else:
        cwd = Path.cwd()
    
    # Check if already initialized
    if (cwd / "taipan.toml").exists():
        print(c("yellow", f"⚠ A Taipan package already exists in {cwd}."))
        return 1
    
    pkg_name = project_name or cwd.name
    
    # Create taipan.toml
    toml_content = f'''[package]
name = "{pkg_name}"
version = "0.1.0"
description = "A Taipan package"
author = "Your Name"
license = "MIT"

[dependencies]
# Add dependencies here: other_pkg = "1.0.0"
'''
    (cwd / "taipan.toml").write_text(toml_content, encoding="utf-8")
    
    # Create src directory
    src_dir = cwd / "src"
    src_dir.mkdir(exist_ok=True)
    
    # Create main.pk
    main_pk = src_dir / "main.tp"
    main_pk.write_text('''// Main entry point for ''' + pkg_name + '''

func greet(name: String) -> String {
    return f"Hello, {name}!"
}

show(greet("Taipan"))
''', encoding="utf-8")
    
    # Create tests directory
    tests_dir = cwd / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_main.tp").write_text('''test "greet works" {
    let result = greet("World")
    assert(result == "Hello, World!")
}
''', encoding="utf-8")
    
    # Create README.md
    readme = cwd / "README.md"
    readme.write_text(f'''# {pkg_name}

A Taipan package.

## Installation

```bash
tpkg install {pkg_name}
```

## Usage

```pk
import {pkg_name}
show({pkg_name}.greet("World"))
```

## Development

```bash
tai test tests/
tai check src/
```
''', encoding="utf-8")
    
    # Create .gitignore
    gitignore = cwd / ".gitignore"
    gitignore.write_text('''# Taipan build artifacts
*.c
*.exe
*.o
*.so
*.dll

# Taipan package cache
.taipan/
''', encoding="utf-8")
    
    print(c("green", f"✓ Initialized Taipan package '{pkg_name}' in {cwd}"))
    print()
    print(c("cyan", "  Files created:"))
    print(f"    taipan.toml     - Package manifest")
    print(f"    src/main.pk      - Entry point")
    print(f"    tests/           - Test files")
    print(f"    README.md        - Package documentation")
    print(f"    .gitignore       - Git ignore rules")
    print()
    print(c("gray", "  Run 'tai test' to run tests, 'tpkg publish' to publish."))
    return 0


def cmd_install(packages: list[str]):
    """Install packages from the local registry."""
    if not packages:
        print(c("red", "Error: specify at least one package name."))
        print("  Usage: tpkg install <package>[@version]")
        return 1
    
    meta = _load_meta()
    installed = meta.get("installed", {})
    
    for spec in packages:
        # Parse package[@version]
        if "@" in spec:
            pkg_name, version = spec.split("@", 1)
        else:
            pkg_name = spec
            version = _latest_version(pkg_name)
        
        if pkg_name in BUILTIN_PKGS:
            print(c("green", f"✓ '{pkg_name}' is a built-in Taipan module — always available!"))
            continue
        
        if not version:
            print(c("red", f"✗ Package '{pkg_name}' not found in registry."))
            print(c("gray", f"  Run 'tpkg publish' to publish it, or check the package name."))
            continue
        
        pkg_dir = REGISTRY_DIR / pkg_name / version
        if not pkg_dir.exists():
            print(c("red", f"✗ Package '{pkg_name}@{version}' not found in registry."))
            continue
        
        # Read manifest
        manifest = _pkg_manifest(pkg_name, version)
        print(c("blue", f"→ Installing '{pkg_name}' v{version}..."))
        
        # Copy to installed directory
        install_dir = INSTALLED_DIR / pkg_name
        if install_dir.exists():
            shutil.rmtree(install_dir)
        shutil.copytree(pkg_dir, install_dir)
        
        # Update metadata
        installed[pkg_name] = {
            "version": version,
            "installed_at": datetime.now().isoformat(),
            "description": manifest.get("package", {}).get("description", ""),
        }
        
        print(c("green", f"  ✓ Installed '{pkg_name}' v{version}"))
    
    meta["installed"] = installed
    _save_meta(meta)
    return 0


def cmd_uninstall(packages: list[str]):
    """Remove installed packages."""
    if not packages:
        print(c("red", "Error: specify at least one package name."))
        print("  Usage: tpkg uninstall <package>")
        return 1
    
    meta = _load_meta()
    installed = meta.get("installed", {})
    
    for pkg in packages:
        if pkg in BUILTIN_PKGS:
            print(c("yellow", f"⚠ '{pkg}' is a built-in module — cannot uninstall."))
            continue
        
        install_dir = INSTALLED_DIR / pkg
        if install_dir.exists():
            shutil.rmtree(install_dir)
        
        if pkg in installed:
            del installed[pkg]
            print(c("green", f"✓ Uninstalled '{pkg}'"))
        else:
            print(c("yellow", f"⚠ '{pkg}' was not installed."))
    
    meta["installed"] = installed
    _save_meta(meta)
    return 0


def cmd_list():
    """List all installed and built-in packages."""
    print(c("bold", "\nBuilt-in Modules (always available):"))
    for pkg in sorted(BUILTIN_PKGS):
        print(f"  {c('green', '*')} {pkg}")
    
    meta = _load_meta()
    installed = meta.get("installed", {})
    if installed:
        print(c("bold", "\nInstalled Packages:"))
        for pkg, info in sorted(installed.items()):
            ver = info.get("version", "?")
            desc = info.get("description", "")
            print(f"  {c('cyan', '*')} {pkg:<20} v{ver}")
            if desc:
                print(f"    {c('gray', desc)}")
    else:
        print(c("gray", "\nNo user-installed packages."))
    
    # Also show registry packages
    registry_pkgs = []
    if REGISTRY_DIR.exists():
        for pkg_dir in REGISTRY_DIR.iterdir():
            if pkg_dir.is_dir():
                latest = _latest_version(pkg_dir.name)
                registry_pkgs.append((pkg_dir.name, latest))
    
    if registry_pkgs:
        print(c("bold", "\nAvailable in Registry:"))
        for pkg, ver in sorted(registry_pkgs):
            installed_ver = installed.get(pkg, {}).get("version")
            status = c("green", "[installed]") if installed_ver == ver else ""
            print(f"  {c('purple', '*')} {pkg:<20} v{ver}  {status}")
    
    print()
    return 0


def cmd_search(query: str):
    """Search the local registry for packages."""
    if not query:
        print(c("red", "Error: specify a search query."))
        print("  Usage: tpkg search <query>")
        return 1
    
    query_lower = query.lower()
    matches = []
    
    if REGISTRY_DIR.exists():
        for pkg_dir in REGISTRY_DIR.iterdir():
            if pkg_dir.is_dir():
                pkg_name = pkg_dir.name
                latest = _latest_version(pkg_name)
                manifest = _pkg_manifest(pkg_name, latest) if latest else {}
                desc = manifest.get("package", {}).get("description", "")
                
                if query_lower in pkg_name.lower() or query_lower in desc.lower():
                    matches.append((pkg_name, latest, desc))
    
    if matches:
        print(c("bold", f"\nSearch results for '{query}':"))
        for pkg, ver, desc in matches:
            print(f"  {c('cyan', pkg)}@{ver}")
            if desc:
                print(f"    {c('gray', desc)}")
    else:
        print(c("yellow", f"\nNo packages found matching '{query}'."))
    print()
    return 0


def cmd_info(package: str):
    """Show information about a package."""
    if not package:
        print(c("red", "Error: specify a package name."))
        print("  Usage: tpkg info <package>")
        return 1
    
    if package in BUILTIN_PKGS:
        print(c("cyan", f"\n{package}"))
        print(c("gray", "  Built-in Taipan standard library module."))
        print()
        return 0
    
    # Check installed
    meta = _load_meta()
    installed = meta.get("installed", {})
    
    if package in installed:
        info = installed[package]
        print(c("cyan", f"\n{package} (installed)"))
        print(f"  Version: {info.get('version', '?')}")
        print(f"  Installed: {info.get('installed_at', 'unknown')}")
        if info.get('description'):
            print(f"  Description: {info['description']}")
    
    # Check registry
    versions = _find_pkg_versions(package)
    if versions:
        print(c("cyan", f"\n{package} (registry)"))
        print(f"  Versions: {', '.join(versions)}")
        latest_manifest = _pkg_manifest(package, versions[-1])
        pkg_info = latest_manifest.get("package", {})
        if pkg_info.get("description"):
            print(f"  Description: {pkg_info['description']}")
        if pkg_info.get("author"):
            print(f"  Author: {pkg_info['author']}")
        if pkg_info.get("license"):
            print(f"  License: {pkg_info['license']}")
    elif package not in installed:
        print(c("red", f"\nPackage '{package}' not found."))
    
    print()
    return 0


def cmd_publish():
    """Publish the current package to the local registry."""
    cwd = Path.cwd()
    manifest = _load_manifest(cwd)
    
    if not manifest:
        print(c("red", "Error: No 'taipan.toml' or 'manifest.json' found in current directory."))
        print(c("gray", "  Run 'tpkg init' to create a new package."))
        return 1
    
    pkg_info = manifest.get("package", manifest)  # Support both toml and json structure
    pkg_name = pkg_info.get("name")
    version = pkg_info.get("version")
    
    if not pkg_name or not version:
        print(c("red", "Error: Package manifest must have 'name' and 'version' fields."))
        return 1
    
    # Check if src directory exists
    src_dir = cwd / "src"
    if not src_dir.exists():
        print(c("yellow", "⚠ No 'src/' directory found. Including all .pk files from current directory."))
        src_dir = cwd
    
    # Create registry entry
    pkg_registry_dir = REGISTRY_DIR / pkg_name / version
    pkg_registry_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy manifest
    _save_manifest(pkg_registry_dir, manifest)
    
    # Copy source files
    src_out = pkg_registry_dir / "src"
    if src_out.exists():
        shutil.rmtree(src_out)
    
    # Copy all .pk files
    pk_files = list(src_dir.rglob("*.tp"))
    if pk_files:
        shutil.copytree(src_dir, src_out)
    else:
        src_out.mkdir(exist_ok=True)
        # Copy any .pk files from cwd
        for pk_file in cwd.rglob("*.tp"):
            if pk_file.name != "main.tp":
                continue
            rel = pk_file.relative_to(cwd)
            dest = src_out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pk_file, dest)
    
    # Also copy tests if they exist
    tests_dir = cwd / "tests"
    if tests_dir.exists():
        tests_out = pkg_registry_dir / "tests"
        if tests_out.exists():
            shutil.rmtree(tests_out)
        shutil.copytree(tests_dir, tests_out)
    
    print(c("green", f"✓ Published '{pkg_name}' v{version} to local registry."))
    print(c("gray", f"  Registry path: {pkg_registry_dir}"))
    print(c("gray", f"  Install with: tpkg install {pkg_name}@{version}"))
    return 0


def cmd_update():
    """Update all installed packages to latest versions."""
    meta = _load_meta()
    installed = meta.get("installed", {})
    
    if not installed:
        print(c("gray", "No packages installed."))
        return 0
    
    updated = 0
    for pkg in list(installed.keys()):
        current_ver = installed[pkg].get("version", "0.0.0")
        latest = _latest_version(pkg)
        
        if latest and latest != current_ver:
            print(c("blue", f"→ Updating '{pkg}' from v{current_ver} to v{latest}..."))
            cmd_install([f"{pkg}@{latest}"])
            updated += 1
        else:
            print(c("gray", f"  {pkg} v{current_ver} is up to date."))
    
    if updated:
        print(c("green", f"\n✓ Updated {updated} package(s)."))
    else:
        print(c("green", "\n✓ All packages are up to date."))
    return 0


def cmd_build():
    """Build/verify the current package."""
    cwd = Path.cwd()
    manifest = _load_manifest(cwd)
    
    if not manifest:
        print(c("red", "Error: No 'taipan.toml' found in current directory."))
        return 1
    
    pkg_name = manifest.get("package", {}).get("name", "unknown")
    print(c("blue", f"→ Building '{pkg_name}'..."))
    
    # Find all .pk files
    src_dir = cwd / "src"
    if not src_dir.exists():
        src_dir = cwd
    
    pk_files = list(src_dir.rglob("*.tp"))
    if not pk_files:
        print(c("yellow", "⚠ No .pk files found."))
        return 1
    
    errors = 0
    for pk_file in pk_files:
        try:
            # Try to lex and parse
            from taipan.compiler.lexer.lexer import Lexer
            from taipan.compiler.parser.parser import Parser
            source = pk_file.read_text(encoding="utf-8")
            tokens = Lexer(source, str(pk_file)).tokenize()
            Parser(tokens, str(pk_file)).parse()
            print(c("green", f"  ✓ {pk_file}"))
        except Exception as e:
            print(c("red", f"  ✗ {pk_file}: {e}"))
            errors += 1
    
    if errors:
        print(c("red", f"\n✗ Build failed with {errors} error(s)."))
        return 1
    else:
        print(c("green", f"\n✓ Build successful: {len(pk_files)} file(s) verified."))
        return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    
    if not args or args[0] in ("help", "--help", "-h"):
        _banner()
        print("Usage: tpkg <command> [arguments]")
        print()
        print("Commands:")
        print(f"  {c('cyan', 'init')}                    Initialize a new Taipan package")
        print(f"  {c('cyan', 'install')}   <package>[@v]   Install a package from registry")
        print(f"  {c('cyan', 'uninstall')} <package>       Remove an installed package")
        print(f"  {c('cyan', 'list')}                     List all packages")
        print(f"  {c('cyan', 'search')}   <query>         Search local registry")
        print(f"  {c('cyan', 'info')}      <package>       Show package information")
        print(f"  {c('cyan', 'publish')}                  Publish current package to registry")
        print(f"  {c('cyan', 'update')}                   Update all packages")
        print(f"  {c('cyan', 'build')}                    Verify/build current package")
        print()
        print(f"Registry: {REGISTRY_DIR}")
        print(f"Packages: {INSTALLED_DIR}")
        return 0
    
    cmd = args[0].lower()
    rest = args[1:]
    
    match cmd:
        case "init":
            return cmd_init(rest[0] if rest else None)
        case "install":
            return cmd_install(rest)
        case "uninstall" | "remove":
            return cmd_uninstall(rest)
        case "list" | "ls":
            return cmd_list()
        case "search" | "find":
            return cmd_search(rest[0] if rest else "")
        case "info" | "show":
            return cmd_info(rest[0] if rest else "")
        case "publish":
            return cmd_publish()
        case "update" | "upgrade":
            return cmd_update()
        case "build" | "verify":
            return cmd_build()
        case _:
            print(c("red", f"Unknown command: '{cmd}'"))
            print("Run 'tpkg help' for usage.")
            return 1


if __name__ == "__main__":
    sys.exit(main())
