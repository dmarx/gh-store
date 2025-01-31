// typescript/scripts/update-version.ts
import { readFileSync, writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Read package.json
const pkgPath = resolve(__dirname, '../package.json');
const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));

// Read version.ts
const versionPath = resolve(__dirname, '../src/version.ts');
const versionContent = readFileSync(versionPath, 'utf8');

// Update version
const updatedContent = versionContent.replace(
  /export const CLIENT_VERSION = '.*'/,
  `export const CLIENT_VERSION = '${pkg.version}'`
);

// Write back
writeFileSync(versionPath, updatedContent);

console.log(`Updated CLIENT_VERSION to ${pkg.version}`);
