import React, { useState, useCallback, useEffect, ReactNode } from 'react';
import { useSurreal } from '@/hooks/useSurreal';
import { Button } from '@/components/ui/button';
import { manuallyProcessTask } from '@/routes/bot/task-manager';
import { getTasks, updateTask, deleteTasks } from '@/services/db-service';
import { Task, TaskResult } from '@/types/Task';

const QueueView: React.FC = () => {
  const { db } = useSurreal();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchTasks = useCallback(async () => {
    if (!db) {
      console.error('Database not initialized.');
      return;
    }
    setIsLoading(true);
    try {
      const fetchedTasks = await getTasks(db);
      setTasks(fetchedTasks);
      console.log('Fetched tasks:', fetchedTasks);
    } catch (error) {
      console.error('Error fetching tasks:', error);
    } finally {
      setIsLoading(false);
    }
  }, [db]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks, db]);

  const clearQueue = async () => {
    if (!db) {
      console.error('Database not initialized.');
      return;
    }
    try {
      await deleteTasks(db);
      setTasks([]);
    } catch (error) {
      console.error('Error clearing queue:', error);
    }
  };

  const executeTask = async (taskId: string) => {
    if (!db) {
      console.error('Database not initialized.');
      return;
    }
    try {
      await updateTask(db, taskId, { status: 'in-progress' });
      console.log(`Task ${taskId} set to in-progress.`);
      await manuallyProcessTask(db, taskId);
      fetchTasks();
    } catch (error) {
      console.error(`Error setting task ${taskId} to in-progress:`, error);
    }
  };

  const formatResultOrError = (data: TaskResult): ReactNode => {
    if (data === null || data === undefined) {
      return 'No data';
    }
    if (typeof data === 'string') {
      try {
        const parsedData = JSON.parse(data);
        return <pre>{JSON.stringify(parsedData, null, 2)}</pre>;
      } catch (e) {
        return data;
      }
    }
    return <pre>{JSON.stringify(data, null, 2)}</pre>;
  };

  if (isLoading) {
    return <div>Loading tasks...</div>;
  }

  return (
    <div className="queue-view mt-4">
      <div className="flex justify-between items-center">
        <h3>Current Queue</h3>
        <div className="flex space-x-2">
          <Button onClick={fetchTasks}>Refresh Queue</Button>
          <Button onClick={clearQueue} disabled={tasks.length === 0}>
            Clear Queue
          </Button>
        </div>
      </div>
      {tasks.length === 0 ? (
        <div>The queue is empty.</div>
      ) : (
        <ul>
          {tasks.map((task) => (
            <li key={task.id.toString()} className="mb-2 p-2 border rounded flex items-center justify-between">
              <div>
                <div>
                  <strong>ID:</strong> {task.id.toString()}
                </div>
                <div>
                  <strong>Type:</strong> {task.type}
                </div>
                <div>
                  <strong>Identifier:</strong> {task.identifier}
                </div>
                <div>
                  <strong>Status:</strong> {task.status}
                </div>
                {task.result && (
                  <div>
                    <strong>Result:</strong>
                    {formatResultOrError(task.result)}
                  </div>
                )}
                {task.error && (
                  <div>
                    <strong>Error:</strong>
                    {formatResultOrError(task.error)}
                  </div>
                )}
              </div>
              <Button onClick={() => executeTask(task.id.toString())} disabled={task.status === 'in-progress' || task.status === 'completed' || task.status === 'failed'}>
                Execute
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default QueueView;
