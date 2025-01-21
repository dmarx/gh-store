// src/cache.ts
export interface CacheEntry {
  issueNumber: number;
  lastAccessed: number; // Using timestamp instead of Date for easier comparison
  createdAt: Date;
  updatedAt: Date;
}

export interface CacheConfig {
  maxSize?: number;
  ttl?: number; // Time-to-live in milliseconds
}

export class IssueCache {
  private cache: Map<string, CacheEntry>;
  private maxSize: number;
  private ttl: number;
  private accessOrder: string[]; // Track order of access

  constructor(config: CacheConfig = {}) {
    this.cache = new Map();
    this.maxSize = config.maxSize ?? 1000;
    this.ttl = config.ttl ?? 1000 * 60 * 60; // Default 1 hour TTL
    this.accessOrder = [];
  }

  get(objectId: string): number | undefined {
    const entry = this.cache.get(objectId);
    
    if (!entry) {
      return undefined;
    }

    // Check if entry has expired
    if (Date.now() - entry.lastAccessed > this.ttl) {
      this.cache.delete(objectId);
      this.removeFromAccessOrder(objectId);
      return undefined;
    }

    // Update last accessed time and move to front of access order
    entry.lastAccessed = Date.now();
    this.updateAccessOrder(objectId);
    return entry.issueNumber;
  }

  set(objectId: string, issueNumber: number, metadata: { createdAt: Date; updatedAt: Date }): void {
    // Evict least recently used entry if cache is full
    if (this.cache.size >= this.maxSize && !this.cache.has(objectId)) {
      const lru = this.accessOrder[this.accessOrder.length - 1];
      if (lru) {
        this.cache.delete(lru);
        this.removeFromAccessOrder(lru);
      }
    }

    // Add/update entry
    this.cache.set(objectId, {
      issueNumber,
      lastAccessed: Date.now(),
      createdAt: metadata.createdAt,
      updatedAt: metadata.updatedAt
    });

    this.updateAccessOrder(objectId);
  }

  remove(objectId: string): void {
    this.cache.delete(objectId);
    this.removeFromAccessOrder(objectId);
  }

  clear(): void {
    this.cache.clear();
    this.accessOrder = [];
  }

  getStats(): { size: number; maxSize: number; ttl: number } {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      ttl: this.ttl
    };
  }

  shouldRefresh(objectId: string, latestUpdate: Date): boolean {
    const entry = this.cache.get(objectId);
    if (!entry) return true;

    return latestUpdate > entry.updatedAt;
  }

  private updateAccessOrder(objectId: string): void {
    this.removeFromAccessOrder(objectId);
    this.accessOrder.unshift(objectId); // Add to front
  }

  private removeFromAccessOrder(objectId: string): void {
    const index = this.accessOrder.indexOf(objectId);
    if (index > -1) {
      this.accessOrder.splice(index, 1);
    }
  }
}
