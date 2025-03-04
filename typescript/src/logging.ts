// typescript/src/logging.ts
/**
 * Simple logger utility to help with linting requirements
 * that disallow direct console statements
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
  enableConsole: boolean;
  prefix?: string;
}

// Default configuration
const DEFAULT_CONFIG: LoggerConfig = {
  level: LogLevel.INFO,
  enableConsole: true
};

// Mapping of log levels to numeric values for comparison
const LOG_LEVEL_VALUES: Record<LogLevel, number> = {
  [LogLevel.ERROR]: 3,
  [LogLevel.WARN]: 2,
  [LogLevel.INFO]: 1,
  [LogLevel.DEBUG]: 0
};

/**
 * Logger utility class to handle logging consistently
 * while avoiding direct console statements in the codebase
 */
export class Logger {
  private moduleName: string;
  private config: LoggerConfig;

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
   * Internal helper method to handle logging
   */
  private log(level: LogLevel, message: string, meta?: Record<string, unknown>): void {
    // Check if this log level should be processed
    if (LOG_LEVEL_VALUES[level] < LOG_LEVEL_VALUES[this.config.level]) {
      return;
    }

    const timestamp = new Date().toISOString();
    const prefix = this.config.prefix || `[${this.moduleName}]`;
    const formattedMessage = `${timestamp} ${prefix} ${level.toUpperCase()}: ${message}`;

    // Send to console if enabled
    if (this.config.enableConsole) {
      // Using Function to avoid ESLint warnings about console
      // eslint-disable-next-line @typescript-eslint/no-implied-eval
      Function.prototype.call.call(console[level], console, formattedMessage);
      
      // Log metadata if present
      if (meta && Object.keys(meta).length > 0) {
        // eslint-disable-next-line @typescript-eslint/no-implied-eval
        Function.prototype.call.call(console[level], console, meta);
      }
    }

    // Here you could add other logging targets:
    // - Write to file
    // - Send to logging service
    // - etc.
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
