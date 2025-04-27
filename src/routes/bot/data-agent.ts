import { getGitHubUser, getGitHubUserRepos, getGitHubRepo } from '@/api/scrape-github';
import { updateTask, createGitHubUser, createGitHubRepo } from '@/services/db-service';
import { Task } from '@/types/Task';
import { Surreal } from 'surrealdb';
import { GithubUser } from '@/types/GithubUser';
import { GithubRepo } from '@/types/GithubRepo';

export async function processTask(db: Surreal | null, task: Task): Promise<void> {
  if (!db) {
    console.error('Database not initialized.');
    return;
  }
  try {
    console.log(`Processing task: ${JSON.stringify(task)}`);
    console.log(`Processing task identifier: ${task.identifier}`);

    let result: any = null;

    if (task.type === 'user') {
      console.log(`Fetching user data for: ${task.identifier}`);
      try {
        const user: GithubUser = await getGitHubUser(task.identifier);
        console.log(`User data fetched:`, user);
        const createdUser = await createGitHubUser(db, user);
        if (createdUser) {
          console.log(`GitHub user created in database:`, createdUser);
        } else {
          console.error(`Failed to create GitHub user in database.`);
        }
        const repos: GithubRepo[] = await getGitHubUserRepos(task.identifier);
        console.log(`Repos data fetched:`, repos);
        for (const repo of repos) {
          const createdRepo = await createGitHubRepo(db, { ...repo, owner: user.login });
          if (createdRepo) {
            console.log(`GitHub repo created in database:`, createdRepo);
          } else {
            console.error(`Failed to create GitHub repo in database.`);
          }
        }
        result = { user, repos };
      } catch (githubError) {
        console.error(`Error fetching GitHub user or repos for ${task.identifier}:`, githubError);
        throw githubError;
      }
    } else if (task.type === 'repo') {
      console.log(`Fetching repo data for: ${task.identifier}`);
      try {
        result = await getGitHubRepo(task.identifier);
        console.log(`Repo data fetched:`, result);
      } catch (githubError) {
        console.error(`Error fetching GitHub repo for ${task.identifier}:`, githubError);
        throw githubError;
      }
    } else {
      throw new Error(`Invalid task type: ${task.type}`);
    }

    await updateTask(db, task.id.toString(), { result: JSON.stringify(result), status: 'completed' });
    console.log(`Task ${task.id} completed.`);
  } catch (error: any) {
    console.error(`Error processing task ${task.id}:`, error);
    await updateTask(db, task.id.toString(), { status: 'failed', error: JSON.stringify(error.message || error) || 'An unknown error occurred' });
  }
}
