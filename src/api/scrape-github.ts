import axios, { AxiosInstance, AxiosError } from 'axios';

const GITHUB_TOKEN = import.meta.env.VITE_GITHUB_TOKEN;
if (!GITHUB_TOKEN) {
  console.warn(
    'VITE_GITHUB_TOKEN environment variable is not set. Requests may be rate-limited.'
  );
}

const GITHUB_API_BASE_URL = 'https://api.github.com';

const githubApi: AxiosInstance = axios.create({
  baseURL: GITHUB_API_BASE_URL,
  headers: {
    Accept: 'application/vnd.github.v3+json',
    ...(GITHUB_TOKEN ? { Authorization: `token ${GITHUB_TOKEN}` } : {}),
  },
});

interface ApiErrorResponse {
  message: string;
  documentation_url?: string;
}

async function fetchGitHubData(apiUrl: string): Promise<any> {  
  try {
    const response = await githubApi.get(apiUrl);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError<ApiErrorResponse>;
      if (axiosError.response) {
        const apiError = axiosError.response.data;
        console.error(`GitHub API Error: ${apiError.message}`);
        if (apiError.documentation_url) {
          console.error(`Documentation: ${apiError.documentation_url}`);
        }
        throw new Error(`GitHub API Error: ${apiError.message}`);
      } else {
        console.error('An unexpected error occurred:', axiosError.message);
        throw new Error('An unexpected error occurred.');
      }
    } else {
      console.error('An unexpected error occurred:', (error as Error).message);
      throw new Error('An unexpected error occurred.');
    }
  }
}

export async function getGitHubUser(username: string): Promise<any> {
  return fetchGitHubData(`/users/${username}`);
}

export async function getGitHubUserRepos(
  username: string
): Promise<any> {
  return fetchGitHubData(`/users/${username}/repos`);
}

export async function getGitHubRepo(repoIdentifier: string): Promise<any> {
  return fetchGitHubData(`/repos/${repoIdentifier}`);
}
