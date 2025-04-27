import { getTask } from '@/services/db-service';
import { processTask } from './data-agent';
import { Surreal } from 'surrealdb';

let isProcessing = false;

export async function manuallyProcessTask(db: Surreal | null, taskId: string) {
  if (isProcessing) return;
  isProcessing = true;
  try {
    const task = await getTask(db, taskId);
    if (task) {
      await processTask(db, task);
    } else {
      console.log(`Task ${taskId} not found.`);
    }
  } catch (error) {
    console.error(`Error manually processing task ${taskId}:`, error);
  } finally {
    isProcessing = false;
  }
}
