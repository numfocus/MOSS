import React, { useState, useCallback, useEffect } from 'react';
import { useSurreal } from '@/hooks/useSurreal';
import { initializeDatabase, populateGithubTables } from '@/utils/db_ini';
import { Surreal } from 'surrealdb';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import MessageDisplay from '@/components/MessageDisplay';

interface DevToolsProps {
  db: Surreal | null;
  isDbBusy: boolean;
  setIsDbBusy: React.Dispatch<React.SetStateAction<boolean>>;
}

const DevTools: React.FC<DevToolsProps> = ({ db, isDbBusy, setIsDbBusy }) => {
  const { query, connectionStatus, connect, eventLog, logEvent } = useSurreal();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queryText, setQueryText] = useState<string>('');
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    logEvent('DevTools component mounted.');
    return () => {
      logEvent('DevTools component unmounted.');
    };
  }, [logEvent]);

  const handleInitializeDB = useCallback(async () => {
    if (connectionStatus !== 'connected' || !db) {
      setError("Database not connected. Cannot initialize.");
      logEvent("Initialize DB: DB not connected");
      return;
    }
    setIsDbBusy(true);
    setError(null);
    logEvent("Initializing DB schema...");
    try {
      await initializeDatabase(db);
      logEvent("Database schema initialized successfully!");
      setMessage("Database schema initialized successfully!");
    } catch (err) {
      console.error("Error initializing database:", err);
      logEvent(`Error initializing database: ${err instanceof Error ? err.message : "Failed to initialize database."}`);
      setError(err instanceof Error ? err.message : "Failed to initialize database.");
    } finally {
      setIsDbBusy(false);
    }
  }, [db, connectionStatus, setIsDbBusy, logEvent]);

  const handlePopulateDB = useCallback(async () => {
    if (connectionStatus !== 'connected' || !db) {
      setError("Database not connected. Cannot populate.");
      logEvent("Populate DB: DB not connected");
      return;
    }
    setIsDbBusy(true);
    setError(null);
    logEvent("Populating DB...");
    try {
      await populateGithubTables(db);
      logEvent("Database populated successfully!");
      setMessage("Database populated successfully!");
    } catch (err) {
      console.error("Error populating database:", err);
      logEvent(`Error populating database: ${err instanceof Error ? err.message : "Failed to populate database."}`);
      setError(err instanceof Error ? err.message : "Failed to populate database.");
    } finally {
      setIsDbBusy(false);
    }
  }, [db, connectionStatus, setIsDbBusy, logEvent]);

  const onDeleteTables = async () => {
    if (connectionStatus !== 'connected') {
      logEvent('Cannot delete tables: Not connected to SurrealDB.');
      console.error('Cannot delete tables: Not connected to SurrealDB.');
      return;
    }
    setIsDeleting(true);
    try {
      logEvent('Attempting to delete tables...');
      await query('REMOVE TABLE github_user');
      await query('REMOVE TABLE github_repo');
      await query('REMOVE TABLE tasks');
      logEvent('Tables deleted successfully.');
      console.log('Tables deleted successfully.');
    } catch (error) {
      logEvent(`Error deleting tables: ${error}`);
      console.warn('Error deleting tables:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleExecuteQuery = async () => {
    if (!db) {
      setError("Database instance not available.");
      logEvent("Execute Query: DB instance not available");
      return;
    }

    if (connectionStatus !== 'connected') {
      logEvent("Execute Query: Attempting to connect to DB");
      try {
        await connect();
        logEvent("Execute Query: Successfully connected to DB");
      } catch (connectErr) {
        console.error('Error connecting to database:', connectErr);
        logEvent(`Error connecting to database: ${connectErr instanceof Error ? connectErr.message : "Failed to connect to database."}`);
        setError(connectErr instanceof Error ? connectErr.message : "Failed to connect to database.");
        return;
      }
    }

    setError(null);
    logEvent(`Executing query: ${queryText}`);
    try {
      const result = await db.query(queryText);
      logEvent(`Query executed successfully: ${JSON.stringify(result)}`);
      console.log('Query result:', result);
    } catch (err) {
      console.error('Error executing query:', err);
      logEvent(`Error executing query: ${err instanceof Error ? err.message : "Failed to execute query."}`);
      setError(err instanceof Error ? err.message : "Failed to execute query.");
    }
  };

  return (
    <div className="action-buttons-section mb-4 space-x-2 bg-card text-card-foreground">
      {error && (
        <Alert className="mb-4">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {message && <MessageDisplay message={message} onClose={() => setMessage(null)} />}
      <Button onClick={handleInitializeDB} disabled={isDbBusy || isDeleting}>
        {isDbBusy ? 'Working...' : 'Initialize DB'}
      </Button>
      <Button onClick={handlePopulateDB} disabled={isDbBusy || isDeleting}>
        {isDbBusy ? 'Working...' : 'Populate DB'}
      </Button>
      <Button variant="destructive" onClick={onDeleteTables} disabled={isDbBusy || isDeleting}>
        {isDeleting ? 'Deleting...' : 'Delete Tables'}
      </Button>
      <div className="mt-4">
        <h3 className="font-bold text-foreground">Execute SurrealDB Query:</h3>
        <textarea
          className="w-full p-2 border rounded mb-2 resize-none bg-input text-foreground"
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          placeholder="Enter SurrealDB query here..."
        />
        <Button onClick={handleExecuteQuery}>Execute Query</Button>
      </div>
      <div className="mt-4">
        <h3 className="font-bold text-foreground">Event Log:</h3>
        <ScrollArea className="max-h-40 overflow-y-auto rounded-md border bg-card">
          <ul className="p-2">
            {eventLog.map((log, index) => (
              <li key={index} className="text-sm text-foreground">
                {log}
              </li>
            ))}
          </ul>
          <ScrollBar orientation="vertical" />
        </ScrollArea>
      </div>
    </div>
  );
};

export default DevTools;
