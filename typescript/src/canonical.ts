// typescript/src/canonical.ts
import { GitHubStoreClient } from './client';
import { StoredObject, GitHubStoreConfig, Json, CommentPayload } from './types';
import { CLIENT_VERSION } from './version';

// Label constants for canonicalization system
export enum LabelNames {
  GH_STORE = "gh-store",
  STORED_OBJECT = "stored-object",
  DEPRECATED = "deprecated-object",
  UID_PREFIX = "UID:",
  ALIAS_TO_PREFIX = "ALIAS-TO:",
  MERGED_INTO_PREFIX = "MERGED-INTO:",
  DEPRECATED_BY_PREFIX = "DEPRECATED-BY:"
}

// Deprecation reason constants
export enum DeprecationReason {
  DUPLICATE = "duplicate",
  MERGED = "merged",
  REPLACED = "replaced"
}

// Interface for comment history with metadata
export interface CommentHistory {
  timestamp: string;
  type: string;
  data: Json;
  commentId: number;
  metadata?: {
    client_version: string;
    timestamp: string;
    update_mode: string;
    [key: string]: any;
  };
  source_issue?: number;
  source_object_id?: string;
}

// Configuration for CanonicalStore
export interface CanonicalStoreConfig extends GitHubStoreConfig {
  canonicalize?: boolean; // Whether to perform canonicalization by default
}

// The main CanonicalStore class
export class CanonicalStoreClient extends GitHubStoreClient {
  private canonicalizeByDefault: boolean;

  constructor(
    token: string,
    repo: string,
    config: CanonicalStoreConfig = {}
  ) {
    super(token, repo, config);
    this.canonicalizeByDefault = config.canonicalize ?? true;
    
    // Ensure special labels exist
    this._ensureSpecialLabels().catch(err => {
      console.warn(`Could not ensure special labels exist: ${(err as Error).message}`);
    });
  }
  
  // Override the protected method from GitHubStoreClient
  protected async fetchFromGitHub<T>(path: string, options: RequestInit & { params?: Record<string, string> } = {}): Promise<T> {
    return super.fetchFromGitHub<T>(path, options);
  }

  // Create special labels needed by the system
  private async _ensureSpecialLabels(): Promise<void> {
    const specialLabels = [
      { name: LabelNames.GH_STORE, color: "6f42c1", description: "All issues managed by gh-store system" },
      { name: LabelNames.DEPRECATED, color: "999999", description: "Deprecated objects that have been merged into others" }
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
            console.warn(`Could not create label ${label.name}: ${(error as Error).message}`);
          }
        }
      }
    } catch (error) {
      console.warn(`Could not ensure special labels exist: ${(error as Error).message}`);
    }
  }

  // Resolve object ID to its canonical form
  async resolveCanonicalObjectId(objectId: string, maxDepth: number = 5): Promise<string> {
    if (maxDepth <= 0) {
      console.warn(`Maximum alias resolution depth reached for ${objectId}`);
      return objectId;
    }

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
                console.error(`Self-referential alias detected for ${objectId}`);
                return objectId;
              }
              
              // Recurse to follow alias chain
              return this.resolveCanonicalObjectId(canonicalId, maxDepth - 1);
            }
          }
        }
      }
    } catch (error) {
      console.warn(`Error resolving canonical ID for ${objectId}: ${error}`);
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
        console.info(`Object ${objectId} resolved to canonical object ${canonicalId}`);
      }
      return this.processWithVirtualMerge(canonicalId);
    } else {
      // Direct fetch without canonicalization
      return super.getObject(objectId);
    }
  }

  // Process virtual merge to build unified object
  async processWithVirtualMerge(objectId: string): Promise<StoredObject> {
    // Collect all related comments
    const allComments = await this.collectAllComments(objectId);
    
    // Find initial state
    let initialState = allComments.find(c => c.type === "initial_state");
    
    if (!initialState) {
      // Try to get initial state from issue body
      try {
        const obj = await super.getObject(objectId);
        initialState = {
          timestamp: obj.meta.createdAt.toISOString(),
          type: "initial_state",
          data: obj.data,
          commentId: 0,
          metadata: {
            client_version: CLIENT_VERSION,
            timestamp: obj.meta.createdAt.toISOString(),
            update_mode: "append"
          }
        };
      } catch (error) {
        throw new Error(`No initial state found for ${objectId}: ${(error as Error).message}`);
      }
    }
    
    // Start with initial data
    let currentState = initialState.data;
    
    // Apply all updates in order
    for (const comment of allComments) {
      if (comment.type === "initial_state") continue;
      
      // Apply update based on update mode
      const updateMode = comment.metadata?.update_mode ?? "append";
      
      if (updateMode === "append") {
        currentState = this._deepMerge(currentState, comment.data);
      } else if (updateMode === "replace") {
        currentState = comment.data;
      }
    }
    
    // Get metadata from the canonical object
    try {
      const obj = await super.getObject(objectId);
      
      // Update the canonical issue body with merged state
      await this._updateIssueBody(obj.meta.objectId, currentState);
      
      // Return object with merged data
      return {
        meta: {
          ...obj.meta,
          updatedAt: new Date(), // Update timestamp to now
          version: allComments.length + 1 // Increment version
        },
        data: currentState
      };
    } catch (error) {
      throw new Error(`Error updating canonical object: ${error.message}`);
    }
  }

  // Update issue body with merged state
  private async _updateIssueBody(objectId: string, data: Json): Promise<void> {
    try {
      // Find the issue
      const issues = await this.fetchFromGitHub<Array<{ number: number }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.UID_PREFIX}${objectId},${LabelNames.STORED_OBJECT}`,
          state: "all",
        },
      });

      if (issues && issues.length > 0) {
        await this.fetchFromGitHub(`/issues/${issues[0].number}`, {
          method: "PATCH",
          body: JSON.stringify({
            body: JSON.stringify(data, null, 2),
            state: "closed" // Ensure issue is closed
          })
        });
      }
    } catch (error) {
      console.warn(`Could not update issue body for ${objectId}: ${error.message}`);
    }
  }

  // Collect all comments from canonical, alias, and deprecated issues
  async collectAllComments(objectId: string): Promise<CommentHistory[]> {
    const canonicalId = await this.resolveCanonicalObjectId(objectId);
    const comments: CommentHistory[] = [];
    const visitedIssues = new Set<number>();
    
    // 1. Get canonical issue comments
    try {
      const canonicalIssues = await this.fetchFromGitHub<Array<{ number: number }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.UID_PREFIX}${canonicalId},${LabelNames.STORED_OBJECT}`,
          state: "all",
        },
      });
      
      if (canonicalIssues && canonicalIssues.length > 0) {
        const issue = canonicalIssues[0];
        const issueComments = await this._getCommentsForIssue(issue.number, canonicalId);
        comments.push(...issueComments);
        visitedIssues.add(issue.number);
      } else {
        throw new Error(`No canonical object found with ID: ${canonicalId}`);
      }
    } catch (error) {
      throw new Error(`Error getting canonical issue comments: ${error.message}`);
    }
    
    // 2. Get alias issue comments
    try {
      const aliasIssues = await this.fetchFromGitHub<Array<{ 
        number: number;
        labels: Array<{ name: string }>
      }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.ALIAS_TO_PREFIX}${canonicalId}`,
          state: "all",
        },
      });
      
      for (const issue of aliasIssues || []) {
        if (visitedIssues.has(issue.number)) continue;
        
        // Extract alias object ID from labels
        let aliasId = null;
        for (const label of issue.labels) {
          if (label.name.startsWith(LabelNames.UID_PREFIX)) {
            aliasId = label.name.slice(LabelNames.UID_PREFIX.length);
            break;
          }
        }
        
        if (!aliasId) continue;
        
        const issueComments = await this._getCommentsForIssue(issue.number, aliasId);
        comments.push(...issueComments);
        visitedIssues.add(issue.number);
      }
    } catch (error) {
      console.warn(`Error getting alias issue comments: ${error.message}`);
    }
    
    // 3. Get deprecated issue comments
    try {
      const deprecatedIssues = await this.fetchFromGitHub<Array<{ number: number }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.GH_STORE},${LabelNames.UID_PREFIX}${canonicalId},${LabelNames.DEPRECATED}`,
          state: "all",
        },
      });
      
      for (const issue of deprecatedIssues || []) {
        if (visitedIssues.has(issue.number)) continue;
        
        const issueComments = await this._getCommentsForIssue(issue.number, canonicalId);
        comments.push(...issueComments);
        visitedIssues.add(issue.number);
      }
    } catch (error) {
      console.warn(`Error getting deprecated issue comments: ${error.message}`);
    }
    
    // Sort by timestamp
    return comments.sort((a, b) => {
      return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
    });
  }

  // Extract comments from an issue
  private async _getCommentsForIssue(issueNumber: number, objectId: string): Promise<CommentHistory[]> {
    const comments: CommentHistory[] = [];
    
    try {
      const issueComments = await this.fetchFromGitHub<Array<{
        id: number;
        created_at: string;
        body: string;
      }>>(`/issues/${issueNumber}/comments`);
      
      for (const comment of issueComments) {
        try {
          const payload = JSON.parse(comment.body);
          let commentType = 'update';
          let commentData: Json;
          let metadata = {
            client_version: 'legacy',
            timestamp: comment.created_at,
            update_mode: 'append'
          };
          
          if (typeof payload === 'object') {
            if ('_data' in payload) {
              // New format with metadata
              commentType = payload.type || 'update';
              commentData = payload._data;
              metadata = payload._meta || metadata;
            } else if ('type' in payload && payload.type === 'initial_state') {
              // Old initial state format
              commentType = 'initial_state';
              commentData = payload.data;
            } else {
              // Legacy format
              commentData = payload;
            }
          } else {
            commentData = payload;
          }
          
          comments.push({
            timestamp: comment.created_at,
            type: commentType,
            data: commentData,
            commentId: comment.id,
            metadata,
            source_issue: issueNumber,
            source_object_id: objectId
          });
        } catch (error) {
          // Skip invalid comments
          continue;
        }
      }
    } catch (error) {
      console.warn(`Error processing comments for issue #${issueNumber}: ${(error as Error).message}`);
    }
    
    return comments;
  }

  // Override updateObject to handle aliases
  async updateObject(objectId: string, changes: Json): Promise<StoredObject> {
    // Find the object - first try direct match, then resolve alias
    let issue;
    
    try {
      // Check if this is a direct match
      const directIssues = await this.fetchFromGitHub<Array<{ number: number }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.UID_PREFIX}${objectId},${LabelNames.STORED_OBJECT}`,
          state: "all",
        },
      });
      
      if (directIssues && directIssues.length > 0) {
        issue = directIssues[0];
      } else {
        // Try to resolve as alias
        const canonicalId = await this.resolveCanonicalObjectId(objectId);
        
        const canonicalIssues = await this.fetchFromGitHub<Array<{ number: number }>>("/issues", {
          method: "GET",
          params: {
            labels: `${LabelNames.UID_PREFIX}${canonicalId},${LabelNames.STORED_OBJECT}`,
            state: "all",
          },
        });
        
        if (canonicalIssues && canonicalIssues.length > 0) {
          issue = canonicalIssues[0];
        } else {
          throw new Error(`No object found with ID: ${objectId}`);
        }
      }
      
      // Create update payload with metadata
      const updatePayload: CommentPayload = {
        _data: changes,
        _meta: {
          client_version: CLIENT_VERSION,
          timestamp: new Date().toISOString(),
          update_mode: "append"
        }
      };
      
      // Add update comment
      await this.fetchFromGitHub(`/issues/${issue.number}/comments`, {
        method: "POST",
        body: JSON.stringify({
          body: JSON.stringify(updatePayload, null, 2)
        })
      });
      
      // Reopen issue to trigger processing
      await this.fetchFromGitHub(`/issues/${issue.number}`, {
        method: "PATCH",
        body: JSON.stringify({ state: "open" })
      });
      
      // Return the object with canonicalize=false to preserve alias identity
      return this.getObject(objectId, { canonicalize: false });
    } catch (error) {
      throw new Error(`Error updating object: ${error.message}`);
    }
  }

  // Create an alias relationship
  async createAlias(sourceId: string, targetId: string): Promise<{
    success: boolean;
    sourceId: string;
    targetId: string;
  }> {
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
      throw new Error(`Error finding source object: ${error.message}`);
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
      throw new Error(`Error finding target object: ${error.message}`);
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
      if (!error.message.includes('already an alias')) {
        throw new Error(`Error checking existing aliases: ${error.message}`);
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
      throw new Error(`Failed to create alias: ${error.message}`);
    }
  }

  // Deprecate an object
  async deprecateObject(
    objectId: string, 
    targetId: string, 
    reason: DeprecationReason = DeprecationReason.DUPLICATE
  ): Promise<{
    success: boolean;
    sourceObjectId: string;
    targetObjectId: string;
    reason: string;
  }> {
    // 1. Verify objects exist
    let sourceIssue, targetIssue;
    
    try {
      const sourceIssues = await this.fetchFromGitHub<Array<{ 
        number: number;
        labels: Array<{ name: string }>;
      }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.UID_PREFIX}${objectId},${LabelNames.STORED_OBJECT}`,
          state: "all",
        },
      });
      
      if (!sourceIssues || sourceIssues.length === 0) {
        throw new Error(`Source object not found: ${objectId}`);
      }
      
      sourceIssue = sourceIssues[0];
    } catch (error) {
      throw new Error(`Error finding source object: ${error.message}`);
    }
    
    try {
      const targetIssues = await this.fetchFromGitHub<Array<{ 
        number: number;
        labels: Array<{ name: string }>;
      }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.UID_PREFIX}${targetId},${LabelNames.STORED_OBJECT}`,
          state: "all",
        },
      });
      
      if (!targetIssues || targetIssues.length === 0) {
        throw new Error(`Target object not found: ${targetId}`);
      }
      
      targetIssue = targetIssues[0];
    } catch (error) {
      throw new Error(`Error finding target object: ${error.message}`);
    }
    
    // 2. Validate that we're not trying to deprecate an object as itself
    if (objectId === targetId && sourceIssue.number === targetIssue.number) {
      throw new Error(`Cannot deprecate an object as itself: ${objectId}`);
    }
    
    // 3. Remove stored-object label from source
    try {
      await this.fetchFromGitHub(`/issues/${sourceIssue.number}/labels/${LabelNames.STORED_OBJECT}`, {
        method: "DELETE"
      });
    } catch (error) {
      console.warn(`Error removing stored-object label: ${error.message}`);
    }
    
    // 4. Add deprecation labels
    try {
      const mergeLabel = `${LabelNames.MERGED_INTO_PREFIX}${targetId}`;
      const deprecatedByLabel = `${LabelNames.DEPRECATED_BY_PREFIX}${targetIssue.number}`;
      
      // Create labels if they don't exist
      try {
        await this.fetchFromGitHub("/labels", {
          method: "POST",
          body: JSON.stringify({
            name: mergeLabel,
            color: "d73a49"
          })
        });
      } catch (error) {
        // Label might already exist, continue
      }
      
      try {
        await this.fetchFromGitHub("/labels", {
          method: "POST",
          body: JSON.stringify({
            name: deprecatedByLabel,
            color: "d73a49"
          })
        });
      } catch (error) {
        // Label might already exist, continue
      }
      
      // Add the labels to the source issue
      await this.fetchFromGitHub(`/issues/${sourceIssue.number}/labels`, {
        method: "POST",
        body: JSON.stringify({
          labels: [LabelNames.DEPRECATED, mergeLabel, deprecatedByLabel]
        })
      });
      
      return {
        success: true,
        sourceObjectId: objectId,
        targetObjectId: targetId,
        reason
      };
    } catch (error) {
      // If we fail, try to restore stored-object label
      try {
        await this.fetchFromGitHub(`/issues/${sourceIssue.number}/labels`, {
          method: "POST",
          body: JSON.stringify({
            labels: [LabelNames.STORED_OBJECT]
          })
        });
      } catch (restoreError) {
        console.error(`Failed to restore label: ${restoreError.message}`);
      }
      
      throw new Error(`Failed to deprecate object: ${error.message}`);
    }
  }

  // Find duplicates in the repository
  async findDuplicates(): Promise<Record<string, any[]>> {
    try {
      // Get all issues with stored-object label
      const issues = await this.fetchFromGitHub<Array<{
        number: number;
        labels: Array<{ name: string }>;
      }>>("/issues", {
        method: "GET",
        params: {
          labels: LabelNames.STORED_OBJECT,
          state: "all",
        },
      });
      
      // Group by UID
      const issuesByUid: Record<string, any[]> = {};
      
      for (const issue of issues) {
        try {
          const objectId = this._extractObjectIdFromLabels(issue);
          const uid = `${LabelNames.UID_PREFIX}${objectId}`;
          if (!issuesByUid[uid]) {
            issuesByUid[uid] = [];
          }
          issuesByUid[uid].push(issue);
        } catch (error) {
          continue; // Skip issues without proper UID label
        }
      }
      
      // Filter to only those with duplicates
      const duplicates: Record<string, any[]> = {};
      for (const [uid, issues] of Object.entries(issuesByUid)) {
        if (issues.length > 1) {
          duplicates[uid] = issues;
        }
      }
      
      return duplicates;
    } catch (error) {
      console.warn(`Error finding duplicates: ${(error as Error).message}`);
      return {};
    }
  }

  // Deduplicate an object
  async deduplicateObject(objectId: string, canonicalId?: string): Promise<{
    success: boolean;
    canonicalObjectId?: string;
    canonicalIssue?: number;
    duplicatesProcessed?: number;
    results?: any[];
    message?: string;
  }> {
    try {
      // Find all issues with this UID that are active
      const issues = await this.fetchFromGitHub<Array<{
        number: number;
        created_at: string;
      }>>("/issues", {
        method: "GET",
        params: {
          labels: `${LabelNames.UID_PREFIX}${objectId},${LabelNames.STORED_OBJECT}`,
          state: "all",
        },
      });
      
      if (!issues || issues.length <= 1) {
        return { success: true, message: "No duplicates found" };
      }
      
      // Sort issues by creation date (oldest first)
      const sortedIssues = issues.sort((a, b) => {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      });
      
      // Select canonical issue
      let canonicalIssue;
      
      if (canonicalId && canonicalId !== objectId) {
        // If user specified a different canonical ID, find its issue
        const canonicalIssues = await this.fetchFromGitHub<Array<{ number: number }>>("/issues", {
          method: "GET",
          params: {
            labels: `${LabelNames.UID_PREFIX}${canonicalId},${LabelNames.STORED_OBJECT}`,
            state: "all",
          },
        });
        
        if (!canonicalIssues || canonicalIssues.length === 0) {
          throw new Error(`Specified canonical object ${canonicalId} not found`);
        }
        
        canonicalIssue = canonicalIssues[0];
      } else {
        // Default to oldest issue for this object ID
        canonicalIssue = sortedIssues[0];
        canonicalId = objectId;
      }
      
      const canonicalIssueNumber = canonicalIssue.number;
      console.info(`Selected issue #${canonicalIssueNumber} as canonical for ${objectId}`);
      
      // Process duplicates
      const results = [];
      
      for (const issue of sortedIssues) {
        // Skip the canonical issue
        if (issue.number === canonicalIssueNumber) {
          continue;
        }
        
        console.info(`Processing duplicate issue #${issue.number}`);
        
        // Deprecate as duplicate
        const result = await this.deprecateIssue(
          issue.number,
          canonicalIssueNumber,
          DeprecationReason.DUPLICATE
        );
        
        results.push(result);
      }
      
      return {
        success: true,
        canonicalObjectId: canonicalId,
        canonicalIssue: canonicalIssueNumber,
        duplicatesProcessed: results.length,
        results
      };
    } catch (error) {
      throw new Error(`Error deduplicating object: ${error.message}`);
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
      console.warn(`Error finding aliases: ${(error as Error).message}`);
      return {};
    }
  }

  // Deprecate a specific issue
  private async deprecateIssue(
    issueNumber: number,
    targetIssueNumber: number,
    reason: DeprecationReason
  ): Promise<{
    success: boolean;
    sourceIssue: number;
    sourceObjectId: string;
    targetIssue: number;
    targetObjectId: string;
    reason: string;
  }> {
    try {
      // Get source issue
      const sourceIssue = await this.fetchFromGitHub<{
        labels: Array<{ name: string }>;
      }>(`/issues/${issueNumber}`);
      
      // Get target issue
      const targetIssue = await this.fetchFromGitHub<{
        labels: Array<{ name: string }>;
      }>(`/issues/${targetIssueNumber}`);
      
      // Get object IDs from both issues
      const sourceObjectId = this._extractObjectIdFromLabels(sourceIssue);
      const targetObjectId = this._extractObjectIdFromLabels(targetIssue);
      
      // Make sure GH_STORE label is on both issues
      try {
        const sourceIssueLabels = await this.fetchFromGitHub<Array<{ name: string }>>(`/issues/${issueNumber}/labels`);
        if (!sourceIssueLabels.some(label => label.name === LabelNames.GH_STORE)) {
          await this.fetchFromGitHub(`/issues/${issueNumber}/labels`, {
            method: "POST",
            body: JSON.stringify({
              labels: [LabelNames.GH_STORE]
            })
          });
        }
        
        const targetIssueLabels = await this.fetchFromGitHub<Array<{ name: string }>>(`/issues/${targetIssueNumber}/labels`);
        if (!targetIssueLabels.some(label => label.name === LabelNames.GH_STORE)) {
          await this.fetchFromGitHub(`/issues/${targetIssueNumber}/labels`, {
            method: "POST",
            body: JSON.stringify({
              labels: [LabelNames.GH_STORE]
            })
          });
        }
      } catch (error) {
        console.warn(`Failed to ensure GH_STORE label: ${error.message}`);
      }
      
      // Remove stored-object label from source
      if (sourceIssue.labels.some(label => label.name === LabelNames.STORED_OBJECT)) {
        await this.fetchFromGitHub(`/issues/${issueNumber}/labels/${LabelNames.STORED_OBJECT}`, {
          method: "DELETE"
        });
      }
      
      // Add merge and deprecated labels
      try {
        // Create labels if they don't exist
        const mergeLabel = `${LabelNames.MERGED_INTO_PREFIX}${targetObjectId}`;
        const deprecatedByLabel = `${LabelNames.DEPRECATED_BY_PREFIX}${targetIssueNumber}`;
        
        try {
          await this.fetchFromGitHub("/labels", {
            method: "POST",
            body: JSON.stringify({
              name: mergeLabel,
              color: "d73a49"
            })
          });
        } catch (error) {
          // Label might already exist, continue
        }
        
        try {
          await this.fetchFromGitHub("/labels", {
            method: "POST",
            body: JSON.stringify({
              name: deprecatedByLabel,
              color: "d73a49"
            })
          });
        } catch (error) {
          // Label might already exist, continue
        }
        
        try {
          await this.fetchFromGitHub("/labels", {
            method: "POST",
            body: JSON.stringify({
              name: LabelNames.DEPRECATED,
              color: "999999"
            })
          });
        } catch (error) {
          // Label might already exist, continue
        }
        
        // Add labels to source issue
        await this.fetchFromGitHub(`/issues/${issueNumber}/labels`, {
          method: "POST",
          body: JSON.stringify({
            labels: [LabelNames.DEPRECATED, mergeLabel, deprecatedByLabel]
          })
        });
      } catch (error) {
        // If we fail, try to restore stored-object label
        try {
          await this.fetchFromGitHub(`/issues/${issueNumber}/labels`, {
            method: "POST",
            body: JSON.stringify({
              labels: [LabelNames.STORED_OBJECT]
            })
          });
        } catch (restoreError) {
          console.error(`Failed to restore label: ${restoreError.message}`);
        }
        
        throw new Error(`Failed to deprecate issue: ${error.message}`);
      }
      
      return {
        success: true,
        sourceIssue: issueNumber,
        sourceObjectId,
        targetIssue: targetIssueNumber,
        targetObjectId,
        reason
      };
    } catch (error) {
      throw new Error(`Failed to deprecate issue: ${error.message}`);
    }
  }

  // Helper to extract object ID from labels (specialized version for canonicalization)
  private _extractObjectIdFromLabels(issue: { labels: Array<{ name: string }> }): string {
    for (const label of issue.labels) {
      if (label.name.startsWith(LabelNames.UID_PREFIX)) {
        return label.name.slice(LabelNames.UID_PREFIX.length);
      }
    }
    
    throw new Error(`No UID label found with prefix ${LabelNames.UID_PREFIX}`);
  }

  // Deep merge utility for combining objects
  private _deepMerge(base: any, update: any): any {
    // Return update directly for non-objects
    if (typeof base !== 'object' || base === null ||
        typeof update !== 'object' || update === null) {
      return update;
    }

    // Handle arrays
    if (Array.isArray(base) && Array.isArray(update)) {
      return update; // Replace arrays by default
    }

    // Handle objects
    const result = { ...base };
    
    for (const key in update) {
      if (Object.prototype.hasOwnProperty.call(update, key)) {
        if (key in base && typeof base[key] === 'object' && typeof update[key] === 'object') {
          result[key] = this._deepMerge(base[key], update[key]);
        } else {
          result[key] = update[key];
        }
      }
    }
    
    return result;
  }
}
