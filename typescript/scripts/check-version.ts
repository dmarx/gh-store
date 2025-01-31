import { readFileSync } from 'fs';
import { resolve } from 'path';
import { CLIENT_VERSION } from '../src/version';

const pkg = JSON.parse(readFileSync(resolve(__dirname, '../package.json'), 'utf8'));

if (pkg.version !== CLIENT_VERSION) {
    console.error(`Version mismatch: package.json (${pkg.version}) != version.ts (${CLIENT_VERSION})`);
    process.exit(1);
}

console.log('Version sync check passed!');
