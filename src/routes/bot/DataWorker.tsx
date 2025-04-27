import React, { useState, useCallback, memo } from 'react';
import { useSurreal } from '@/hooks/useSurreal';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useForm } from 'react-hook-form';
import QueueView from '@/routes/view/QueueView';
import DBStatus from '@/components/dbstatus/DBStatus';
import { createTask } from '@/services/db-service';
import { NewTaskData } from '@/types/Task';

interface FormValues {
  searchIdentifier: string;
  isRepoSearch: boolean;
}

const DataWorkerComponent: React.FC = () => {
  const { db } = useSurreal();
  const [taskId, setTaskId] = useState<string | null>(null);

  const form = useForm<FormValues>({
    defaultValues: {
      searchIdentifier: '',
      isRepoSearch: false,
    },
  });

  const addTaskToQueue = useCallback(
    async (identifier: string, isRepo: boolean) => {
      const taskData: NewTaskData = {
        type: isRepo ? 'repo' : 'user',
        identifier: identifier,
      };
      const createdTask = await createTask(db, taskData);
      if (createdTask) {
        setTaskId(createdTask.id.toString());
        console.log(`Task added to queue: ${JSON.stringify(createdTask)}`);
      }
    },
    [db]
  );

  const onSubmit = useCallback(
    (values: FormValues) => {
      addTaskToQueue(values.searchIdentifier, values.isRepoSearch);
    },
    [addTaskToQueue, form]
  );

  return (
    <div className="data-worker-page p-4 max-w-4xl">
      <DBStatus />
      <h1 className="text-2xl font-bold mb-4">Data Worker</h1>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            control={form.control}
            name="searchIdentifier"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Search Identifier</FormLabel>
                <FormControl>
                  <Input placeholder="GitHub User or Repo" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="isRepoSearch"
            render={({ field }) => (
              <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                <FormControl>
                  <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                </FormControl>
                <div className="space-y-1 leading-none">
                  <FormLabel>Is Repo Search?</FormLabel>
                </div>
              </FormItem>
            )}
          />
          <Button type="submit">Add Task</Button>
        </form>
      </Form>
      {taskId && (
        <div className="mt-4">
          Task added to queue with ID: {taskId}
        </div>
      )}
      <QueueView />
    </div>
  );
};

const DataWorker = memo(DataWorkerComponent);

export default DataWorker;
