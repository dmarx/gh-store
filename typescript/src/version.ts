// typescript/src/version.ts
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

function getVersion(): string {
    try {
        const __dirname = dirname(fileURLToPath(import.meta.url));
        const pkgPath = resolve(__dirname, '../package.json');
        const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
        return pkg.version;
    } catch (error) {
        return '0.2.4'; // Fallback version
    }
}

export const CLIENT_VERSION = getVersion();
