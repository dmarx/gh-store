// typescript/src/__tests__/canonical.test.ts - Updated test class and config

import { describe, it, expect, beforeEach } from '@jest/globals';
import { CanonicalStoreClient, LabelNames, DeprecationReason } from '../canonical';
import fetchMock from 'jest-fetch-mock';

// Create a test version by extending and adding protected methods for exposure
class TestCanonicalStoreClient extends CanonicalStoreClient {
  // Override fetchFromGitHub to make it accessible
  public testFetchFromGitHub<T>(path: string, options?: RequestInit & { params?: Record<string, string> }): Promise<T> {
    return this.fetchFromGitHub<T>(path, options);
  }
  
  // We need to recreate these private methods for testing
  public testExtractObjectIdFromLabels(issue: { labels: Array<{ name: string }> }): string {
    for (const label of issue.labels) {
      if (label.name.startsWith(LabelNames.UID_PREFIX)) {
        return label.name.slice(LabelNames.UID_PREFIX.length);
      }
    }
    
    throw new Error(`No UID label found with prefix ${LabelNames.UID_PREFIX}`);
  }
  
  // Create a public method for testing deep merge
  public testDeepMerge<T, U>(base: T, update: U): T & U {
    // Call the private method using 'any' to bypass TypeScript access checks
    // This is only for testing and won't appear in production code
    return (this as any)._deepMerge(base, update);
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
      expect(result).toBe('test-alias-b');
    });
  });

  describe('getObject with canonicalization', () => {
    it('should resolve and process virtual merge by default', async () => {
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
        labels: [
          { name: `${LabelNames.UID_PREFIX}test-canonical` },
          { name: LabelNames.STORED_OBJECT }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify([mockCanonicalIssue]));

      // Mock for canonical issue comments
      const mockComments = [{
        id: 1,
        created_at: '2025-01-01T00:00:00Z',
        body: JSON.stringify({
          type: 'initial_state',
          _data: { value: 42 },
          _meta: {
            client_version: '0.3.1',
            timestamp: '2025-01-01T00:00:00Z',
            update_mode: 'append'
          }
        })
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockComments));

      // Mock for alias issue comments
      fetchMock.mockResponseOnce(JSON.stringify([]));

      // Mock for deprecated issue comments
      fetchMock.mockResponseOnce(JSON.stringify([]));

      // Mock for canonical issue lookup again (for metadata)
      fetchMock.mockResponseOnce(JSON.stringify([mockCanonicalIssue]));

      // Mock for direct issue fetch for metadata
      const mockIssueData = {
        number: 456,
        body: JSON.stringify({ value: 42 }),
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}test-canonical` }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify(mockIssueData));

      // Mock for updating issue body
      fetchMock.mockResponseOnce(JSON.stringify({}));

      // Mock for comments count
      fetchMock.mockResponseOnce(JSON.stringify(mockComments));

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

      // Verify the alias label was created with proper format
      const createLabelCall = JSON.parse(fetchMock.mock.calls[3][1]?.body as string);
      expect(createLabelCall.name).toBe(`${LabelNames.ALIAS_TO_PREFIX}target-id`);
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

  describe('deprecateObject', () => {
    it('should deprecate an object by marking it and creating relationships', async () => {
      // Mock for source object lookup
      const mockSourceIssues = [{
        number: 123,
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}old-id` }
        ]
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockSourceIssues));

      // Mock for target object lookup
      const mockTargetIssues = [{
        number: 456,
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}canonical-id` }
        ]
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockTargetIssues));

      // Mock for removing stored-object label
      fetchMock.mockResponseOnce(JSON.stringify({}));

      // Mock for creating merge label
      fetchMock.mockResponseOnce(JSON.stringify({}));

      // Mock for creating deprecated-by label
      fetchMock.mockResponseOnce(JSON.stringify({}));

      // Mock for creating deprecated label
      fetchMock.mockResponseOnce(JSON.stringify({}));

      // Mock for adding labels to issue
      fetchMock.mockResponseOnce(JSON.stringify({}));

      const result = await client.deprecateObject('old-id', 'canonical-id', DeprecationReason.MERGED);
      
      expect(result.success).toBe(true);
      expect(result.sourceObjectId).toBe('old-id');
      expect(result.targetObjectId).toBe('canonical-id');
      expect(result.reason).toBe(DeprecationReason.MERGED);

      // Verify the deprecated label was added
      const addLabelsCall = JSON.parse(fetchMock.mock.calls[6][1]?.body as string);
      expect(addLabelsCall.labels).toContain(LabelNames.DEPRECATED);
      expect(addLabelsCall.labels).toContain(`${LabelNames.MERGED_INTO_PREFIX}canonical-id`);
    });

    it('should reject if trying to deprecate an object as itself', async () => {
      // Mock for source object lookup - same object ID and issue
      const mockSourceIssues = [{
        number: 123,
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}same-id` }
        ]
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockSourceIssues));

      // Mock for target object lookup - same object
      fetchMock.mockResponseOnce(JSON.stringify(mockSourceIssues));

      await expect(client.deprecateObject('same-id', 'same-id'))
        .rejects
        .toThrow('Cannot deprecate an object as itself');
    });
  });

  describe('find methods', () => {
    it('should find duplicates in the repository', async () => {
      // Mock for all stored objects
      const mockIssues = [
        {
          number: 123,
          labels: [
            { name: LabelNames.STORED_OBJECT },
            { name: `${LabelNames.UID_PREFIX}unique-id` }
          ]
        },
        {
          number: 124,
          labels: [
            { name: LabelNames.STORED_OBJECT },
            { name: `${LabelNames.UID_PREFIX}duplicate-id` }
          ]
        },
        {
          number: 125,
          labels: [
            { name: LabelNames.STORED_OBJECT },
            { name: `${LabelNames.UID_PREFIX}duplicate-id` }
          ]
        }
      ];
      fetchMock.mockResponseOnce(JSON.stringify(mockIssues));

      const duplicates = await client.findDuplicates();
      
      // Should find one duplicate set
      expect(Object.keys(duplicates).length).toBe(1);
      expect(duplicates[`${LabelNames.UID_PREFIX}duplicate-id`].length).toBe(2);
    });

    it('should find aliases in the repository', async () => {
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

  describe('Virtual merging', () => {
    it('should combine data from canonical and alias objects', async () => {
      // Mock for canonical issue
      const mockCanonicalIssue = {
        number: 456,
        labels: [
          { name: `${LabelNames.UID_PREFIX}test-canonical` },
          { name: LabelNames.STORED_OBJECT }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify([mockCanonicalIssue]));

      // Mock for canonical issue comments - initial state
      const canonicalComments = [{
        id: 1,
        created_at: '2025-01-01T00:00:00Z',
        body: JSON.stringify({
          type: 'initial_state',
          _data: { count: 42 },
          _meta: {
            client_version: '0.3.1',
            timestamp: '2025-01-01T00:00:00Z',
            update_mode: 'append'
          }
        })
      }];
      fetchMock.mockResponseOnce(JSON.stringify(canonicalComments));

      // Mock for alias lookup
      const mockAliasIssues = [{
        number: 123,
        labels: [
          { name: `${LabelNames.UID_PREFIX}test-alias` },
          { name: `${LabelNames.ALIAS_TO_PREFIX}test-canonical` }
        ]
      }];
      fetchMock.mockResponseOnce(JSON.stringify(mockAliasIssues));

      // Mock for alias comments - has additional data
      const aliasComments = [{
        id: 2,
        created_at: '2025-01-02T00:00:00Z',
        body: JSON.stringify({
          _data: { period: 'daily' },
          _meta: {
            client_version: '0.3.1',
            timestamp: '2025-01-02T00:00:00Z',
            update_mode: 'append'
          }
        })
      }];
      fetchMock.mockResponseOnce(JSON.stringify(aliasComments));

      // Mock for deprecated lookup
      fetchMock.mockResponseOnce(JSON.stringify([]));

      // Mock for canonical issue lookup (metadata)
      fetchMock.mockResponseOnce(JSON.stringify([mockCanonicalIssue]));

      // Mock direct issue info
      const mockIssueData = {
        number: 456,
        body: JSON.stringify({ count: 42 }),
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        labels: [
          { name: LabelNames.STORED_OBJECT },
          { name: `${LabelNames.UID_PREFIX}test-canonical` }
        ]
      };
      fetchMock.mockResponseOnce(JSON.stringify(mockIssueData));

      // Mock for updating issue body
      fetchMock.mockResponseOnce(JSON.stringify({}));

      // Mock for comments count
      fetchMock.mockResponseOnce(JSON.stringify([...canonicalComments, ...aliasComments]));

      const result = await client.processWithVirtualMerge('test-canonical');
      
      // Should have merged the data from both sources
      expect(result.data).toEqual({
        count: 42,
        period: 'daily'
      });
    });
  });

  describe('Deep merge utility', () => {
    // This directly tests the internal _deepMerge method through the test class
    it('should correctly merge objects at multiple levels', () => {
      // Define explicit interfaces for our test objects
      interface BaseType {
        level1: {
          a: number;
          level2: {
            b: number;
            c: number;
          };
        };
        list: number[];
      }
      
      interface UpdateType {
        level1: {
          a: number;
          level2: {
            c: number;
            d: number;
          };
        };
        list: number[];
        new_field: string;
      }
      
      // Create typed test objects
      const base: BaseType = {
        level1: {
          a: 1,
          level2: {
            b: 2,
            c: 3
          }
        },
        list: [1, 2, 3]
      };
      
      const update: UpdateType = {
        level1: {
          a: 10,
          level2: {
            c: 30,
            d: 40
          }
        },
        list: [4, 5, 6],
        new_field: 'value'
      };
      
      // Use the typed deep merge test method
      const result = client.testDeepMerge(base, update);
      
      expect(result).toEqual({
        level1: {
          a: 10,  // Updated
          level2: {
            b: 2,   // Preserved
            c: 30,  // Updated
            d: 40   // Added
          }
        },
        list: [4, 5, 6],  // Replaced
        new_field: 'value'  // Added
      });
    });
  });
});
