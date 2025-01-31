import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { CLIENT_VERSION } from '../src/version';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const pkg = JSON.parse(readFileSync(resolve(__dirname, '../package.json'), 'utf8'));

if (pkg.version !== CLIENT_VERSION) {
    console.error(`Version mismatch: package.json (${pkg.version}) != version.ts (${CLIENT_VERSION})`);
    process.exit(1);
}

console.log('Version sync check passed!');
