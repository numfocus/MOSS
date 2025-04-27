import type { RecordId } from 'surrealdb';

export type TaskResult = string | string[] | { [key: string]: string } | null;

export interface Task {
  id: RecordId;
  type: 'repo' | 'user';
  identifier: string;
  status: 'pending' | 'in-progress' | 'completed' | 'failed';
  result: TaskResult;
  error: TaskResult;
  [key: string]: unknown;
}

export interface NewTaskData {
  type: 'repo' | 'user';
  identifier: string;
}
