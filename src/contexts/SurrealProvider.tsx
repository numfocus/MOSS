import React, {
  useState,
  useEffect,
  useContext,
  createContext,
  useCallback,
  useMemo,
  useRef,
} from "react";
import { Surreal } from "surrealdb";
import { surrealdbWasmEngines } from "@surrealdb/wasm";

interface SurrealContextType {
  db: Surreal | null;
  connectionStatus: "disconnected" | "connecting" | "connected" | "error";
  error: Error | null;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  query: (sql: string, vars?: Record<string, any>) => Promise<any>;
}

export const SurrealContext = createContext<SurrealContextType | undefined>(
  undefined,
);

interface SurrealProviderProps {
  children: React.ReactNode;
  endpoint: string;
  namespace?: string;
  database?: string;
}

export const SurrealProvider: React.FC<SurrealProviderProps> = ({
  children,
  endpoint,
  namespace,
  database,
}) => {
  const dbInstanceRef = useRef<Surreal | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<
    "disconnected" | "connecting" | "connected" | "error"
  >("disconnected");
  const [error, setError] = useState<Error | null>(null);

  const connectDb = useCallback(async () => {
    if (connectionStatus === 'connecting' || connectionStatus === 'connected') {
        console.log(`SurrealProvider: connectDb skipped, status is ${connectionStatus}.`);
        return;
    }
    
    setConnectionStatus("connecting");
    console.log('SurrealProvider: Attempting connect...');

    if (dbInstanceRef.current) {
        console.log("SurrealProvider: Disconnecting existing instance before reconnecting.");
        await dbInstanceRef.current.close().catch(err => {
          console.error("SurrealProvider: Error closing old DB instance:", err);
          setError(err instanceof Error ? err : new Error("Error closing old DB instance"));
          setConnectionStatus("error");
        });
        dbInstanceRef.current = null;
    }

    try {
      const newDb = new Surreal({ engines: surrealdbWasmEngines() });
      console.log(`SurrealProvider: Connecting to: ${endpoint}`);
      await newDb.connect(endpoint);
      console.log('SurrealProvider: Connected to endpoint.');

      if (namespace && database) {
        console.log(`SurrealProvider: Using namespace: ${namespace}, database: ${database}`);
        await newDb.use({ namespace, database });
        console.log('SurrealProvider: Used namespace/database.');
      }

      dbInstanceRef.current = newDb;
      setConnectionStatus("connected");
      setError(null);
      console.log('SurrealProvider: Connection successful, state updated.');


    } catch (err) {
      console.error("SurrealProvider: Connection Error:", err);
      dbInstanceRef.current = null;
      const error = err instanceof Error ? err : new Error("Unknown connection error");
      setError(error);
      setConnectionStatus("error");
    }
  }, [endpoint, namespace, database]);

const disconnectDb = useCallback(async () => {
  if (dbInstanceRef.current) {
    console.log("SurrealProvider: Attempting disconnect...");
    try {
      await dbInstanceRef.current.close();
      console.log("SurrealProvider: DB connection closed successfully via disconnectDb.");
    } catch (err) {
      console.error("SurrealProvider: Error closing DB via disconnectDb:", err);
      setError(err instanceof Error ? err : new Error("Error closing DB"));
      setConnectionStatus("error");
    } finally {
      dbInstanceRef.current = null;
      setConnectionStatus("disconnected");
      console.log("SurrealProvider: Instance ref cleared, state set to disconnected.");
    }
  } else {
    console.log("SurrealProvider: disconnectDb called but no instance ref found.");
  }
}, []);
  
useEffect(() => {
  return () => {
    console.log("SurrealProvider Effect Cleanup: Unmounting or params changed. Running disconnectDb.");
    disconnectDb();
    console.log("SurrealProvider Effect Cleanup: Disconnect attempt finished.");
  };
}, []);

  const query = useCallback(async (sql: string, vars?: Record<string, any>) => {
    if (connectionStatus !== 'connected') {
      throw new Error(`Cannot query: SurrealDB is not connected. Status: ${connectionStatus}`);
    }
    if (!dbInstanceRef.current) {
      throw new Error('Database instance is not available.');
    }
    try {
      return await dbInstanceRef.current.query(sql, vars);
    } catch (queryError) {
      console.warn('Error during query:', queryError);
      throw queryError;
    }
  }, [connectionStatus]);


  const contextValue: SurrealContextType = useMemo(
      () => ({
          db: dbInstanceRef.current,
          connectionStatus,
          error,
          connect: connectDb,
          disconnect: disconnectDb,
          query,
      }), [connectionStatus, error, connectDb, disconnectDb, query]
  ); 

  return (
    <SurrealContext.Provider value={contextValue}>
      {children}
    </SurrealContext.Provider>
  );
};

export const useSurreal = () => {
    const context = useContext(SurrealContext);
    if (context === undefined) {
        throw new Error('useSurreal must be used within a SurrealProvider');
    }
    return context;
};
