/**
 * Парсер аргументов командной строки
 */

export interface CLIArgs {
  apiKey?: string;
}

export function parseArgs(argv: string[]): CLIArgs {
  const args: CLIArgs = {};
  
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    
    if (arg === '--api-key' || arg === '-k') {
      args.apiKey = argv[++i];
    } else if (arg.startsWith('--api-key=')) {
      args.apiKey = arg.split('=')[1];
    } else if (arg.startsWith('-k=')) {
      args.apiKey = arg.split('=')[1];
    }
  }
  
  return args;
}
