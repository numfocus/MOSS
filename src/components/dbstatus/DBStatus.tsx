import React from 'react';
import { useSurreal } from '@/hooks/useSurreal';
import { Button } from '@/components/ui/button';
import { defineTasksSchema } from '@/schemas/Tasks';
import { defineGithubUserSchema } from '@/schemas/GithubUser';
import { defineGithubRepoSchema } from '@/schemas/GithubRepo';
import randomGen from '@/utils/random_gen';
import type { GithubUser } from '@/types/GithubUser';
import type { GithubRepo } from '@/types/GithubRepo';
import type { RecordId } from 'surrealdb';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import Portal from '@/components/Portal';
import './index.css';
import { atom, useAtom } from 'jotai'; // Import Jotai

// Define Jotai atoms
interface DatabaseInfo {
  namespace: string;
  database: string;
}

interface TableInfo {
  [key: string]: {
    id: string;
  };
}

type SurrealCreateResult<T> = {
  id: RecordId;
} & T;

// Define Jotai atoms
const dbInfoAtom = atom<DatabaseInfo | null>(null);
const tableNamesAtom = atom<string[]>([]);
const infoErrorAtom = atom<string | null>(null);
const isDbStatusVisibleAtom = atom<boolean>(false);
const isConnectingAtom = atom<boolean>(false);

const DBStatus: React.FC = () => {
  const { connect, disconnect, connectionStatus, error, query, db } = useSurreal();
  // Use Jotai hooks to manage state
  const [dbInfo, setDbInfo] = useAtom(dbInfoAtom);
  const [tableNames, setTableNames] = useAtom(tableNamesAtom);
  const [infoError, setInfoError] = useAtom(infoErrorAtom);
  const [isDbStatusVisible, setIsDbStatusVisible] = useAtom(isDbStatusVisibleAtom);
  const [isConnecting, setIsConnecting] = useAtom(isConnectingAtom);

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      await connect();
    } catch (err) {
      console.error('Error connecting to database:', err);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnect();
    } catch (err) {
      console.error('Error disconnecting from database:', err);
    }
  };

  const handleCheckInfo = async () => {
    setDbInfo(null);
    setTableNames([]);
    setInfoError(null);
    try {
      const dbInfoResult = await query('INFO FOR DB;');
      const tasksInfoResult = await query('INFO FOR TABLE tasks;');
      console.log('dbInfoResult:', dbInfoResult);
      console.log('tasksInfoResult:', tasksInfoResult);

      if (dbInfoResult && dbInfoResult[0] && typeof dbInfoResult[0] === 'object' && 'result' in dbInfoResult[0]) {
        const { namespace, database } = dbInfoResult[0].result as DatabaseInfo;
        setDbInfo({ namespace, database });
      } else {
        setInfoError('Could not retrieve database information.');
      }

      if (tasksInfoResult && tasksInfoResult[0] && typeof tasksInfoResult[0] === 'object' && 'result' in tasksInfoResult[0]) {
        const tasks = tasksInfoResult[0].result as TableInfo;
        const names = Object.keys(tasks);
        setTableNames(names);
      } else {
        setInfoError('Could not retrieve tasks information.');
      }
    } catch (err) {
      console.error('Error checking database info:', err);
      setInfoError('Error checking database info.');
    }
  };

  const handleClearDatabase = async () => {
    setInfoError(null);
    try {
      if (!db) {
        setInfoError('Cannot clear database: Database instance not available.');
        return;
      }
      await db.query('REMOVE DATABASE test;');
      setDbInfo(null);
      setTableNames([]);
      setInfoError('Database cleared successfully.');
    } catch (err) {
      console.error('Error clearing database:', err);
      setInfoError('Error clearing database.');
    }
  };

  const createTasksTable = async () => {
    if (!db) {
      console.error("createTasksTable: Database instance not available.");
      return;
    }
    await defineTasksSchema(db);
  };

  const createGithubUserTable = async () => {
    if (!db) {
      console.error("createGithubUserTable: Database instance not available.");
      return;
    }
    await defineGithubUserSchema(db);
  };

  const createGithubRepoTable = async () => {
    if (!db) {
      console.error("createGithubRepoTable: Database instance not available.");
      return;
    }
    await defineGithubRepoSchema(db);
  };

  const populateGithubTables = async () => {
    if (!db) {
      console.error("populateGithubTables: Database instance not available.");
      return;
    }
    console.log("Populating Github tables...");

    try {
      const fakeGithubUsers = randomGen.generateFakeGithubUsers(10);
      console.log("Generated fake users:", fakeGithubUsers.length);

      const createdUsersResults: SurrealCreateResult<GithubUser>[] = [];
      for (const user of fakeGithubUsers) {
        const userDataForDb = { ...user };
        const result = await db.create<GithubUser>("github_user", userDataForDb);

        if (result && result[0]) {
          const createdUser = result[0] as SurrealCreateResult<GithubUser>;
          createdUsersResults.push(createdUser);
        } else {
          console.warn("Failed to create/merge user or get result for:", user.login);
        }
      }

      console.log("Users created/merged:", createdUsersResults.map(u => ({ id: u.id, login: u.login })));

      if (createdUsersResults.length === 0) {
        console.warn("No users were created/merged. Skipping repo creation.");
        return;
      }

      const ownerLogins = createdUsersResults.map(result => result.login).filter(login => !!login);
      if (ownerLogins.length === 0) {
        console.warn("No valid owner logins found after user creation. Skipping repo creation.");
        return;
      }

      const fakeGithubRepos = randomGen.generateFakeGithubRepos(5, ownerLogins);
      console.log("Generated fake repos:", fakeGithubRepos.length);

      const repoPromises = fakeGithubRepos.map(async (repo) => {
        const ownerLogin = repo.owner;
        const repoDataForDb: GithubRepo = randomGen.generateFakeGithubRepo(ownerLogin);
        repoDataForDb.name = repo.name;
        repoDataForDb.full_name = `${ownerLogin}/${repo.name}`;
        repoDataForDb.html_url = `https://github.com/${ownerLogin}/${repo.name}`;
        repoDataForDb.url = `https://api.github.com/repos/${ownerLogin}/${repo.name}`;
        repoDataForDb.github_id = repo.github_id;

        const repoDataWithId = { ...repoDataForDb };

        try {
          const repoResult = await db.create<GithubRepo>("github_repo", repoDataWithId);
          if (!repoResult || !repoResult[0]) {
            console.warn("Failed to create/merge repo:", repo.name);
          }
        } catch (err) {
          console.error(`Error creating/merging repo ${repo.name}:`, err);
        }
      });

      await Promise.all(repoPromises);

      console.log("Github repos table population attempt finished.");

    } catch (err) {
      console.error("Error populating Github tables:", err);
    }
  };

  const toggleDbStatusVisibility = () => {
      console.log("toggleDbStatusVisibility called"); 
    setIsDbStatusVisible(!isDbStatusVisible);
  };

  return (
    <div> {/* Outer div added */}
      <div className="db-status-container"> {/* Separate container for the button */}
        <Button className="db-status-button" onClick={toggleDbStatusVisibility}>
          {isDbStatusVisible ? 'Hide DB Status' : 'Show DB Status'}
        </Button>
      </div>
      <Portal containerId="db-status-portal">
        {isDbStatusVisible && (
          <div className="db-status p-4 border rounded bg-white shadow-md">
            <h3 className="mb-2">Database Status</h3>
            <p className="mb-2">
              <strong>Status:</strong> {connectionStatus}
            </p>
            {error && (
              <p className="text-red-500 mb-2">
                <strong>Error:</strong> {error.message}
              </p>
            )}
            <div className="flex space-x-2 mb-4"> {/* This is the flex container for the other buttons */}
              <Button onClick={handleConnect} disabled={connectionStatus === 'connected' || connectionStatus === 'connecting' || isConnecting}>
                {isConnecting ? 'Connecting...' : 'Connect'}
              </Button>
              <Button onClick={handleDisconnect} disabled={connectionStatus === 'disconnected' || connectionStatus === 'connecting' || isConnecting}>
                Disconnect
              </Button>
              <Button onClick={handleCheckInfo} disabled={connectionStatus !== 'connected' || isConnecting}>
                Check tasks/Namespace
              </Button>
              <Button onClick={handleClearDatabase} disabled={connectionStatus !== 'connected' || isConnecting}>
                Clear Database
              </Button>
              <Accordion type="single" collapsible className="w-full accordion">
              <AccordionItem value="database-actions">
                <AccordionTrigger>Database Actions</AccordionTrigger>
                <AccordionContent>
                  <div className="flex flex-col space-y-2 mb-4">
                    <Button onClick={createTasksTable} disabled={connectionStatus !== 'connected' || isConnecting}>
                      Initialize Tasks Table
                    </Button>
                    <Button onClick={createGithubUserTable} disabled={connectionStatus !== 'connected' || isConnecting}>
                      Initialize Github User Table
                    </Button>
                    <Button onClick={createGithubRepoTable} disabled={connectionStatus !== 'connected' || isConnecting}>
                      Initialize Github Repo Table
                    </Button>
                    <Button onClick={populateGithubTables} disabled={connectionStatus !== 'connected' || isConnecting}>
                      Populate Github Tables
                    </Button>
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
            </div>
            
            {infoError && (
              <p className="text-red-500 mb-2">
                <strong>Info Error:</strong> {infoError}
              </p>
            )}
            {dbInfo && (
              <div className="mb-2">
                <strong>Database Info:</strong>
                <pre>
                  {JSON.stringify(dbInfo, null, 2)}
                </pre>
              </div>
            )}
            {tableNames.length > 0 && (
              <div>
                <strong>Table Names:</strong>
                <ul>
                  {tableNames.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Portal>
    </div>
  );
};

export default DBStatus;
