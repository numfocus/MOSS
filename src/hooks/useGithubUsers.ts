import { useQuery } from '@tanstack/react-query';
import { useSurreal } from './useSurreal';
import type { GithubUser } from '@/types/GithubUser';

const GITHUB_USERS_QUERY_KEY = ['githubUsers'];

export const useGithubUsers = () => {
  const { db, connectionStatus } = useSurreal();

  const fetchGithubUsers = async (): Promise<GithubUser[]> => {
    if (connectionStatus !== 'connected' || !db) {
      throw new Error('Database not connected');
    }
    console.log("Fetching users via useGithubUsers hook...");
    const users = await db.select<GithubUser>('github_user');
    console.log("Users fetched in hook:", users.length);
    return users;
  };

  return useQuery<GithubUser[], Error>({
     queryKey: GITHUB_USERS_QUERY_KEY,
     queryFn: fetchGithubUsers,
     enabled: connectionStatus === 'connected',
     staleTime: 5 * 60 * 1000,
     refetchOnWindowFocus: false,
  });
};