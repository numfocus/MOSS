import { createContext, useContext } from 'react';
import { Surreal } from 'surrealdb';

interface SurrealContextType {
  db: Surreal | null;
  connectionStatus: "disconnected" | "connecting" | "connected" | "error";
  error: Error | null;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  query: (sql: string, vars?: Record<string, any>) => Promise<any>;
}

export const SurrealContext = createContext<SurrealContextType | undefined>(undefined);

export const useSurrealContext = () => {
  const context = useContext(SurrealContext);
  if (!context) {
    throw new Error('useSurrealContext must be used within a SurrealProvider');
  }
  return context;
};
