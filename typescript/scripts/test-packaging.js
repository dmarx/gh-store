// typescript/scripts/test-packaging.js
import { readFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, '..');

// Verify dist directory exists
function checkDist() {
    const distDir = resolve(rootDir, 'dist');
    if (!existsSync(distDir)) {
        console.error('✗ dist directory not found - run build first');
        process.exit(1);
    }

    const requiredFiles = ['index.mjs', 'index.cjs', 'index.d.ts'];
    for (const file of requiredFiles) {
        if (!existsSync(resolve(distDir, file))) {
            console.error(`✗ Missing required build output: ${file}`);
            process.exit(1);
        }
    }
    console.log('✓ dist directory contains required files');
}

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

    // Verify paths in exports match files that should exist
    const paths = [
        exports['.'].import,
        exports['.'].require,
        exports['.'].types
    ].map(p => p.replace(/^\.\//, ''));

    for (const path of paths) {
        if (!existsSync(resolve(rootDir, path))) {
            console.error(`✗ Export path does not exist: ${path}`);
            process.exit(1);
        }
    }
    
    console.log('✓ package.json exports verified');
}

// Run tests
async function main() {
    console.log('Testing package configuration...');
    // First verify the build files exist
    checkDist();
    // Then test the configuration and imports
    testPackageExports();
    await testESMImport();
    console.log('All packaging tests passed!');
}

main().catch(error => {
    console.error('Test failed:', error);
    process.exit(1);
});
