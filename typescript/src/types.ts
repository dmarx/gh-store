// typescript/src/types.ts
export type Json = { [key: string]: Json } | Json[] | string | number | boolean | null;

export interface ObjectMeta {
  objectId: string;
  label: string;
  issueNumber: number;  // Added field to track GitHub issue number
  createdAt: Date;
  updatedAt: Date;
  version: number;
}

export interface StoredObject {
  meta: ObjectMeta;
  data: Json;
}

export interface GitHubStoreConfig {
  baseLabel?: string;
  uidPrefix?: string;
  reactions?: {
    processed?: string;
    initialState?: string;
  };
}

export interface CommentMeta {
  client_version: string;
  timestamp: string;
  update_mode: string;
  issue_number: number;  // Added field to track GitHub issue number
}

export interface CommentPayload {
  _data: Json;
  _meta: CommentMeta;
  type?: string;
}

/* Constants */

export enum LabelNames {
  GH_STORE = "gh-store",
  STORED_OBJECT = "stored-object",
  DEPRECATED = "deprecated-object",
  UID_PREFIX = "UID:",
  ALIAS_TO_PREFIX = "ALIAS-TO:"
}
