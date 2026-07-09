# History

## 2026-07-09: Harden GitHub Pages Autonomous Deployment

- Updated GitHub-maintained workflow actions to current major versions after a Pages deployment failed under older action runtimes.
- Collapsed the Pages artifact build and deployment into a single workflow job so a deploy does not need a second hosted-runner allocation after the artifact has already been uploaded.
- Added a daily scheduled Pages deployment repair run so transient GitHub Pages or Actions failures can self-heal without a manual rerun.
