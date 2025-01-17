// typescript/src/client.ts
import { StoredObject, ObjectMeta, GitHubStoreConfig, Json } from './types';

export class GitHubStoreClient {
  private token: string;
  private repo: string;
  private config: Required<GitHubStoreConfig>;

  constructor(
    token: string,
    repo: string,
    config: GitHubStoreConfig = {}
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

  async getObject(objectId: string): Promise<StoredObject> {
    // Query for issue with matching labels
    const issues = await this.fetchFromGitHub<Array<{
      number: number;
      body: string;
      created_at: string;
      updated_at: string;
      labels: Array<{ name: string }>;
    }>>("/issues", {
      method: "GET",
      params: {
        labels: [this.config.baseLabel, `${this.config.uidPrefix}${objectId}`].join(","),
        state: "closed",
      },
    });

    if (!issues || issues.length === 0) {
      throw new Error(`No object found with ID: ${objectId}`);
    }

    const issue = issues[0];
    const data = JSON.parse(issue.body) as Json;

    const meta: ObjectMeta = {
      objectId,
      label: `${this.config.uidPrefix}${objectId}`,
      createdAt: new Date(issue.created_at),
      updatedAt: new Date(issue.updated_at),
      version: await this._getVersion(issue.number),
    };

    return { meta, data };
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
        const obj = await this._getObjectByNumber(issue.number);
        objects[objectId] = obj;
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
        const obj = await this._getObjectByNumber(issue.number);

        if (obj.meta.updatedAt > timestamp) {
          objects[objectId] = obj;
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
        const update = JSON.parse(comment.body) as { type?: string; data?: Json };
        history.push({
          timestamp: comment.created_at,
          type: update.type || "update",
          data: update.data || update,
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

  private async _getObjectByNumber(issueNumber: number): Promise<StoredObject> {
    const issue = await this.fetchFromGitHub<{
      body: string;
      created_at: string;
      updated_at: string;
      labels: Array<{ name: string }>;
    }>(`/issues/${issueNumber}`);
    
    const objectId = this._getObjectIdFromLabels(issue);
    const data = JSON.parse(issue.body) as Json;

    const meta: ObjectMeta = {
      objectId,
      label: objectId,
      createdAt: new Date(issue.created_at),
      updatedAt: new Date(issue.updated_at),
      version: await this._getVersion(issueNumber),
    };

    return { meta, data };
  }
}
