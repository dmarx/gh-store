// src/__tests__/client.test.ts
import { GitHubStoreClient } from '../client';
import fetchMock from 'jest-fetch-mock';

describe('GitHubStoreClient', () => {
  const token = 'test-token';
  const repo = 'owner/repo';
  let client: GitHubStoreClient;

  beforeEach(() => {
    fetchMock.resetMocks();
    client = new GitHubStoreClient(token, repo);
  });

  describe('getObject', () => {
    it('should fetch and parse object correctly', async () => {
      const mockIssue = {
        number: 1,
        body: JSON.stringify({ key: 'value' }),
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        labels: [
          { name: 'stored-object' },
          { name: 'UID:test-object' }
        ]
      };

      const mockComments = [{ id: 1 }, { id: 2 }];

      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue])) // Issues query
        .mockResponseOnce(JSON.stringify(mockComments)); // Comments for version

      const obj = await client.getObject('test-object');

      expect(obj.meta.objectId).toBe('test-object');
      expect(obj.meta.version).toBe(3); // 2 comments + 1
      expect(obj.data).toEqual({ key: 'value' });
    });

    it('should throw error when object not found', async () => {
      fetchMock.mockResponseOnce(JSON.stringify([]));

      await expect(client.getObject('nonexistent'))
        .rejects
        .toThrow('No object found with ID: nonexistent');
    });
  });

  describe('listAll', () => {
    it('should list all non-archived objects', async () => {
      const mockIssues = [
        {
          number: 1,
          body: JSON.stringify({ id: 'obj1' }),
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-02T00:00:00Z',
          labels: [
            { name: 'stored-object' },
            { name: 'UID:test-1' }
          ]
        },
        {
          number: 2,
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

      fetchMock
        .mockResponseOnce(JSON.stringify(mockIssues)) // Initial issues query
        .mockResponseOnce(JSON.stringify([])) // Comments for first object
        .mockResponseOnce(JSON.stringify(mockIssues[0])); // Get first object

      const objects = await client.listAll();

      expect(Object.keys(objects)).toHaveLength(1);
      expect(objects['test-1']).toBeDefined();
      expect(objects['test-2']).toBeUndefined(); // Archived object
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
        .mockResponseOnce(JSON.stringify([]))
        .mockResponseOnce(JSON.stringify(mockIssues[0]));

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
