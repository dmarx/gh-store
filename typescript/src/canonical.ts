// typescript/src/canonical.ts
import { GitHubStoreClient } from './client';
import { GitHubStoreConfig, LabelNames, StoredObject } from './types';
import { Logger } from './logging'; // Import a logger utility

// Create a logger instance
const logger = new Logger('CanonicalStore');

// Configuration for CanonicalStore
export interface CanonicalStoreConfig extends GitHubStoreConfig {
  canonicalize?: boolean; // Whether to perform canonicalization by default
}

// Result type for alias creation
export interface AliasResult {
  success: boolean;
  sourceId: string;
  targetId: string;
}

// The main CanonicalStore class
export class CanonicalStoreClient extends GitHubStoreClient {
  private canonicalizeByDefault: boolean;
  private visitedIds: Set<string>; // For circular reference detection

  constructor(
    token: string,
    repo: string,
    config: CanonicalStoreConfig = {}
  ) {
    super(token, repo, config);
    this.canonicalizeByDefault = config.canonicalize ?? true;
    this.visitedIds = new Set<string>();
    
    // Ensure special labels exist
    this._ensureSpecialLabels().catch(err => {
      logger.warn(`Could not ensure special labels exist: ${(err as Error).message}`);
    });
  }
  
  // Create special labels needed by the system
  private async _ensureSpecialLabels(): Promise<void> {
    const specialLabels = [
      { name: LabelNames.GH_STORE, color: "6f42c1", description: "All issues managed by gh-store system" }
    ];

    try {
      // Get existing labels
      const existingLabelsResponse = await this.fetchFromGitHub<Array<{ name: string }>>("/labels");
      const existingLabels = new Set(existingLabelsResponse.map(label => label.name));

      // Create any missing labels
      for (const label of specialLabels) {
        if (!existingLabels.has(label.name)) {
          try {
            await this.fetchFromGitHub("/labels", {
              method: "POST",
              body: JSON.stringify(label)
            });
          } catch (error) {
            logger.warn(`Could not create label ${label.name}: ${(error as Error).message}`);
          }
        }
      }
    } catch (error) {
      logger.warn(`Could not ensure special labels exist: ${(error as Error).message}`);
    }
  }

  // Resolve object ID to its canonical form
  async resolveCanonicalObjectId(objectId: string, maxDepth: number = 5): Promise<string> {
    // Reset visited IDs for each top-level resolution attempt
    this.visitedIds = new Set<string>();
    return this._resolveCanonicalIdInternal(objectId, maxDepth);
  }

  // Internal method for alias resolution with cycle detection
  private async _resolveCanonicalIdInternal(objectId: string, maxDepth: number): Promise<string> {
    if (maxDepth <= 0) {
      logger.warn(`Maximum alias resolution depth reached for ${objectId}`);
      return objectId;
    }

    // Detect circular references
    if (this.visitedIds.has(objectId)) {
      logger.warn(`Circular reference detected for ${objectId}`);
      return objectId;
    }

    // Mark this ID as visited
    this.visitedIds.add(objectId);

    // Check if this is an alias
    try {
      const issues = await this.fetchFromGitHub<Array<{
        number: number;
        labels: Array<{ name: string }>;
      }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.UID_PREFIX}${objectId},${LabelNames.ALIAS_TO_PREFIX}*`,
          state: "all",
        },
      });

      if (issues && issues.length > 0) {
        for (const issue of issues) {
          for (const label of issue.labels) {
            if (label.name.startsWith(LabelNames.ALIAS_TO_PREFIX)) {
              // Extract canonical object ID from label
              const canonicalId = label.name.slice(LabelNames.ALIAS_TO_PREFIX.length);
              
              // Prevent self-referential loops
              if (canonicalId === objectId) {
                logger.error(`Self-referential alias detected for ${objectId}`);
                return objectId;
              }
              
              // Recurse to follow alias chain
              return this._resolveCanonicalIdInternal(canonicalId, maxDepth - 1);
            }
          }
        }
      }
    } catch (error) {
      logger.warn(`Error resolving canonical ID for ${objectId}: ${(error as Error).message}`);
    }

    // Not an alias, or couldn't resolve - assume it's canonical
    return objectId;
  }

  // Override getObject to implement canonicalization
  async getObject(objectId: string, options: { canonicalize?: boolean } = {}): Promise<StoredObject> {
    const canonicalize = options.canonicalize ?? this.canonicalizeByDefault;
    
    if (canonicalize) {
      const canonicalId = await this.resolveCanonicalObjectId(objectId);
      if (canonicalId !== objectId) {
        logger.info(`Object ${objectId} resolved to canonical object ${canonicalId}`);
      }
      return super.getObject(canonicalId);
    } else {
      // Direct fetch without canonicalization
      return super.getObject(objectId);
    }
  }

  // Create an alias relationship
  async createAlias(sourceId: string, targetId: string): Promise<AliasResult> {
    // 1. Verify source object exists
    let sourceIssue;
    try {
      const sourceIssues = await this.fetchFromGitHub<Array<{ number: number }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.UID_PREFIX}${sourceId},${LabelNames.STORED_OBJECT}`,
          state: "all",
        },
      });
      
      if (!sourceIssues || sourceIssues.length === 0) {
        throw new Error(`Source object not found: ${sourceId}`);
      }
      
      sourceIssue = sourceIssues[0];
    } catch (error) {
      throw new Error(`Error finding source object: ${(error as Error).message}`);
    }
    
    // 2. Verify target object exists
    try {
      const targetIssues = await this.fetchFromGitHub<Array<{ number: number }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.UID_PREFIX}${targetId},${LabelNames.STORED_OBJECT}`,
          state: "all",
        },
      });
      
      if (!targetIssues || targetIssues.length === 0) {
        throw new Error(`Target object not found: ${targetId}`);
      }
    } catch (error) {
      throw new Error(`Error finding target object: ${(error as Error).message}`);
    }
    
    // 3. Check if this is already an alias
    try {
      const existingAliasLabels = await this.fetchFromGitHub<Array<{ name: string }>>(`/issues/${sourceIssue.number}/labels`);
      
      for (const label of existingAliasLabels) {
        if (label.name.startsWith(LabelNames.ALIAS_TO_PREFIX)) {
          throw new Error(`Object ${sourceId} is already an alias`);
        }
      }
    } catch (error) {
      if (!(error as Error).message.includes('already an alias')) {
        throw new Error(`Error checking existing aliases: ${(error as Error).message}`);
      } else {
        throw error; // Rethrow "already an alias" error
      }
    }
    
    // 4. Create alias label if it doesn't exist
    const aliasLabel = `${LabelNames.ALIAS_TO_PREFIX}${targetId}`;
    try {
      // Try to create the label - might fail if it already exists
      try {
        await this.fetchFromGitHub("/labels", {
          method: "POST",
          body: JSON.stringify({
            name: aliasLabel,
            color: "fbca04"
          })
        });
      } catch (error) {
        // Label might already exist, continue
        logger.warn(`Could not create label ${aliasLabel}: ${(error as Error).message}`);
      }
      
      // Add label to source issue
      await this.fetchFromGitHub(`/issues/${sourceIssue.number}/labels`, {
        method: "POST",
        body: JSON.stringify({
          labels: [aliasLabel]
        })
      });
      
      return {
        success: true,
        sourceId,
        targetId
      };
    } catch (error) {
      throw new Error(`Failed to create alias: ${(error as Error).message}`);
    }
  }

  // Find aliases in the repository
  async findAliases(objectId?: string): Promise<Record<string, string>> {
    const aliases: Record<string, string> = {};
    
    try {
      if (objectId) {
        // Find aliases for specific object
        const aliasIssues = await this.fetchFromGitHub<Array<{
          labels: Array<{ name: string }>;
        }>>("/issues", {
          method: "GET",
          params: {
            labels: `${LabelNames.ALIAS_TO_PREFIX}${objectId}`,
            state: "all",
          },
        });
        
        for (const issue of aliasIssues || []) {
          const aliasId = this._extractObjectIdFromLabels(issue);
          if (aliasId) {
            aliases[aliasId] = objectId;
          }
        }
      } else {
        // Find all aliases
        const aliasIssues = await this.fetchFromGitHub<Array<{
          labels: Array<{ name: string }>;
        }>>("/issues", {
          method: "GET",
          params: {
            labels: `${LabelNames.ALIAS_TO_PREFIX}*`,
            state: "all",
          },
        });
        
        for (const issue of aliasIssues || []) {
          const aliasId = this._extractObjectIdFromLabels(issue);
          if (!aliasId) continue;
          
          // Find target of alias
          for (const label of issue.labels) {
            if (label.name.startsWith(LabelNames.ALIAS_TO_PREFIX)) {
              const canonicalId = label.name.slice(LabelNames.ALIAS_TO_PREFIX.length);
              aliases[aliasId] = canonicalId;
              break;
            }
          }
        }
      }
      
      return aliases;
    } catch (error) {
      logger.warn(`Error finding aliases: ${(error as Error).message}`);
      return {};
    }
  }

  // Helper to extract object ID from labels
  protected _extractObjectIdFromLabels(issue: { labels: Array<{ name: string }> }): string {
    for (const label of issue.labels) {
      if (label.name.startsWith(LabelNames.UID_PREFIX)) {
        return label.name.slice(LabelNames.UID_PREFIX.length);
      }
    }
    
    throw new Error(`No UID label found with prefix ${LabelNames.UID_PREFIX}`);
  }
}
