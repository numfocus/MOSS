import { useState, useEffect, useCallback, useContext } from 'react';
import Surreal from 'surrealdb';
import { SurrealContext } from '@/contexts/SurrealProvider';

interface SurrealHook {
  db: Surreal | null;
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  query: (query: string, vars?: Record<string, any>) => Promise<any>;
  error: Error | null;
  eventLog: string[];
  logEvent: (event: string) => void;
}

export const useSurreal = (): SurrealHook => {
  const context = useContext(SurrealContext);
  if (!context) {
    throw new Error("useSurreal must be used within a SurrealProvider");
  }

  const { db: dbFromContext, connectionStatus: connectionStatusFromContext, error: errorFromContext, connect: connectFromContext, disconnect: disconnectFromContext, query: queryFromContext } = context;

  const [db, setDb] = useState<Surreal | null>(dbFromContext);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>(connectionStatusFromContext);
  const [error, setError] = useState<Error | null>(errorFromContext);
  const [eventLog, setEventLog] = useState<string[]>([]);

  const logEvent = useCallback((event: string) => {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = `[${timestamp}] ${event}`;
    setEventLog((prevLog) => [...prevLog, logEntry]);
  }, []);

  const connect = useCallback(async () => {
    connectFromContext();
  }, [connectFromContext]);

  const disconnect = useCallback(async () => {
    disconnectFromContext();
  }, [disconnectFromContext]);

  const query = useCallback(async (query: string, vars?: Record<string, any>) => {
    return await queryFromContext(query, vars);
  }, [queryFromContext]);

  useEffect(() => {
    setDb(dbFromContext);
    setConnectionStatus(connectionStatusFromContext);
    setError(errorFromContext);
  }, [dbFromContext, connectionStatusFromContext, errorFromContext]);

  return { db, connectionStatus, connect, disconnect, query, error, eventLog, logEvent };
};
