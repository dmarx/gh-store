// src/__tests__/cache.test.ts
import { jest, describe, it, expect, beforeEach } from '@jest/globals';
import { IssueCache } from '../cache';

describe('IssueCache', () => {
  let cache: IssueCache;
  
  beforeEach(() => {
    cache = new IssueCache();
  });

  it('should store and retrieve issue numbers', () => {
    const metadata = {
      createdAt: new Date(),
      updatedAt: new Date()
    };
    
    cache.set('test-1', 123, metadata);
    expect(cache.get('test-1')).toBe(123);
  });

  it('should respect maxSize limit', () => {
    const cache = new IssueCache({ maxSize: 2 });
    const metadata = {
      createdAt: new Date(),
      updatedAt: new Date()
    };

    cache.set('test-1', 123, metadata);
    cache.set('test-2', 456, metadata);
    cache.set('test-3', 789, metadata); // Should evict oldest

    expect(cache.get('test-1')).toBeUndefined();
    expect(cache.get('test-2')).toBe(456);
    expect(cache.get('test-3')).toBe(789);
  });

  it('should respect TTL', () => {
    jest.useFakeTimers();
    const cache = new IssueCache({ ttl: 1000 }); // 1 second TTL
    const metadata = {
      createdAt: new Date(),
      updatedAt: new Date()
    };

    cache.set('test-1', 123, metadata);
    expect(cache.get('test-1')).toBe(123);

    // Advance time past TTL
    jest.advanceTimersByTime(1001);
    expect(cache.get('test-1')).toBeUndefined();

    jest.useRealTimers();
  });

  it('should clear all entries', () => {
    const metadata = {
      createdAt: new Date(),
      updatedAt: new Date()
    };

    cache.set('test-1', 123, metadata);
    cache.set('test-2', 456, metadata);
    
    cache.clear();
    
    expect(cache.get('test-1')).toBeUndefined();
    expect(cache.get('test-2')).toBeUndefined();
    expect(cache.getStats().size).toBe(0);
  });

  it('should report correct stats', () => {
    const cache = new IssueCache({ maxSize: 100, ttl: 3600000 });
    const metadata = {
      createdAt: new Date(),
      updatedAt: new Date()
    };

    cache.set('test-1', 123, metadata);
    cache.set('test-2', 456, metadata);

    const stats = cache.getStats();
    expect(stats.size).toBe(2);
    expect(stats.maxSize).toBe(100);
    expect(stats.ttl).toBe(3600000);
  });

  it('should correctly determine if refresh is needed', () => {
    const createdAt = new Date('2025-01-01');
    const updatedAt = new Date('2025-01-02');
    const metadata = { createdAt, updatedAt };

    cache.set('test-1', 123, metadata);

    // No refresh needed for same or older update time
    expect(cache.shouldRefresh('test-1', updatedAt)).toBe(false);
    expect(cache.shouldRefresh('test-1', new Date('2025-01-01'))).toBe(false);

    // Refresh needed for newer update time
    expect(cache.shouldRefresh('test-1', new Date('2025-01-03'))).toBe(true);

    // Always refresh for non-existent entries
    expect(cache.shouldRefresh('nonexistent', new Date())).toBe(true);
  });
});
