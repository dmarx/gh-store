// typescript/src/__tests__/client.test.ts
import { describe, it, expect, beforeEach } from '@jest/globals';
import { GitHubStoreClient } from '../client';
import fetchMock from 'jest-fetch-mock';

describe('GitHubStoreClient', () => {
  const token = 'test-token';
  const repo = 'owner/repo';
  let client: GitHubStoreClient;

  beforeEach(() => {
    fetchMock.resetMocks();
    client = new GitHubStoreClient(token, repo, {
      cache: {
        maxSize: 100,
        ttl: 3600000
      }
    });
  });

  describe('getObject with cache', () => {
    const mockIssue = {
      number: 123,
      body: JSON.stringify({ key: 'value' }),
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-02T00:00:00Z',
      labels: [
        { name: 'stored-object' },
        { name: 'UID:test-object' }
      ]
    };

    it('should use cached issue number on subsequent requests', async () => {
      // First request - should query by labels
      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue])) // Initial labels query
        .mockResponseOnce(JSON.stringify([])); // Comments query for version

      await client.getObject('test-object');
      expect(fetchMock.mock.calls[0][0]).toContain('/issues?labels=');

      // Reset mock to verify cache hit
      fetchMock.resetMocks();
      fetchMock
        .mockResponseOnce(JSON.stringify(mockIssue)) // Direct issue fetch
        .mockResponseOnce(JSON.stringify([])); // Comments query for version

      await client.getObject('test-object');
      
      // Should use direct issue number fetch instead of labels query
      expect(fetchMock.mock.calls[0][0]).toContain('/issues/123');
    });

    it('should fall back to label query if cached issue is not found', async () => {
      // First request succeeds
      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue]))
        .mockResponseOnce(JSON.stringify([]));

      await client.getObject('test-object');

      // Reset mock to simulate deleted issue
      fetchMock.resetMocks();
      fetchMock
        .mockResponseOnce('', { status: 404 }) // Cached issue not found
        .mockResponseOnce(JSON.stringify([mockIssue])) // Fallback label query
        .mockResponseOnce(JSON.stringify([])); // Comments query

      await client.getObject('test-object');

      // Should have attempted direct fetch, then fallen back to labels
      expect(fetchMock.mock.calls[0][0]).toContain('/issues/123');
      expect(fetchMock.mock.calls[1][0]).toContain('/issues?labels=');
    });

    it('should fetch and parse object correctly', async () => {
      const mockComments = [{ id: 1 }, { id: 2 }];

      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue]))
        .mockResponseOnce(JSON.stringify(mockComments));

      const obj = await client.getObject('test-object');

      expect(obj.meta.objectId).toBe('test-object');
      expect(obj.meta.version).toBe(3);
      expect(obj.data).toEqual({ key: 'value' });
    });

    it('should throw error when object not found', async () => {
      fetchMock.mockResponseOnce(JSON.stringify([]));

      await expect(client.getObject('nonexistent'))
        .rejects
        .toThrow('No object found with ID: nonexistent');
    });
  });

  describe('createObject', () => {
    it('should create new object with initial state and cache issue number', async () => {
      const mockIssue = {
        number: 456,
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
        html_url: 'https://github.com/owner/repo/issues/456',
        body: JSON.stringify({ test: 'data' }),
        labels: [
          { name: 'stored-object' },
          { name: 'UID:test-object' }
        ]
      };

      const mockComment = { id: 123 };

      fetchMock
        .mockResponseOnce(JSON.stringify(mockIssue)) // Create issue
        .mockResponseOnce(JSON.stringify(mockComment)) // Create comment
        .mockResponseOnce(JSON.stringify({ id: 1 })) // Add processed reaction
        .mockResponseOnce(JSON.stringify({ id: 2 })) // Add initial state reaction
        .mockResponseOnce(JSON.stringify({ state: 'closed' })); // Close issue

      const data = { test: 'data' };
      const obj = await client.createObject('test-object', data);

      expect(obj.meta.objectId).toBe('test-object');
      expect(obj.meta.version).toBe(1);
      expect(obj.data).toEqual(data);

      // Verify issue creation
      expect(fetchMock.mock.calls[0][1]?.body).toContain('"stored-object"');
      expect(fetchMock.mock.calls[0][1]?.body).toContain('"UID:test-object"');

      // Verify initial state comment
      const commentBody = JSON.parse(JSON.parse(fetchMock.mock.calls[1][1]?.body as string).body);
      expect(commentBody.type).toBe('initial_state');
      expect(commentBody.data).toEqual(data);

      // Verify cache by making a subsequent request
      fetchMock.resetMocks();
      fetchMock
        .mockResponseOnce(JSON.stringify(mockIssue))
        .mockResponseOnce(JSON.stringify([]));

      await client.getObject('test-object');
      expect(fetchMock.mock.calls[0][0]).toContain('/issues/456');
    });

    it('should handle API errors during creation', async () => {
      fetchMock.mockRejectOnce(new Error('API error'));

      await expect(client.createObject('test-object', { test: 'data' }))
        .rejects
        .toThrow('API error');
    });
  });

  describe('updateObject', () => {
    it('should add update comment and reopen issue', async () => {
      const mockIssue = {
        number: 1,
        state: 'closed',
        body: JSON.stringify({ key: 'value' }),
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        labels: [
          { name: 'stored-object' },
          { name: 'UID:test-object' }
        ]
      };

      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue])) // Get issue
        .mockResponseOnce(JSON.stringify({ id: 123 })) // Add comment
        .mockResponseOnce(JSON.stringify({ state: 'open' })) // Reopen issue
        .mockResponseOnce(JSON.stringify([mockIssue])) // Get updated object
        .mockResponseOnce(JSON.stringify([])); // Get comments for version

      const changes = { key: 'updated' };
      const obj = await client.updateObject('test-object', changes);

      expect(obj.data).toEqual({ key: 'value' });

      // Verify update comment
      const commentBody = JSON.parse(fetchMock.mock.calls[1][1]?.body as string).body;
      expect(JSON.parse(commentBody)).toEqual(changes);
      
      // Verify issue reopened
      expect(fetchMock.mock.calls[2][1]?.body).toContain('"state":"open"');
    });

    it('should throw error when object not found', async () => {
      fetchMock.mockResponseOnce(JSON.stringify([]));

      await expect(client.updateObject('nonexistent', { key: 'value' }))
        .rejects
        .toThrow('No object found with ID: nonexistent');
    });
  });

  describe('listAll', () => {
    it('should list all non-archived objects and update cache', async () => {
      const mockIssues = [
        {
          number: 789,
          body: JSON.stringify({ id: 'obj1' }),
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-02T00:00:00Z',
          labels: [
            { name: 'stored-object' },
            { name: 'UID:test-1' }
          ]
        },
        {
          number: 790,
          body: JSON.stringify({ id: 'obj2' }),
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-02T00:00:00Z',
          labels: [
            { name: 'stored-object' },
            { name: 'UID:test-2' },
            { name: 'archived' }
          ]
        }
      ];

      // Add spy on fetch to track calls
      fetchMock.mockImplementation(async (inputUrl: string | Request | undefined, _options?: RequestInit) => {
        if (!inputUrl) {
          return {
            ok: false,
            status: 400,
            statusText: 'No URL provided'
          } as Response;
        }

        const url = inputUrl.toString();
        console.error('Fetch called with URL:', url);
        
        if (url.includes('/issues?labels=')) {
          // Initial listAll query
          return {
            ok: true,
            json: async () => mockIssues
          } as Response;
        } else if (url.includes('/issues/789')) {
          // Direct issue fetch via cache
          console.error('Returning cached issue:', mockIssues[0]);
          return {
            ok: true,
            json: async () => mockIssues[0]
          } as Response;
        } else if (url.includes('/comments')) {
          // Comments query
          return {
            ok: true,
            json: async () => []
          } as Response;
        }
        
        console.error('Unhandled URL in mock:', url);
        return {
          ok: false,
          status: 404
        } as Response;
      });

      // First call to list all objects
      const objects = await client.listAll();

      expect(Object.keys(objects)).toHaveLength(1);
      expect(objects['test-1']).toBeDefined();
      expect(objects['test-2']).toBeUndefined();

      // Now verify the cache by fetching directly
      const cachedObject = await client.getObject('test-1');
      expect(cachedObject.meta.objectId).toBe('test-1');
      expect(cachedObject.data).toEqual({ id: 'obj1' });
    });
  });

  describe('listUpdatedSince', () => {
    it('should list only objects updated after timestamp', async () => {
      const timestamp = new Date('2025-01-01T00:00:00Z');
      const mockIssues = [
        {
          number: 1,
          body: JSON.stringify({ id: 'obj1' }),
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-02T00:00:00Z', // Updated after timestamp
          labels: [
            { name: 'stored-object' },
            { name: 'UID:test-1' }
          ]
        },
        {
          number: 2,
          body: JSON.stringify({ id: 'obj2' }),
          created_at: '2024-12-31T00:00:00Z',
          updated_at: '2024-12-31T12:00:00Z', // Updated before timestamp
          labels: [
            { name: 'stored-object' },
            { name: 'UID:test-2' }
          ]
        }
      ];

      fetchMock
        .mockResponseOnce(JSON.stringify(mockIssues))
        .mockResponseOnce(JSON.stringify([])) // Comments for first issue
        .mockResponseOnce(JSON.stringify([])); // Comments for second issue

      const objects = await client.listUpdatedSince(timestamp);

      expect(Object.keys(objects)).toHaveLength(1);
      expect(objects['test-1']).toBeDefined();
      expect(objects['test-2']).toBeUndefined();
    });
  });

  describe('getObjectHistory', () => {
    it('should return full object history', async () => {
      const mockIssue = {
        number: 1,
        body: JSON.stringify({ id: 'test' }),
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        labels: [
          { name: 'stored-object' },
          { name: 'UID:test-object' }
        ]
      };

      const mockComments = [
        {
          id: 1,
          created_at: '2025-01-01T00:00:00Z',
          body: JSON.stringify({
            type: 'initial_state',
            data: { status: 'new' }
          })
        },
        {
          id: 2,
          created_at: '2025-01-02T00:00:00Z',
          body: JSON.stringify({ status: 'updated' })
        }
      ];

      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue]))
        .mockResponseOnce(JSON.stringify(mockComments));

      const history = await client.getObjectHistory('test-object');

      expect(history).toHaveLength(2);
      expect(history[0].type).toBe('initial_state');
      expect(history[1].type).toBe('update');
    });
  });
});
