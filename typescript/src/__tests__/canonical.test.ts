// typescript/src/__tests__/canonical.test.ts

import { describe, it, expect, beforeEach } from '@jest/globals';
import { CanonicalStoreClient } from '../canonical';
import { LabelNames } from '../types';
import fetchMock from 'jest-fetch-mock';

// Create a test version by extending and adding protected methods for exposure
class TestCanonicalStoreClient extends CanonicalStoreClient {
  // Override fetchFromGitHub to make it accessible
  public testFetchFromGitHub<T>(path: string, options?: RequestInit & { params?: Record<string, string> }): Promise<T> {
    return this.fetchFromGitHub<T>(path, options);
  }
  
  // We need to recreate these protected methods for testing
  public testExtractObjectIdFromLabels(issue: { labels: Array<{ name: string }> }): string {
    return this._extractObjectIdFromLabels(issue);
  }
}

describe('CanonicalStoreClient', () => {
  const token = 'test-token';
  const repo = 'owner/repo';
  let client: TestCanonicalStoreClient;

  beforeEach(() => {
    fetchMock.resetMocks();
    // Create the client without passing cache - it's not in CanonicalStoreConfig
    client = new TestCanonicalStoreClient(token, repo);
  });

  describe('resolveCanonicalObjectId', () => {
    it('should resolve direct object ID', async () => {
      // Mock to find the object directly (not an alias)
      fetchMock.mockResponseOnce(JSON.stringify([])); // No issues with alias labels

      const result = await client.resolveCanonicalObjectId('test-object');
      expect(result).toBe('test-object');
    });

    it('should resolve alias to canonical ID', async () => {
      // Mock to find an issue with alias label
      const mockIssue = {
        number: 123,
        labels: [
          { name: `${LabelNames.UID_PREFIX}test-alias` },
          { name: `${LabelNames.ALIAS_TO_PREFIX}test-canonical` }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify([mockIssue]));

      const result = await client.resolveCanonicalObjectId('test-alias');
      expect(result).toBe('test-canonical');
    });

    it('should follow alias chain but prevent infinite loops', async () => {
      // Mock the first lookup (test-alias-1 -> test-alias-2)
      const mockIssue1 = {
        number: 123,
        labels: [
          { name: `${LabelNames.UID_PREFIX}test-alias-1` },
          { name: `${LabelNames.ALIAS_TO_PREFIX}test-alias-2` }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify([mockIssue1]));

      // Mock the second lookup (test-alias-2 -> test-canonical)
      const mockIssue2 = {
        number: 124,
        labels: [
          { name: `${LabelNames.UID_PREFIX}test-alias-2` },
          { name: `${LabelNames.ALIAS_TO_PREFIX}test-canonical` }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify([mockIssue2]));

      // Mock the last lookup (no more aliases)
      fetchMock.mockResponseOnce(JSON.stringify([]));

      const result = await client.resolveCanonicalObjectId('test-alias-1');
      expect(result).toBe('test-canonical');
    });

    it('should detect and break circular references', async () => {
      // Mock circular references (test-alias-a -> test-alias-b -> test-alias-a)
      const mockIssueA = {
        number: 123,
        labels: [
          { name: `${LabelNames.UID_PREFIX}test-alias-a` },
          { name: `${LabelNames.ALIAS_TO_PREFIX}test-alias-b` }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify([mockIssueA]));

      const mockIssueB = {
        number: 124,
        labels: [
          { name: `${LabelNames.UID_PREFIX}test-alias-b` },
          { name: `${LabelNames.ALIAS_TO_PREFIX}test-alias-a` }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify([mockIssueB]));

      // We should detect the circularity and return test-alias-b (the first level)
      const result = await client.resolveCanonicalObjectId('test-alias-a');
      expect(result).toBe('test-alias-a'); // Return original ID on circular reference
    });
  });

  describe('getObject with canonicalization', () => {
    it('should resolve and use canonical ID by default', async () => {
      // Mock to find the alias
      const mockAliasIssue = {
        number: 123,
        labels: [
          { name: `${LabelNames.UID_PREFIX}test-alias` },
          { name: `${LabelNames.ALIAS_TO_PREFIX}test-canonical` }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify([mockAliasIssue]));

      // Mock for empty response (no more aliases)
      fetchMock.mockResponseOnce(JSON.stringify([]));

      // Mock for finding canonical issue
      const mockCanonicalIssue = {
        number: 456,
        body: JSON.stringify({ value: 42 }),
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}test-canonical` }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify([mockCanonicalIssue]));

      // Mock for comments count
      fetchMock.mockResponseOnce(JSON.stringify([]));

      const result = await client.getObject('test-alias');
      
      expect(result.meta.objectId).toBe('test-canonical');
      expect(result.data).toEqual({ value: 42 });
    });

    it('should get alias directly when canonicalize=false', async () => {
      // Mock for direct lookup with UID label
      const mockIssues = [{
        number: 123,
        body: JSON.stringify({ alias_value: 'direct' }),
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}test-alias` },
          { name: `${LabelNames.ALIAS_TO_PREFIX}test-canonical` }
        ]
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockIssues));

      // Mock for comments count
      fetchMock.mockResponseOnce(JSON.stringify([]));

      const result = await client.getObject('test-alias', { canonicalize: false });
      
      expect(result.meta.objectId).toBe('test-alias');
      expect(result.data).toEqual({ alias_value: 'direct' });
    });
  });

  describe('createAlias', () => {
    it('should create alias relationship between objects', async () => {
      // Mock for source object lookup
      const mockSourceIssues = [{
        number: 123,
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}source-id` }
        ]
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockSourceIssues));

      // Mock for target object lookup
      const mockTargetIssues = [{
        number: 456,
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}target-id` }
        ]
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockTargetIssues));

      // Mock for existing labels check
      fetchMock.mockResponseOnce(JSON.stringify([
        { name: LabelNames.STORED_OBJECT },
        { name: `${LabelNames.UID_PREFIX}source-id` }
      ]));

      // Mock for creating alias label
      fetchMock.mockResponseOnce(JSON.stringify({}));

      // Mock for adding label to issue
      fetchMock.mockResponseOnce(JSON.stringify({}));

      const result = await client.createAlias('source-id', 'target-id');
      
      expect(result.success).toBe(true);
      expect(result.sourceId).toBe('source-id');
      expect(result.targetId).toBe('target-id');

      // Verify correct URL for the label creation
      expect(fetchMock.mock.calls[3][0]).toContain('/labels');
    });

    it('should reject if source is already an alias', async () => {
      // Mock for source object lookup
      const mockSourceIssues = [{
        number: 123,
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}source-id` }
        ]
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockSourceIssues));

      // Mock for target object lookup
      const mockTargetIssues = [{
        number: 456,
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}target-id` }
        ]
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockTargetIssues));

      // Mock for existing labels check - already has an alias
      fetchMock.mockResponseOnce(JSON.stringify([
        { name: LabelNames.STORED_OBJECT },
        { name: `${LabelNames.UID_PREFIX}source-id` },
        { name: `${LabelNames.ALIAS_TO_PREFIX}other-id` }
      ]));

      await expect(client.createAlias('source-id', 'target-id'))
        .rejects
        .toThrow('Object source-id is already an alias');
    });
  });

  describe('findAliases', () => {
    it('should find all aliases in the repository', async () => {
      // Mock for all alias issues
      const mockIssues = [
        {
          labels: [
            { name: `${LabelNames.UID_PREFIX}alias-1` },
            { name: `${LabelNames.ALIAS_TO_PREFIX}canonical-1` }
          ]
        },
        {
          labels: [
            { name: `${LabelNames.UID_PREFIX}alias-2` },
            { name: `${LabelNames.ALIAS_TO_PREFIX}canonical-2` }
          ]
        }
      ];
      fetchMock.mockResponseOnce(JSON.stringify(mockIssues));

      const aliases = await client.findAliases();
      
      // Should find both aliases
      expect(Object.keys(aliases).length).toBe(2);
      expect(aliases['alias-1']).toBe('canonical-1');
      expect(aliases['alias-2']).toBe('canonical-2');
    });

    it('should find aliases for a specific object', async () => {
      // Mock for specific alias issues
      const mockIssues = [
        {
          labels: [
            { name: `${LabelNames.UID_PREFIX}alias-1` },
            { name: `${LabelNames.ALIAS_TO_PREFIX}target-id` }
          ]
        },
        {
          labels: [
            { name: `${LabelNames.UID_PREFIX}alias-2` },
            { name: `${LabelNames.ALIAS_TO_PREFIX}target-id` }
          ]
        }
      ];
      fetchMock.mockResponseOnce(JSON.stringify(mockIssues));

      const aliases = await client.findAliases('target-id');
      
      // Should find both aliases for the target
      expect(Object.keys(aliases).length).toBe(2);
      expect(aliases['alias-1']).toBe('target-id');
      expect(aliases['alias-2']).toBe('target-id');
    });
  });
});
