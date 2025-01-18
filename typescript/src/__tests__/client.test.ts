// typescript/src/__tests__/client.test.ts
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
    it('should create new object with initial state', async () => {
      const mockIssue = {
        number: 1,
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
        html_url: 'https://github.com/owner/repo/issues/1'
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
        state: 'closed'
      };

      fetchMock
        .mockResponseOnce(JSON.stringify([mockIssue])) // Get issue
        .mockResponseOnce(JSON.stringify({ id: 123 })) // Add comment
        .mockResponseOnce(JSON.stringify({ state: 'open' })) // Reopen issue
        .mockResponseOnce(JSON.stringify([{ // Get updated object
          number: 1,
          body: JSON.stringify({ key: 'updated' }),
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-02T00:00:00Z',
          labels: [
            { name: 'stored-object' },
            { name: 'UID:test-object' }
          ]
        }]))
        .mockResponseOnce(JSON.stringify([])); // Get comments for version

      const changes = { key: 'updated' };
      const obj = await client.updateObject('test-object', changes);

      expect(obj.data).toEqual(changes);

      // Verify update comment
      const commentBody = JSON.parse(fetchMock.mock.calls[1][1]?.body as string).body;
      expect(JSON.parse(commentBody)).toEqual({ key: 'updated' });
      
      // Verify issue reopened
      expect(fetchMock.mock.calls[2][1]?.body).toContain('"state":"open"');
    });

    it('should prevent concurrent updates', async () => {
      const mockIssue = {
        number: 1,
        state: 'open' // Issue already being processed
      };

      fetchMock.mockResponseOnce(JSON.stringify([mockIssue]));

      await expect(client.updateObject('test-object', { key: 'value' }))
        .rejects
        .toThrow('Object is currently being processed');
    });

    it('should throw error when object not found', async () => {
      fetchMock.mockResponseOnce(JSON.stringify([]));

      await expect(client.updateObject('nonexistent', { key: 'value' }))
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
        .mockResponseOnce(JSON.stringify(mockIssues))
        .mockResponseOnce(JSON.stringify([]))  // Comments for version of first issue
        .mockResponseOnce(JSON.stringify([])); // Comments for version of second issue

      const objects = await client.listAll();

      expect(Object.keys(objects)).toHaveLength(1);
      expect(objects['test-1']).toBeDefined();
      expect(objects['test-2']).toBeUndefined();
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
        .mockResponseOnce(JSON.stringify([])) // Comments for version of first issue
        .mockResponseOnce(JSON.stringify([])); // Comments for version of second issue

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
