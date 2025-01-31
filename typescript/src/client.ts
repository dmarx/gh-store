// typescript/src/client.ts
import { StoredObject, ObjectMeta, GitHubStoreConfig, Json, CommentPayload } from './types';
import { IssueCache, CacheConfig } from './cache';
import { CLIENT_VERSION } from './version';

interface GitHubIssue {
  number: number;
  body: string;
  created_at: string;
  updated_at: string;
  labels: Array<{ name: string }>;
  state?: string;
}

export class GitHubStoreClient {
  private token: string;
  private repo: string;
  private config: Required<GitHubStoreConfig>;
  private cache: IssueCache;

  constructor(
    token: string,
    repo: string,
    config: GitHubStoreConfig & { cache?: CacheConfig } = {}
  ) {
    this.token = token;
    this.repo = repo;
    this.config = {
      baseLabel: config.baseLabel ?? "stored-object",
      uidPrefix: config.uidPrefix ?? "UID:",
      reactions: {
        processed: config.reactions?.processed ?? "+1",
        initialState: config.reactions?.initialState ?? "rocket",
      },
    };
    this.cache = new IssueCache(config.cache);
  }

  private async fetchFromGitHub<T>(path: string, options: RequestInit & { params?: Record<string, string> } = {}): Promise<T> {
    const url = new URL(`https://api.github.com/repos/${this.repo}${path}`);
    
    if (options.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        url.searchParams.append(key, value);
      });
      delete options.params;
    }

    const response = await fetch(url.toString(), {
      ...options,
      headers: {
        "Authorization": `token ${this.token}`,
        "Accept": "application/vnd.github.v3+json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status}`);
    }

    return response.json() as Promise<T>;
  }

  private createCommentPayload(data: Json, type?: string): CommentPayload {
    const payload: CommentPayload = {
      _data: data,
      _meta: {
        client_version: CLIENT_VERSION,
        timestamp: new Date().toISOString(),
        update_mode: "append"
      }
    };
    
    if (type) {
      payload.type = type;
    }
    
    return payload;
  }

  async getObject(objectId: string): Promise<StoredObject> {
    // Try to get issue number from cache
    const cachedIssueNumber = this.cache.get(objectId);
    let issue: GitHubIssue | undefined;

    if (cachedIssueNumber) {
      // Try to fetch directly using cached issue number
      try {
        issue = await this.fetchFromGitHub<GitHubIssue>(`/issues/${cachedIssueNumber}`);

        // Verify it's the correct issue
        if (!this._verifyIssueLabels(issue, objectId)) {
          this.cache.remove(objectId);
          issue = undefined;
        }
      } catch (error) {
        // If issue not found, remove from cache
        this.cache.remove(objectId);
      }
    }

    if (!issue) {
      // Fall back to searching by labels
      const issues = await this.fetchFromGitHub<GitHubIssue[]>("/issues", {
        method: "GET",
        params: {
          labels: [this.config.baseLabel, `${this.config.uidPrefix}${objectId}`].join(","),
          state: "closed",
        },
      });

      if (!issues || issues.length === 0) {
        throw new Error(`No object found with ID: ${objectId}`);
      }

      issue = issues[0];
    }

    if (!issue?.body) {
      throw new Error(`Invalid issue data received for ID: ${objectId}`);
    }

    const data = JSON.parse(issue.body) as Json;
    const createdAt = new Date(issue.created_at);
    const updatedAt = new Date(issue.updated_at);

    // Update cache
    this.cache.set(objectId, issue.number, { createdAt, updatedAt });

    const meta: ObjectMeta = {
      objectId,
      label: `${this.config.uidPrefix}${objectId}`,
      createdAt,
      updatedAt,
      version: await this._getVersion(issue.number),
    };

    return { meta, data };
  }

  async createObject(objectId: string, data: Json): Promise<StoredObject> {
    const uidLabel = `${this.config.uidPrefix}${objectId}`;
    
    const issue = await this.fetchFromGitHub<{
      number: number;
      created_at: string;
      updated_at: string;
      html_url: string;
    }>("/issues", {
      method: "POST",
      body: JSON.stringify({
        title: `Stored Object: ${objectId}`,
        body: JSON.stringify(data, null, 2),
        labels: [this.config.baseLabel, uidLabel]
      })
    });

    // Add to cache immediately
    this.cache.set(objectId, issue.number, {
      createdAt: new Date(issue.created_at),
      updatedAt: new Date(issue.updated_at)
    });

    // Create and add initial state comment
    const initialState = this.createCommentPayload(data, "initial_state");
    
    const comment = await this.fetchFromGitHub<{ id: number }>(`/issues/${issue.number}/comments`, {
      method: "POST",
      body: JSON.stringify({
        body: JSON.stringify(initialState, null, 2)
      })
    });

    await this.fetchFromGitHub(`/issues/comments/${comment.id}/reactions`, {
      method: "POST",
      body: JSON.stringify({ content: this.config.reactions.processed })
    });

    await this.fetchFromGitHub(`/issues/comments/${comment.id}/reactions`, {
      method: "POST",
      body: JSON.stringify({ content: this.config.reactions.initialState })
    });

    await this.fetchFromGitHub(`/issues/${issue.number}`, {
      method: "PATCH",
      body: JSON.stringify({ state: "closed" })
    });

    const meta: ObjectMeta = {
      objectId,
      label: uidLabel,
      createdAt: new Date(issue.created_at),
      updatedAt: new Date(issue.updated_at),
      version: 1
    };

    return { meta, data };
  }
  
  private _verifyIssueLabels(issue: { labels: Array<{ name: string }> }, objectId: string): boolean {
    const expectedLabels = new Set([
      this.config.baseLabel,
      `${this.config.uidPrefix}${objectId}`
    ]);

    return issue.labels.some(label => expectedLabels.has(label.name));
  }
  
  async updateObject(objectId: string, changes: Json): Promise<StoredObject> {
    // Get the object's issue first
    const issues = await this.fetchFromGitHub<Array<{
      number: number;
      state: string;
    }>>("/issues", {
      method: "GET",
      params: {
        labels: [this.config.baseLabel, `${this.config.uidPrefix}${objectId}`].join(","),
        state: "all",
      },
    });

    if (!issues || issues.length === 0) {
      throw new Error(`No object found with ID: ${objectId}`);
    }

    const issue = issues[0];
    
    // Create update payload with metadata
    const updatePayload = this.createCommentPayload(changes);

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

    // Return current state (before update is processed)
    return this.getObject(objectId);
  }

  async listAll(): Promise<Record<string, StoredObject>> {
    const issues = await this.fetchFromGitHub<Array<{
      number: number;
      body: string;
      created_at: string;
      updated_at: string;
      labels: Array<{ name: string }>;
    }>>("/issues", {
      method: "GET",
      params: {
        labels: this.config.baseLabel,
        state: "closed",
      },
    });

    const objects: Record<string, StoredObject> = {};

    for (const issue of issues) {
      // Skip archived objects
      if (issue.labels.some((label) => label.name === "archived")) {
        continue;
      }

      try {
        const objectId = this._getObjectIdFromLabels(issue);
        const data = JSON.parse(issue.body) as Json;

        const meta: ObjectMeta = {
          objectId,
          label: objectId,
          createdAt: new Date(issue.created_at),
          updatedAt: new Date(issue.updated_at),
          version: await this._getVersion(issue.number),
        };

        objects[objectId] = { meta, data };
      } catch (error) {
        // Skip issues that can't be processed
        continue;
      }
    }

    return objects;
  }

  async listUpdatedSince(timestamp: Date): Promise<Record<string, StoredObject>> {
    const issues = await this.fetchFromGitHub<Array<{
      number: number;
      body: string;
      created_at: string;
      updated_at: string;
      labels: Array<{ name: string }>;
    }>>("/issues", {
      method: "GET",
      params: {
        labels: this.config.baseLabel,
        state: "closed",
        since: timestamp.toISOString(),
      },
    });

    const objects: Record<string, StoredObject> = {};

    for (const issue of issues) {
      if (issue.labels.some((label) => label.name === "archived")) {
        continue;
      }

      try {
        const objectId = this._getObjectIdFromLabels(issue);
        const data = JSON.parse(issue.body) as Json;
        const updatedAt = new Date(issue.updated_at);

        if (updatedAt > timestamp) {
          const meta: ObjectMeta = {
            objectId,
            label: objectId,
            createdAt: new Date(issue.created_at),
            updatedAt,
            version: await this._getVersion(issue.number),
          };

          objects[objectId] = { meta, data };
        }
      } catch (error) {
        // Skip issues that can't be processed
        continue;
      }
    }

    return objects;
  }

  async getObjectHistory(objectId: string): Promise<Array<{
    timestamp: string;
    type: string;
    data: Json;
    commentId: number;
  }>> {
    const issues = await this.fetchFromGitHub<Array<{
      number: number;
      labels: Array<{ name: string }>;
    }>>("/issues", {
      method: "GET",
      params: {
        labels: [this.config.baseLabel, `${this.config.uidPrefix}${objectId}`].join(","),
        state: "all",
      },
    });

    if (!issues || issues.length === 0) {
      throw new Error(`No object found with ID: ${objectId}`);
    }

    const issue = issues[0];
    const comments = await this.fetchFromGitHub<Array<{
      id: number;
      created_at: string;
      body: string;
    }>>(`/issues/${issue.number}/comments`);
    
    const history = [];

    for (const comment of comments) {
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

        history.push({
          timestamp: comment.created_at,
          type: commentType,
          data: commentData,
          commentId: comment.id,
        });
      } catch (error) {
        // Skip comments with invalid JSON
        continue;
      }
    }

    return history;
  }

  private async _getVersion(issueNumber: number): Promise<number> {
    const comments = await this.fetchFromGitHub<Array<unknown>>(`/issues/${issueNumber}/comments`);
    return comments.length + 1;
  }

  private _getObjectIdFromLabels(issue: { labels: Array<{ name: string }> }): string {
      for (const label of issue.labels) {
        if (label.name !== this.config.baseLabel && label.name.startsWith(this.config.uidPrefix)) {
          return label.name.slice(this.config.uidPrefix.length);
        }
      }
      throw new Error(`No UID label found with prefix ${this.config.uidPrefix}`);
    }
  }
