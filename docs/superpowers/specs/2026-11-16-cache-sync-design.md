# Hugging Face cache synchronization

## Goal
Pull or push a selected model or all cached models between a local Hub cache and a CIFS-mounted Hub cache, preserving usable cache layouts and existing revisions. This operates on downloaded cache data, not working trees or Hub uploads.

## Approaches
- **Selected: Python cache-aware utility.** Understand repository layouts and shared blobs so selected models remain usable. Python matches the main upstream client.
- **rsync wrapper:** convenient for file copying but requires comparable cache-specific logic for shared blobs and ref conflicts.

## Behavior
Accept local and remote Hub cache paths, a model ID or an explicit all-models selection, and a push or pull direction. All-models mode discovers model repositories in the source cache; datasets and Spaces are outside scope. Merge model snapshots, blobs, refs and cached absence markers without deleting destination data. Preserve symbolic links and their required in-cache targets, including shared blobs. Copy regular files and preserve relevant metadata where supported. Reject unsafe links escaping the cache and report missing targets. Skip incomplete download files and locks. Detect differing refs across the entire selection before changing anything; by default stop and report conflicts, with an explicit source-wins option. Identical existing files can be reused; conflicting immutable content must produce an error rather than overwrite it. Copy via temporary files and atomic rename where supported, and report errors clearly. Provide a dry run and progress summary.

CIFS must support the symlinks required by the source layout; detect failures and explain the mount limitation. Do not sync the separate Xet transfer cache: model data resides in the Hub cache, including any shared blob store. Preserve shared-store metadata as needed without overwriting metadata belonging to other models.

## Remote pruning
Provide an explicit command to remove selected model repositories from the remote cache, independent of local cache contents. Support dry run and show what would be removed. Preserve shared blobs still referenced by other repositories; if their ownership cannot be established safely, leave them in place. Never infer remote deletion from local absence.

## Verification
Exercise single-model and all-model push and pull with temporary cache fixtures covering multiple revisions, shared blobs, symlinks, conflicts, incomplete files, dry run, and missing or unsafe targets, plus remote pruning with shared and uncertain blob ownership. Document usage and CIFS requirements.
