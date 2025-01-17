// typescript/src/config.ts
export interface StoreConfig {
  // Base configuration
  baseLabel: string;
  uidPrefix: string;
  
  // Reaction settings
  reactions: {
    processed: string;
    initialState: string;
  };
  
  // API retry settings
  retries: {
    maxAttempts: number;
    backoffFactor: number;
  };
  
  // Rate limiting
  rateLimit: {
    maxRequestsPerHour: number;
  };
}

export const DEFAULT_CONFIG: StoreConfig = {
  baseLabel: "stored-object",
  uidPrefix: "UID:",
  reactions: {
    processed: "+1",
    initialState: "rocket"
  },
  retries: {
    maxAttempts: 3,
    backoffFactor: 2
  },
  rateLimit: {
    maxRequestsPerHour: 1000
  }
};

export function mergeConfig(userConfig: Partial<StoreConfig>): StoreConfig {
  return {
    ...DEFAULT_CONFIG,
    ...userConfig,
    reactions: {
      ...DEFAULT_CONFIG.reactions,
      ...userConfig.reactions
    },
    retries: {
      ...DEFAULT_CONFIG.retries,
      ...userConfig.retries
    },
    rateLimit: {
      ...DEFAULT_CONFIG.rateLimit,
      ...userConfig.rateLimit
    }
  };
}

// Helper to validate token format
export function validateToken(token: string): boolean {
  // Check if it's a valid GitHub token format
  return /^gh[ps]_[a-zA-Z0-9]{36}$/.test(token);
}

// Helper to validate repository format
export function validateRepo(repo: string): boolean {
  return /^[\w-]+\/[\w-]+$/.test(repo);
}

// Error types for configuration issues
export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

export class TokenError extends ConfigError {
  constructor(message = 'Invalid GitHub token format') {
    super(message);
    this.name = 'TokenError';
  }
}

export class RepoError extends ConfigError {
  constructor(message = 'Invalid repository format. Use owner/repo') {
    super(message);
    this.name = 'RepoError';
  }
}
