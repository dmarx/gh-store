// typescript/src/types.ts
export type Json = { [key: string]: Json } | Json[] | string | number | boolean | null;

export interface ObjectMeta {
  objectId: string;
  label: string;
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
