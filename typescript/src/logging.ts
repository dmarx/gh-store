// typescript/src/logging.ts
/**
 * Simple logger utility that avoids console statements
 * but collects messages for potential later use
 */

// Log levels
export enum LogLevel {
  ERROR = 'error',
  WARN = 'warn',
  INFO = 'info',
  DEBUG = 'debug'
}

// Logger configuration
export interface LoggerConfig {
  level: LogLevel;
  silent?: boolean;
  prefix?: string;
}

// Log entry structure
export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  module: string;
  message: string;
  metadata?: Record<string, unknown>;
}

// Default configuration
const DEFAULT_CONFIG: LoggerConfig = {
  level: LogLevel.INFO,
  silent: false
};

// Mapping of log levels to numeric values for comparison
const LOG_LEVEL_VALUES: Record<LogLevel, number> = {
  [LogLevel.ERROR]: 3,
  [LogLevel.WARN]: 2,
  [LogLevel.INFO]: 1,
  [LogLevel.DEBUG]: 0
};

/**
 * Logger utility class that avoids direct console usage
 */
export class Logger {
  private moduleName: string;
  private config: LoggerConfig;
  private entries: LogEntry[] = [];

  /**
   * Create a new logger
   * @param moduleName Name of the module using this logger
   * @param config Optional configuration
   */
  constructor(moduleName: string, config: Partial<LoggerConfig> = {}) {
    this.moduleName = moduleName;
    this.config = {
      ...DEFAULT_CONFIG,
      ...config
    };
  }

  /**
   * Log a debug message
   * @param message Message content
   * @param meta Optional metadata
   */
  debug(message: string, meta?: Record<string, unknown>): void {
    this.log(LogLevel.DEBUG, message, meta);
  }

  /**
   * Log an info message
   * @param message Message content
   * @param meta Optional metadata
   */
  info(message: string, meta?: Record<string, unknown>): void {
    this.log(LogLevel.INFO, message, meta);
  }

  /**
   * Log a warning message
   * @param message Message content
   * @param meta Optional metadata
   */
  warn(message: string, meta?: Record<string, unknown>): void {
    this.log(LogLevel.WARN, message, meta);
  }

  /**
   * Log an error message
   * @param message Message content
   * @param meta Optional metadata
   */
  error(message: string, meta?: Record<string, unknown>): void {
    this.log(LogLevel.ERROR, message, meta);
  }

  /**
   * Internal helper method to record logs
   */
  private log(level: LogLevel, message: string, meta?: Record<string, unknown>): void {
    // Check if this log level should be processed
    if (LOG_LEVEL_VALUES[level] < LOG_LEVEL_VALUES[this.config.level]) {
      return;
    }

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      module: this.moduleName,
      message,
      metadata: meta
    };

    this.entries.push(entry);

    // In production, you would implement external logging here
    // For example:
    // - Write to a database
    // - Send to a logging service
    // - Write to a file
  }

  /**
   * Get collected log entries
   */
  getEntries(): LogEntry[] {
    return [...this.entries];
  }

  /**
   * Clear collected log entries
   */
  clearEntries(): void {
    this.entries = [];
  }

  /**
   * Configure the logger
   * @param config Configuration options to apply
   */
  configure(config: Partial<LoggerConfig>): void {
    this.config = {
      ...this.config,
      ...config
    };
  }

  /**
   * Get the current logger configuration
   */
  getConfig(): LoggerConfig {
    return { ...this.config };
  }
}
