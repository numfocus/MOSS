import { StringRecordId, Surreal } from "surrealdb";
import { Task, NewTaskData } from '@/types/Task';
import { GithubUser } from '@/types/GithubUser';
import { GithubRepo } from '@/types/GithubRepo';


export const createTask = async (db: Surreal | null, taskData: NewTaskData): Promise<Task | null> => {
  if (!db) {
    console.error('Database not initialized.');
    return null;
  }
  try {
    const taskToCreate: Omit<Task, 'id'> = {
      ...taskData,
      status: 'pending',
      result: "",
      error: "",
    };
    console.log('Creating task:', taskToCreate);
    const created = await db.create<Omit<Task, 'id'>>('tasks', taskToCreate);
    console.log('Task created:', created);
    console.log('Task created:', created[0]);
    if (!created[0]) {
      return null;
    }
    return created[0] as Task;
  } catch (error) {
    console.error('Error creating task:', error);
    return null;
  }
};

export const getTask = async (db: Surreal | null, taskId: string): Promise<Task | null> => {
  if (!db) {
    console.error('Database not initialized.');
    return null;
  }
  try {
    console.log(`Getting task with ID: ${taskId}`);
    const task = await db.select<Task>(new StringRecordId(taskId));
    console.log('Task:', task)
    return task || null;
  } catch (error) {
    console.error('Error getting task:', error);
    return null;
  }
};

export const updateTask = async (db: Surreal | null, taskId: string, data: Partial<Task>): Promise<void> => {
  if (!db) {
    console.error('Database not initialized.');
    return;
  }
  try {
    console.log(`Updating task with ID: ${taskId}`);
    console.log('Data to update:', data);
    const tempresult = await db.update(taskId, data);
    console.log('Task updated:', tempresult)
  } catch (error) {
    console.error('Error updating task:', error);
  }
};

export const getTasks = async (db: Surreal | null): Promise<Task[]> => {
  if (!db) {
    console.error('Database not initialized.');
    return [];
  }
  try {
    const result = await db.select<Task>('tasks');
    return result;
  } catch (error) {
    console.error('Error getting tasks:', error);
    return [];
  }
};

export const deleteTasks = async (db: Surreal | null): Promise<void> => {
  if (!db) {
    console.error('Database not initialized.');
    return;
  }
  try {
    await db.query('DELETE tasks');
  } catch (error) {
    console.error('Error deleting tasks:', error);
  }
};

// New function to create a GitHub user
export const createGitHubUser = async (db: Surreal | null, userData: GithubUser): Promise<GithubUser | null> => {
  if (!db) {
    console.error('Database not initialized.');
    return null;
  }
  try {
    console.log('Creating GitHub user:', userData);
    const created = await db.create<GithubUser>('github_user', userData);
    console.log('GitHub user created:', created);
    if (!created[0]) {
      return null;
    }
    return created[0];
  } catch (error) {
    console.error('Error creating GitHub user:', error);
    return null;
  }
};

// New function to create a GitHub repo
export const createGitHubRepo = async (db: Surreal | null, repoData: GithubRepo): Promise<GithubRepo | null> => {
  if (!db) {
    console.error('Database not initialized.');
    return null;
  }
  try {
    console.log('Creating GitHub repo:', repoData);
    const created = await db.create<GithubRepo>('github_repo', repoData);
    console.log('GitHub repo created:', created);
    if (!created[0]) {
      return null;
    }
    return created[0];
  } catch (error) {
    console.error('Error creating GitHub repo:', error);
    return null;
  }
};
