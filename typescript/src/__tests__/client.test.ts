// typescript/src/__tests__/client.test.ts

import { describe, it, expect, beforeEach } from '@jest/globals';
import { GitHubStoreClient } from '../client';
import { CLIENT_VERSION } from '../version';
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
  });

  describe('createObject', () => {
    it('should create new object with initial state and metadata', async () => {
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

      // Verify initial state comment with metadata
      const commentBody = JSON.parse(JSON.parse(fetchMock.mock.calls[1][1]?.body as string).body);
      expect(commentBody.type).toBe('initial_state');
      expect(commentBody._data).toEqual(data);
      expect(commentBody._meta).toBeDefined();
      expect(commentBody._meta.client_version).toBe(CLIENT_VERSION);
      expect(commentBody._meta.timestamp).toBeDefined();
      expect(commentBody._meta.update_mode).toBe('append');
    });
  });

  describe('updateObject', () => {
    it('should add update comment with metadata', async () => {
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
      await client.updateObject('test-object', changes);

      // Verify update comment with metadata
      const commentPayload = JSON.parse(fetchMock.mock.calls[1][1]?.body as string);
      const commentBody = JSON.parse(commentPayload.body);
      expect(commentBody._data).toEqual(changes);
      expect(commentBody._meta).toBeDefined();
      expect(commentBody._meta.client_version).toBe(CLIENT_VERSION);
      expect(commentBody._meta.timestamp).toBeDefined();
      expect(commentBody._meta.update_mode).toBe('append');
    });
  });

  describe('getObjectHistory', () => {
    it('should return full object history with metadata', async () => {
      const mockIssue = {
        number: 1,
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
            _data: { status: 'new' },
            _meta: {
              client_version: CLIENT_VERSION,
              timestamp: '2025-01-01T00:00:00Z',
              update_mode: 'append'
            }
          })
        },
        {
          id: 2,
          created_at: '2025-01-02T00:00:00Z',
          body: JSON.stringify({
            _data: { status: 'updated' },
            _meta: {
              client_version: CLIENT_VERSION,
              timestamp: '2025-01-02T00:00:00Z',
              update_mode: 'append'
            }
          })
        }
      ];

      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue]))
        .mockResponseOnce(JSON.stringify(mockComments));

      const history = await client.getObjectHistory('test-object');

      expect(history).toHaveLength(2);
      expect(history[0].type).toBe('initial_state');
      expect(history[0].data).toEqual({ status: 'new' });
      expect(history[1].type).toBe('update');
      expect(history[1].data).toEqual({ status: 'updated' });
    });
  });

  describe('API Error Handling', () => {
    it('should throw error on API failure', async () => {
      fetchMock.mockResponseOnce('', { 
        status: 500,
        statusText: 'Internal Server Error'
      });

      await expect(client.getObject('test-obj'))
        .rejects
        .toThrow('GitHub API error: 500');
    });

    it('should handle malformed JSON responses', async () => {
      fetchMock.mockResponseOnce('invalid json');

      await expect(client.getObject('test-obj'))
        .rejects
        .toThrow();
    });
  });

  describe('listAll', () => {
    it('should handle empty repository', async () => {
      fetchMock.mockResponseOnce(JSON.stringify([]));

      const objects = await client.listAll();
      expect(Object.keys(objects)).toHaveLength(0);
    });

    it('should handle invalid issue data', async () => {
      const mockIssues = [{
        number: 1,
        body: 'invalid json',
        labels: [
          { name: 'stored-object' },
          { name: 'UID:test-1' }
        ],
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z'
      }];

      fetchMock.mockResponseOnce(JSON.stringify(mockIssues));

      const objects = await client.listAll();
      expect(Object.keys(objects)).toHaveLength(0);
    });

    it('should skip issues without proper labels', async () => {
      const mockIssues = [{
        number: 1,
        body: JSON.stringify({ test: 'data' }),
        labels: [
          { name: 'stored-object' }  // Missing UID label
        ],
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z'
      }];

      fetchMock.mockResponseOnce(JSON.stringify(mockIssues));

      const objects = await client.listAll();
      expect(Object.keys(objects)).toHaveLength(0);
    });
  });

  describe('listUpdatedSince', () => {
    it('should handle no updates', async () => {
      const timestamp = new Date('2025-01-01T00:00:00Z');
      fetchMock.mockResponseOnce(JSON.stringify([]));

      const objects = await client.listUpdatedSince(timestamp);
      expect(Object.keys(objects)).toHaveLength(0);
    });

    it('should ignore updates before timestamp', async () => {
      const timestamp = new Date('2025-01-02T00:00:00Z');
      const mockIssues = [{
        number: 1,
        body: JSON.stringify({ test: 'data' }),
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T12:00:00Z',  // Before timestamp
        labels: [
          { name: 'stored-object' },
          { name: 'UID:test-1' }
        ]
      }];

      fetchMock.mockResponseOnce(JSON.stringify(mockIssues));

      const objects = await client.listUpdatedSince(timestamp);
      expect(Object.keys(objects)).toHaveLength(0);
    });
  });

  describe('getObjectHistory', () => {
    it('should handle missing object', async () => {
      fetchMock.mockResponseOnce(JSON.stringify([]));

      await expect(client.getObjectHistory('nonexistent'))
        .rejects
        .toThrow('No object found with ID: nonexistent');
    });

    it('should handle invalid comments', async () => {
      const mockIssue = {
        number: 1,
        labels: [
          { name: 'stored-object' },
          { name: 'UID:test-object' }
        ]
      };

      const mockComments = [
        {
          id: 1,
          created_at: '2025-01-01T00:00:00Z',
          body: 'invalid json'  // Invalid comment
        },
        {
          id: 2,
          created_at: '2025-01-02T00:00:00Z',
          body: JSON.stringify({
            _data: { status: 'valid' },
            _meta: {
              client_version: CLIENT_VERSION,
              timestamp: '2025-01-02T00:00:00Z',
              update_mode: 'append'
            }
          })
        }
      ];

      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue]))
        .mockResponseOnce(JSON.stringify(mockComments));

      const history = await client.getObjectHistory('test-object');

      expect(history).toHaveLength(1);  // Only valid comment included
      expect(history[0].data).toEqual({ status: 'valid' });
    });

    it('should process legacy format comments', async () => {
      const mockIssue = {
        number: 1,
        labels: [
          { name: 'stored-object' },
          { name: 'UID:test-object' }
        ]
      };

      const mockComments = [
        {
          id: 1,
          created_at: '2025-01-01T00:00:00Z',
          body: JSON.stringify({ status: 'legacy' })  // Legacy format
        }
      ];

      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue]))
        .mockResponseOnce(JSON.stringify(mockComments));

      const history = await client.getObjectHistory('test-object');

      expect(history).toHaveLength(1);
      expect(history[0].type).toBe('update');
      expect(history[0].data).toEqual({ status: 'legacy' });
    });
  });
});
