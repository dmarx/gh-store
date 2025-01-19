// typescript/scripts/test-packaging.js
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, '..');

// Test ESM import
async function testESMImport() {
    try {
        const { GitHubStoreClient } = await import('../dist/index.mjs');
        if (!GitHubStoreClient) {
            throw new Error('GitHubStoreClient not exported from ESM build');
        }
        console.log('✓ ESM import successful');
    } catch (error) {
        console.error('✗ ESM import failed:', error);
        process.exit(1);
    }
}

// Test package.json exports
function testPackageExports() {
    const pkg = JSON.parse(readFileSync(resolve(rootDir, 'package.json'), 'utf8'));
    
    // Check required fields
    const requiredFields = ['exports', 'main', 'module', 'types'];
    for (const field of requiredFields) {
        if (!pkg[field]) {
            console.error(`✗ Missing required field: ${field}`);
            process.exit(1);
        }
    }
    
    // Check exports configuration
    const { exports } = pkg;
    if (!exports['.'].import || !exports['.'].require || !exports['.'].types) {
        console.error('✗ Exports must specify import, require, and types');
        process.exit(1);
    }
    
    console.log('✓ package.json exports verified');
}

// Run tests
async function main() {
    console.log('Testing package configuration...');
    testPackageExports();
    await testESMImport();
    console.log('All packaging tests passed!');
}

main().catch(error => {
    console.error('Test failed:', error);
    process.exit(1);
});
