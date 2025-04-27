import { Surreal } from "surrealdb";
import type { RecordId } from "surrealdb";
import type { GithubUser } from "../types/GithubUser";
import type { GithubRepo } from "../types/GithubRepo";
import randomGen from "./random_gen";
import fs from 'fs';
import path from 'path';

type SurrealCreateResult<T> = {
  id: RecordId;
} & T;

export const initializeDatabase = async (client: Surreal) => {
  console.log("Initializing database schema...");
  if (!client) {
      console.error("initializeDatabase: Received invalid Surreal client instance.");
      throw new Error("Database client is not available for initialization.");
  }
  try {
    await createGithubTables(client);
    await createTasksTable(client);
    console.log("Database schema setup complete.");
  } catch (error) {
    console.error("Error setting up database schema:", error);
    throw error;
  }
};

export const createTasksTable = async (client: Surreal) => {
  try {
    const tasksSchemaPath = path.join(__dirname, '../../schemas/Tasks.surql');
    const tasksSchema = fs.readFileSync(tasksSchemaPath, 'utf-8');
    await client.query(tasksSchema);
    console.log("Defined tasks table schema from Tasks.surql.");
  } catch (err) {
    console.error("Error creating tasks table schema:", err);
    throw err;
  }
};

export const createGithubUserTable = async (client: Surreal) => {
  try {
    const githubUserSchemaPath = path.join(__dirname, '../../schemas/Github_user.surql');
    const githubUserSchema = fs.readFileSync(githubUserSchemaPath, 'utf-8');
    await client.query(githubUserSchema);
    console.log("Defined github_user table schema from Github_user.surql.");
  } catch (err) {
    console.error("Error creating github_user table schema:", err);
    throw err;
  }
};

export const createGithubRepoTable = async (client: Surreal) => {
  try {
    const githubRepoSchemaPath = path.join(__dirname, '../../schemas/Github_repo.surql');
    const githubRepoSchema = fs.readFileSync(githubRepoSchemaPath, 'utf-8');
    await client.query(githubRepoSchema);
    console.log("Defined github_repo table schema from Github_repo.surql.");
  } catch (err) {
    console.error("Error creating github_repo table schema:", err);
    throw err;
  }
};

export const createGithubTables = async (client: Surreal) => {
  try {
    await createGithubUserTable(client);
    await createGithubRepoTable(client);
    console.log("Github table schemas ensured.");
  } catch (err) {
    console.error("Error creating table schemas:", err);
    throw err;
  }
};

export const populateGithubTables = async (client: Surreal) => {
    console.log("Populating Github tables...");

  try {
    const fakeGithubUsers = randomGen.generateFakeGithubUsers(10);
    console.log("Generated fake users:", fakeGithubUsers.length);

    const createdUsersResults: SurrealCreateResult<GithubUser>[] = [];
    for (const user of fakeGithubUsers) {
        const userDataForDb = { ...user };

      const result = await client.create<GithubUser>("github_user", userDataForDb);

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
    if(ownerLogins.length === 0) {
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
        const repoResult = await client.create<GithubRepo>("github_repo", repoDataWithId);
        if (!repoResult || !repoResult[0]) {
          console.warn("Failed to create/merge repo:", repo.name);
        } else {
        }
      } catch (err) {
        console.error(`Error creating/merging repo ${repo.name}:`, err);
      }
    });

    await Promise.all(repoPromises);

    console.log("Github repos table population attempt finished.");

  } catch (err) {
    console.error("Error populating Github tables:", err);
    throw err;
  }
};
