import React, { useState, useCallback } from 'react';
import type { GithubUser } from '@/types/GithubUser';
import type { GithubRepo } from '@/types/GithubRepo';
import { useSurreal } from '@/hooks/useSurreal';
import { Button } from '@/components/ui/button';


const DataView: React.FC = () => {
  const { db, connectionStatus, query } = useSurreal();

  const [allUsers, setAllUsers] = useState<GithubUser[]>([]);
  const [userRepos, setUserRepos] = useState<Record<string, GithubRepo[]>>({});
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [fetchedRepos, setFetchedRepos] = useState<GithubRepo[]>([]);

  const [allRepos, setAllRepos] = useState<GithubRepo[]>([]);
  const [isReposLoading, setIsReposLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [repoContributors, setRepoContributors] = useState<Record<string, GithubUser[]>>({});
  const [isContributorsLoading, setIsContributorsLoading] = useState<boolean>(false);

  const fetchAllUsers = useCallback(async () => {
    if (connectionStatus !== 'connected') {
      setError('Database not connected.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const queryResult = await query('SELECT * FROM github_user') as GithubUser[][];

      const fetchedUsers = queryResult?.[0] || [];
      if (!Array.isArray(fetchedUsers)) {
        console.error('Fetched users is not an array:', fetchedUsers);
        return;
      }
      if (fetchedUsers.length === 0) {
        console.warn('No users found in the database.');
        setAllUsers([]);
        return;
      }
      setAllUsers(fetchedUsers);
    } catch (err) {
      console.error('Error fetching users:', err);
      setError('Error fetching users.');
    } finally {
      setIsLoading(false);
    }
  }, [connectionStatus, query]);

  const fetchUserRepos = useCallback(
    async (login: string) => {
      if (connectionStatus !== 'connected') {
        setError('Database not connected.');
        return;
      }
      setIsReposLoading(true);
      setError(null);
      try {
        const queryString = `SELECT * FROM github_repo WHERE owner = $login`;
        console.log(`fetchUserRepos: Querying with: ${queryString}, login: ${login}`);

        const queryResult = await db!.query<[{ result?: GithubRepo[] }]>(
          queryString,
          { login }
        );
        console.log(`fetchUserRepos: queryResult:`, queryResult);

        const fetchedRepos = queryResult?.[0]?.result || [];
        if (!fetchedRepos || fetchedRepos.length === 0) {
          console.warn(`No repos found for user: ${login}`);
          setUserRepos((prevRepos) => ({
            ...prevRepos,
            [login]: [],
          }));
          return;
        }
        setUserRepos((prevRepos) => ({
          ...prevRepos,
          [login]: fetchedRepos,
        }));
      } catch (err) {
        console.error(`Error fetching repos for ${login}:`, err);
        setError(`Error fetching repos for ${login}.`);
      } finally {
        setIsReposLoading(false);
      }
    },
    [db, connectionStatus, query]
  );

  const fetchAllRepos = useCallback(async () => {
    if (connectionStatus !== 'connected') {
      setError('Database not connected.');
      return;
    }
    setIsReposLoading(true);
    setError(null);
    try {
      console.log('DataView: fetchAllRepos - about to query, query:', query, 'connectionStatus:', connectionStatus);
      const queryResult = await query('SELECT * FROM github_repo') as any[][];
      console.log('DataView: fetchAllRepos - queryResult:', queryResult);

      const fetchedRepos = queryResult?.[0] || [];

      if (!Array.isArray(fetchedRepos)) {
        console.error('Fetched repos is not an array:', fetchedRepos);
        return;
      }
      if (fetchedRepos.length === 0) {
        console.warn('No repos found in the database.');
        setAllRepos([]);
        return;
      }
      console.log('DataView: fetchAllRepos - about to setAllRepos with:', fetchedRepos);
      setAllRepos(fetchedRepos);
    } catch (err) {
      console.error('Error fetching all repos:', err);
      console.log('Error fetching all repos - error object:', err);
      setError('Error fetching all repos.');
    } finally {
      setIsReposLoading(false);
    }
  }, [connectionStatus, query]);

  const fetchContributors = useCallback(async (repoFullName: string): Promise<GithubUser[]> => {
    console.log(`fetchContributors: Starting to fetch contributors for ${repoFullName}`);
    const [owner, repo] = repoFullName.split('/');

    const githubApiUrl = `https://api.github.com/repos/${owner}/${repo}/contributors`;
    console.log(`fetchContributors: Constructed API URL: ${githubApiUrl}`);

    try {
      const response = await fetch(githubApiUrl);
      console.log(`fetchContributors: API response status: ${response.status}`);

      if (!response.ok) {
        if (response.status === 404) {
          console.error(`fetchContributors: Repository ${repoFullName} not found.`);
          throw new Error(`Repository ${repoFullName} not found.`);
        } else if (response.status === 403) {
          console.error(`fetchContributors: Rate limit exceeded or access forbidden for ${repoFullName}.`);
          throw new Error(`Rate limit exceeded or access forbidden for ${repoFullName}.`);
        } else if (response.status === 204) {
          console.warn(`fetchContributors: No public contributors found for repo: ${repoFullName}`);
          return [];
        } else {
          console.error(`fetchContributors: Failed to fetch contributors for ${repoFullName}. Status: ${response.status}`);
          throw new Error(`Failed to fetch contributors for ${repoFullName}. Status: ${response.status}`);
        }
      }

      const fetchedContributors = await response.json() as any[];
      console.log(`fetchContributors: Fetched contributors for ${repoFullName}:`, fetchedContributors);
      return fetchedContributors.map((contributor) => ({
        github_id: contributor.id || 0,
        login: contributor.login,
        avatar_url: contributor.avatar_url,
        html_url: contributor.html_url,
        node_id: contributor.node_id,
        type: contributor.type,
        site_admin: contributor.site_admin,
        name: contributor.name || null,
        bio: contributor.bio || null,
        blog: contributor.blog || null,
        company: contributor.company || null,
        created_at: contributor.created_at || null,
        email: contributor.email || null,
        followers: contributor.followers || null,
        following: contributor.following || null,
        location: contributor.location || null,
        public_gists: contributor.public_gists || null,
        public_repos: contributor.public_repos || null,
        twitter_username: contributor.twitter_username || null,
        updated_at: contributor.updated_at || null,
        url: contributor.url || null,
        followers_url: contributor.followers_url || null,
        following_url: contributor.following_url || null,
        gists_url: contributor.gists_url || null,
        organizations_url: contributor.organizations_url || null,
        received_events_url: contributor.received_events_url || null,
        repos_url: contributor.repos_url || null,
        starred_url: contributor.starred_url || null,
        subscriptions_url: contributor.subscriptions_url || null,
        events_url: contributor.events_url || null,
        gravatar_id: contributor.gravatar_id || null,
        contributions: contributor.contributions || null,
      } as GithubUser));
    } catch (error) {
      console.error(`fetchContributors: An error occurred while fetching contributors for ${repoFullName}:`, error);
      throw error;
    }
  }, []);

  const fetchRepoContributors = useCallback(async (repoFullName: string) => {
    if (connectionStatus !== 'connected') {
      setError('Database not connected.');
      return;
    }
    setIsContributorsLoading(true);
    setError(null);
    try {
      const fetchedContributors = await fetchContributors(repoFullName);

      if (!fetchedContributors || fetchedContributors.length === 0) {
        console.warn(`No contributors found for repo: ${repoFullName}`);
        setRepoContributors((prevContributors) => ({
          ...prevContributors,
          [repoFullName]: [],
        }));
        return;
      }

      const userUpserts = fetchedContributors.map(async (user) => {
        try {
          await db!.query(`
          CREATE github_user:$login OR UPDATE github_user:$login CONTENT $user;
          `, {
            login: user.login,
            user: user,
          });
        } catch (err) {
          console.error(`Error upserting user ${user.login}:`, err);
          setError(`Error upserting user ${user.login}.`);
        }
      });
      await Promise.all(userUpserts);

      const linkInserts = fetchedContributors.map(async (contributor) => {
        try {
          await db!.query(`
          RELATE (SELECT id FROM github_repo WHERE full_name = $repoFullName) -> contributes -> github_user:$login SET contributions = $contributions
          `, {
            repoFullName: repoFullName,
            login: contributor.login,
            contributions: contributor.contributions,
          });
        } catch (err) {
          console.error(`Error creating link for user ${contributor.login} in repo ${repoFullName}:`, err);
          setError(`Error creating link for user ${contributor.login} in repo ${repoFullName}.`);
        }
      });
      await Promise.all(linkInserts);

      setRepoContributors((prevContributors) => ({
        ...prevContributors,
        [repoFullName]: fetchedContributors,
      }));
    } catch (err) {
      console.error(`Error fetching or inserting contributors for ${repoFullName}:`, err);
      setError(`Error fetching or inserting contributors for ${repoFullName}.`);
    } finally {
      setIsContributorsLoading(false);
    }
  }, [connectionStatus, db, fetchContributors]);

  const refreshUsers = useCallback(async () => {
    await new Promise((resolve) => setTimeout(resolve, 100));
    await fetchAllUsers();
  }, [fetchAllUsers]);

  const refreshRepos = useCallback(async () => {
    await new Promise((resolve) => setTimeout(resolve, 100));
    await fetchAllRepos();
  }, [fetchAllRepos]);

  const scrapeUserRepos = useCallback(async (login: string) => {
    if (connectionStatus !== 'connected') {
      setError('Database not connected.');
      return;
    }
    setIsReposLoading(true);
    setError(null);
    try {
      const githubApiUrl = `https://api.github.com/users/${login}/repos`;
      console.log(`scrapeUserRepos: Fetching from ${githubApiUrl}`);
      const response = await fetch(githubApiUrl);

      if (!response.ok) {
        console.error(`scrapeUserRepos: Failed to fetch repos for ${login}. Status: ${response.status}`);
        throw new Error(`Failed to fetch repos for ${login}. Status: ${response.status}`);
      }

      const fetchedReposData = await response.json() as any[];
      console.log(`scrapeUserRepos: Fetched repos for ${login}:`, fetchedReposData);

      const repos: GithubRepo[] = fetchedReposData.map((repo) => ({
        github_id: repo.id,
        full_name: repo.full_name,
        name: repo.name,
        html_url: repo.html_url,
        description: repo.description,
        owner: login,
        url: repo.url,
      } as GithubRepo));

      setFetchedRepos(repos);
    } catch (err) {
      console.error(`Error scraping or inserting repos for ${login}:`, err);
      setError(`Error scraping or inserting repos for ${login}.`);
    } finally {
      setIsReposLoading(false);
    }
  }, [connectionStatus]);

const addReposToDb = useCallback(async (login: string) => {
  if (connectionStatus !== 'connected') {
    setError('Database not connected.');
    return;
  }
  setIsReposLoading(true);
  setError(null);
  try {
    if (fetchedRepos.length === 0) {
      console.warn('No repos to add.');
      return;
    }

    const repoUpserts = fetchedRepos.map(async (repo) => {
      try {
        await db!.query(`
          UPSERT type::thing("github_repo", $github_id) CONTENT $repo;
          `, {
          github_id: repo.github_id,
          repo: repo,
        });
      } catch (err) {
        console.error(`Error upserting repo ${repo.full_name}:`, err);
        setError(`Error upserting repo ${repo.full_name}.`);
      }
    });
    await Promise.all(repoUpserts);

    const updatedRepos = await query(`SELECT * FROM github_repo WHERE owner = $login`, { login }) as any[][];
    const updatedReposData = updatedRepos?.[0] || [];
    setUserRepos((prevRepos) => ({
      ...prevRepos,
      [login]: updatedReposData,
    }));
    setFetchedRepos([]);
  } catch (err) {
    console.error(`Error adding repos to database:`, err);
    setError(`Error adding repos to database.`);
  } finally {
    setIsReposLoading(false);
  }
}, [connectionStatus, db, query, fetchedRepos]);


  if (connectionStatus !== 'connected') {
    return <div>Database not connected.</div>;
  }

  if (isLoading || isReposLoading || isContributorsLoading) {
    return <div>Loading data...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div className="data-view mt-4 flex">
      <div className="w-1/2 pr-4">
        <div className="flex items-center mb-4">
          <h3 className="mr-4">GitHub User Data</h3>
          <Button onClick={refreshUsers}>Refresh Users</Button>
        </div>
        {allUsers.length === 0 ? (
          <div>No users found.</div>
        ) : (
          <ul>
            {allUsers.map((savedUser) => (
              <li key={savedUser.login} className="mb-2 p-2 border rounded">
                <div className="flex items-start">
                  {savedUser.avatar_url && (
                    <img
                      src={savedUser.avatar_url}
                      alt={`${savedUser.login}'s avatar`}
                      className="w-10 h-10 rounded-full mr-3"
                    />
                  )}
                  <div className="flex flex-row">
                    <div>
                      <p className="font-medium">{savedUser.name || 'N/A'}</p>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        @{savedUser.login}
                      </p>
                    </div>
                    <Button
                      onClick={() => fetchUserRepos(savedUser.login)}
                      className="h-5"
                    >
                      Load Repos
                    </Button>
                    <Button
                      onClick={() => scrapeUserRepos(savedUser.login)}
                      className="h-5 ml-2"
                    >
                      Fetch Repos
                    </Button>
                    {fetchedRepos.length > 0 && (
                      <Button
                        onClick={() => addReposToDb(savedUser.login)}
                        className="h-5 ml-2"
                      >
                        Add Repos
                      </Button>
                    )}
                  </div>
                </div>
                {fetchedRepos.length > 0 && fetchedRepos[0].owner === savedUser.login && (
                  <div className="mt-2">
                    <h4 className="font-semibold">Fetched Repos:</h4>
                    <ul>
                      {fetchedRepos.map((repo) => (
                        <li key={repo.github_id} className="mb-1">
                          <a
                            href={repo.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:underline"
                          >
                            {repo.full_name}
                          </a>
                          {repo.description && (
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {repo.description}
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {userRepos[savedUser.login] && (
                  <div className="mt-2">
                    <h4 className="font-semibold">Repos:</h4>
                    <ul>
                      {userRepos[savedUser.login].map((repo) => (
                        <li key={repo.github_id} className="mb-1">
                          <a
                            href={repo.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:underline"
                          >
                            {repo.full_name}
                          </a>
                          {repo.description && (
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {repo.description}
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="w-1/2">
        <div className="flex items-center mb-4">
          <h3 className="mr-4">GitHub Repo Data</h3>
          <Button onClick={refreshRepos}>Refresh Repos</Button>
        </div>
        {allRepos.length === 0 ? (
          <div>No repos found.</div>
        ) : (
          <ul>
            {allRepos.map((repo: any) => (
              <li key={repo.github_id} className="mb-2 p-2 border rounded">
                <div className="flex items-center">
                  <a
                    href={repo.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline"
                  >
                    {repo.full_name}
                  </a>
                  <Button
                    onClick={() => fetchRepoContributors(repo.full_name)}
                    className="ml-2 h-5"
                  >
                    Add Contributors
                  </Button>
                  <Button
                    onClick={() => fetchContributors(repo.full_name)}
                    className="ml-2 h-5"
                  >
                    Fetch Contributors
                  </Button>
                </div>
                {repo.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {repo.description}
                  </p>
                )}
                {repoContributors[repo.full_name] && repoContributors[repo.full_name].length > 0 && (
                  <div className="mt-2">
                    <h4 className="font-semibold">Contributors:</h4>
                    <ul>
                      {repoContributors[repo.full_name].map((contributor) => (
                        <li key={contributor.login} className="mb-1">
                          <a
                            href={contributor.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:underline flex items-center"
                          >
                            <img
                              src={contributor.avatar_url}
                              alt={`${contributor.login}'s avatar`}
                              className="w-6 h-6 rounded-full mr-2"
                            />
                            {contributor.login}
                          </a>
                          {contributor.contributions && (
                            <span className="ml-2 text-sm text-gray-500">
                              Contributions: {contributor.contributions}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default DataView;
