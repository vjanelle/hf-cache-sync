# Cache Sync Implementation Plan

**Goal:** Synchronize selected or all Hugging Face models and prune selected remote models safely.
**Architecture:** A Python CLI plans and validates filesystem operations before applying them. Shared blob targets are copied along with their links; remote pruning conservatively retains shared blobs.
**Tech Stack:** Python, unittest BDD-style scenarios, coverage.py, PyInstaller, Make.
**Spec:** docs/superpowers/specs/2026-11-16-cache-sync-design.md

## Tasks
1. Test and implement model discovery, path and link validation, transfer planning, conflict detection and atomic copying.
2. Test and implement remote model pruning, dry runs and CLI argument handling.
3. Add documentation, Make targets for tests, coverage and a single-file executable; verify coverage and build where dependencies are available.

## Review focus
Missing targets, paths escaping roots, preexisting destination conflicts, shared blobs, incomplete downloads, CIFS symlink failures and concurrent changes must fail safely or be preserved.
