// src/cache.ts
export interface CacheEntry {
  issueNumber: number;
  lastAccessed: Date;
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

  constructor(config: CacheConfig = {}) {
    this.cache = new Map();
    this.maxSize = config.maxSize ?? 1000;
    this.ttl = config.ttl ?? 1000 * 60 * 60; // Default 1 hour TTL
  }

  get(objectId: string): number | undefined {
    const entry = this.cache.get(objectId);
    
    if (!entry) {
      return undefined;
    }

    // Check if entry has expired
    if (Date.now() - entry.lastAccessed.getTime() > this.ttl) {
      this.cache.delete(objectId);
      return undefined;
    }

    // Update last accessed time
    entry.lastAccessed = new Date();
    return entry.issueNumber;
  }

  set(objectId: string, issueNumber: number, metadata: { createdAt: Date; updatedAt: Date }): void {
    // Evict oldest entries if cache is full
    if (this.cache.size >= this.maxSize) {
      const oldestKey = this.findOldestEntry();
      if (oldestKey) {
        this.cache.delete(oldestKey);
      }
    }

    this.cache.set(objectId, {
      issueNumber,
      lastAccessed: new Date(),
      createdAt: metadata.createdAt,
      updatedAt: metadata.updatedAt
    });
  }

  remove(objectId: string): void {
    this.cache.delete(objectId);
  }

  clear(): void {
    this.cache.clear();
  }

  // Useful for debugging and monitoring
  getStats(): { size: number; maxSize: number; ttl: number } {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      ttl: this.ttl
    };
  }

  // Check if an entry might need updating based on the latest known update time
  shouldRefresh(objectId: string, latestUpdate: Date): boolean {
    const entry = this.cache.get(objectId);
    if (!entry) return true;

    return latestUpdate > entry.updatedAt;
  }

  private findOldestEntry(): string | undefined {
    let oldestKey: string | undefined;
    let oldestTime = Date.now();

    for (const [key, entry] of this.cache.entries()) {
      if (entry.lastAccessed.getTime() < oldestTime) {
        oldestTime = entry.lastAccessed.getTime();
        oldestKey = key;
      }
    }

    return oldestKey;
  }
}
