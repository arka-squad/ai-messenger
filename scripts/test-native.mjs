import { spawnSync } from 'node:child_process';

const result = spawnSync('cargo', ['test', '--manifest-path', 'src-tauri/Cargo.toml', ...process.argv.slice(2)], {
  env: { ...process.env, SURREAL_SYNC_DATA: 'true' },
  stdio: 'inherit',
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
