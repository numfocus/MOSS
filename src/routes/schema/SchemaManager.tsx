import React, { useState, useEffect } from 'react';
import {
  Form,
  FormField,
  FormItem,
  FormLabel,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Trash } from 'lucide-react';

const schemaManagerFormSchema = z.object({
  githubUserFields: z.array(z.string()).optional(),
  githubRepoFields: z.array(z.string()).optional(),
  customFields: z.array(z.object({
    name: z.string().min(1, { message: "Field name is required." }),
    type: z.string().min(1, { message: "Data type is required." }),
  })).optional(),
});

type SchemaManagerFormValues = z.infer<typeof schemaManagerFormSchema>;

const allGithubUserFields: string[] = [
  'login',
  'node_id',
  'avatar_url',
  'gravatar_id',
  'url',
  'html_url',
  'followers_url',
  'following_url',
  'gists_url',
  'starred_url',
  'subscriptions_url',
  'organizations_url',
  'repos_url',
  'events_url',
  'received_events_url',
  'type',
  'site_admin',
  'name',
  'company',
  'blog',
  'location',
  'email',
  'hireable',
  'bio',
  'twitter_username',
  'public_repos',
  'public_gists',
  'followers',
  'following',
  'created_at',
  'updated_at',
];

const allGithubRepoFields: string[] = [
  'node_id',
  'name',
  'full_name',
  'owner',
  'description',
  'private',
  'fork',
  'url',
  'forks_url',
  'keys_url',
  'collaborators_url',
  'teams_url',
  'hooks_url',
  'issue_events_url',
  'events_url',
  'assignees_url',
  'branches_url',
  'tags_url',
  'blobs_url',
  'git_tags_url',
  'git_refs_url',
  'trees_url',
  'statuses_url',
  'languages_url',
  'stargazers_url',
  'contributors_url',
  'subscribers_url',
  'subscription_url',
  'commits_url',
  'git_commits_url',
  'comments_url',
  'issue_comment_url',
  'contents_url',
  'compare_url',
  'merges_url',
  'archive_url',
  'downloads_url',
  'issues_url',
  'pulls_url',
  'milestones_url',
  'notifications_url',
  'labels_url',
  'releases_url',
  'deployments_url',
  'created_at',
  'updated_at',
  'pushed_at',
  'git_url',
  'ssh_url',
  'clone_url',
  'svn_url',
  'homepage',
  'size',
  'stargazers_count',
  'watchers_count',
  'language',
  'has_issues',
  'has_projects',
  'has_downloads',
  'has_wiki',
  'has_pages',
  'has_discussions',
  'forks_count',
  'mirror_url',
  'archived',
  'disabled',
  'open_issues_count',
  'license',
  'allow_forking',
  'is_template',
  'web_commit_signoff_required',
  'topics',
  'visibility',
  'forks',
  'open_issues',
  'watchers',
  'default_branch',
  'temp_clone_token',
  'network_count',
  'subscribers_count',
  'html_url',
];

const dataTypes = ['string', 'number', 'boolean', 'date', 'any'];

interface CustomField {
  name: string;
  type: string;
}

const SchemaManager: React.FC = () => {
  const form = useForm<SchemaManagerFormValues>({
    resolver: zodResolver(schemaManagerFormSchema),
    defaultValues: {
      githubUserFields: [],
      githubRepoFields: [],
      customFields: [],
    },
  });

  const [selectedGithubUserFields, setSelectedGithubUserFields] = useState<
    string[]
  >([]);
  const [selectedGithubRepoFields, setSelectedGithubRepoFields] = useState<
    string[]
  >([]);
  const [customFields, setCustomFields] = useState<CustomField[]>([]);
  const [newFieldName, setNewFieldName] = useState<string>('');
  const [newFieldType, setNewFieldType] = useState<string>('string');

  useEffect(() => {
    form.setValue('githubUserFields', selectedGithubUserFields);
  }, [selectedGithubUserFields, form]);

  useEffect(() => {
    form.setValue('githubRepoFields', selectedGithubRepoFields);
  }, [selectedGithubRepoFields, form]);

  useEffect(() => {
    form.setValue('customFields', customFields);
  }, [customFields, form]);

  const handleAddField = () => {
    if (newFieldName && newFieldType) {
      setCustomFields([...customFields, { name: newFieldName, type: newFieldType }]);
      setNewFieldName('');
      setNewFieldType('string');
    }
  };

  const handleRemoveField = (index: number) => {
    const updatedFields = [...customFields];
    updatedFields.splice(index, 1);
    setCustomFields(updatedFields);
  };

  const onSubmit = (data: SchemaManagerFormValues) => {
    console.log('Form submitted:', data);
  };

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-2xl font-bold mb-4">Schema Manager</h1>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h2 className="text-lg font-semibold mb-2">GitHub User Fields</h2>
              <div className="space-y-2">
                {allGithubUserFields.map((field) => (
                  <FormField
                    key={field}
                    control={form.control}
                    name="githubUserFields"
                    render={({ field: {  } }) => (
                      <FormItem
                        key={field}
                        className="flex flex-row items-center space-x-3 space-y-0"
                      >
                        <Checkbox
                          id={field}
                          checked={selectedGithubUserFields.includes(field)}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedGithubUserFields([
                                ...selectedGithubUserFields,
                                field,
                              ]);
                            } else {
                              setSelectedGithubUserFields(
                                selectedGithubUserFields.filter(
                                  (f) => f !== field
                                )
                              );
                            }
                          }}
                        />
                        <FormLabel htmlFor={field} className="font-normal">
                          {field}
                        </FormLabel>
                      </FormItem>
                    )}
                  />
                ))}
              </div>
            </div>

            <div>
              <h2 className="text-lg font-semibold mb-2">GitHub Repo Fields</h2>
              <div className="space-y-2">
                {allGithubRepoFields.map((field) => (
                  <FormField
                    key={field}
                    control={form.control}
                    name="githubRepoFields"
                    render={({ field: {  } }) => (
                      <FormItem
                        key={field}
                        className="flex flex-row items-center space-x-3 space-y-0"
                      >
                        <Checkbox
                          id={field}
                          checked={selectedGithubRepoFields.includes(field)}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedGithubRepoFields([
                                ...selectedGithubRepoFields,
                                field,
                              ]);
                            } else {
                              setSelectedGithubRepoFields(
                                selectedGithubRepoFields.filter(
                                  (f) => f !== field
                                )
                              );
                            }
                          }}
                        />
                        <FormLabel htmlFor={field} className="font-normal">
                          {field}
                        </FormLabel>
                      </FormItem>
                    )}
                  />
                ))}
              </div>
            </div>
          </div>
          <div>
            <h2 className="text-lg font-semibold mb-2">Custom Fields</h2>
            <div className="space-y-2">
              {customFields.map((field, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <Input
                    type="text"
                    value={field.name}
                    readOnly
                    className="w-1/3"
                  />
                  <Input
                    type="text"
                    value={field.type}
                    readOnly
                    className="w-1/3"
                  />
                  <Button
                    type="button"
                    variant="destructive"
                    size="icon"
                    onClick={() => handleRemoveField(index)}
                  >
                    <Trash className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
            <div className="flex items-center space-x-2 mt-2">
              <Input
                type="text"
                placeholder="Field Name"
                value={newFieldName}
                onChange={(e) => setNewFieldName(e.target.value)}
                className="w-1/3"
              />
              <Select onValueChange={setNewFieldType} defaultValue={newFieldType}>
                <SelectTrigger className="w-1/3">
                  <SelectValue placeholder="Data Type" />
                </SelectTrigger>
                <SelectContent>
                  {dataTypes.map((type) => (
                    <SelectItem key={type} value={type}>
                      {type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button type="button" onClick={handleAddField}>
                Add Field
              </Button>
            </div>
          </div>

          <Button type="submit">Submit</Button>
        </form>
      </Form>
    </div>
  );
};

export default SchemaManager;
