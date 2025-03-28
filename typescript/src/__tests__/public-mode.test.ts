// typescript/src/__tests__/public-mode.test.ts
import { describe, it, expect, beforeEach } from '@jest/globals';
import { GitHubStoreClient } from '../client';
import fetchMock from 'jest-fetch-mock';

describe('GitHubStoreClient in Public Mode', () => {
  let client: GitHubStoreClient;
  const repo = 'owner/repo';

  beforeEach(() => {
    fetchMock.resetMocks();
    // Initialize in public mode (no token)
    client = new GitHubStoreClient(null, repo);
  });

  it('should correctly identify as public mode', () => {
    expect(client.isPublic()).toBe(true);
  });

  it('should fetch objects without authentication headers', async () => {
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

    fetchMock
      .mockResponseOnce(JSON.stringify([mockIssue]))
      .mockResponseOnce(JSON.stringify([]));

    await client.getObject('test-object');
    
    // Verify no auth header was sent
    expect(fetchMock.mock.calls[0][1]?.headers).not.toHaveProperty('Authorization');
  });

  it('should reject create operations in public mode', async () => {
    await expect(client.createObject('test-object', { key: 'value' }))
      .rejects
      .toThrow('Authentication required for creating objects');
  });

  it('should reject update operations in public mode', async () => {
    await expect(client.updateObject('test-object', { key: 'value' }))
      .rejects
      .toThrow('Authentication required for updating objects');
  });

  it('should fetch object history in public mode', async () => {
    const mockIssue = {
      number: 123,
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
            client_version: '0.9.0',
            timestamp: '2025-01-01T00:00:00Z',
            update_mode: 'append'
          }
        })
      }
    ];

    fetchMock
      .mockResponseOnce(JSON.stringify([mockIssue]))
      .mockResponseOnce(JSON.stringify(mockComments));

    const history = await client.getObjectHistory('test-object');
    
    expect(history).toHaveLength(1);
    expect(history[0].type).toBe('initial_state');
    expect(history[0].data).toEqual({ status: 'new' });
    
    // Verify no auth header was sent
    expect(fetchMock.mock.calls[0][1]?.headers).not.toHaveProperty('Authorization');
  });
});
