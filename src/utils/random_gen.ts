import type { GithubUser } from "@/types/GithubUser";
import type { GithubRepo } from "@/types/GithubRepo";

const getRandomBoolean = (): boolean => Math.random() < 0.5;

const getRandomInt = (min: number, max: number): number => {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min + 1)) + min;
};

const getRandomString = (length: number): string => {
    const characters = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += characters.charAt(Math.floor(Math.random() * characters.length));
    }
    return result;
};

const getRandomUrl = (): string => `https://example.com/${getRandomString(10)}`;

const getRandomDate = (): string => {
    const now = new Date();
    const past = new Date(now.getTime() - Math.random() * 365 * 24 * 60 * 60 * 1000);
    return past.toISOString();
};

const getRandomUserType = (): "User" | "Organization" => {
    return getRandomBoolean() ? "User" : "Organization";
};

const generateFakeGithubUser = (): GithubUser => {
    const login = getRandomString(8);
    const now = new Date().toISOString();
    const type = getRandomUserType();
    const userId = getRandomInt(10000, 99999);

    return {
        github_id: userId,
        login: login,
        node_id: `MDQ6VXNlcj${getRandomInt(1000000, 9999999)}`,
        avatar_url: getRandomUrl(),
        gravatar_id: getRandomBoolean() ? getRandomString(10) : null,
        url: `https://api.github.com/users/${login}`,
        html_url: `https://github.com/${login}`,
        followers_url: `https://api.github.com/users/${login}/followers`,
        following_url: `https://api.github.com/users/${login}/following{/other_user}`,
        gists_url: `https://api.github.com/users/${login}/gists{/gist_id}`,
        starred_url: `https://api.github.com/users/${login}/starred{/owner}{/repo}`,
        subscriptions_url: `https://api.github.com/users/${login}/subscriptions`,
        organizations_url: `https://api.github.com/users/${login}/orgs`,
        repos_url: `https://api.github.com/users/${login}/repos`,
        events_url: `https://api.github.com/users/${login}/events{/privacy}`,
        received_events_url: `https://api.github.com/users/${login}/received_events`,
        type: type,
        site_admin: getRandomBoolean(),
        name: `${getRandomString(5)} ${getRandomString(8)}`,
        company: getRandomBoolean() ? `${getRandomString(10)} Inc.` : null,
        blog: getRandomBoolean() ? getRandomUrl() : null,
        location: `${getRandomString(6)}, ${getRandomString(2).toUpperCase()}`,
        email: getRandomBoolean() ? `${login}@example.com` : null,
        hireable: getRandomBoolean() ? getRandomBoolean() : null,
        bio: getRandomBoolean() ? `Bio for ${login}: ${getRandomString(50)}` : null,
        twitter_username: getRandomBoolean() ? login : null,
        public_repos: getRandomInt(0, 50),
        public_gists: getRandomInt(0, 10),
        followers: getRandomInt(0, 500),
        following: getRandomInt(0, 100),
        created_at: getRandomDate(),
        updated_at: now,
    };
};

const generateFakeGithubRepo = (ownerLogin: string): GithubRepo => {
    const repoName = `${getRandomString(6)}-repo`;
    const now = new Date().toISOString();
    const repoId = getRandomInt(1000000, 9999999);

    return {
        github_id: repoId,
        node_id: `MDEwOlJlcG9zaXRvcnk${getRandomInt(10000000, 99999999)}`,
        name: repoName,
        full_name: `${ownerLogin}/${repoName}`,
        owner: ownerLogin,
        description: getRandomBoolean() ? `Description for ${repoName}: ${getRandomString(60)}` : null,
        private: getRandomBoolean(),
        fork: getRandomBoolean(),
        url: `https://api.github.com/repos/${ownerLogin}/${repoName}`,
        forks_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/forks`,
        keys_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/keys{/key_id}`,
        collaborators_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/collaborators{/collaborator}`,
        teams_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/teams`,
        hooks_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/hooks`,
        issue_events_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/issues/events{/number}`,
        events_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/events`,
        assignees_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/assignees{/user}`,
        branches_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/branches{/branch}`,
        tags_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/tags`,
        blobs_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/git/blobs{/sha}`,
        git_tags_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/git/tags{/sha}`,
        git_refs_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/git/refs{/sha}`,
        trees_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/git/trees{/sha}`,
        statuses_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/statuses/{sha}`,
        languages_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/languages`,
        stargazers_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/stargazers`,
        contributors_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/contributors`,
        subscribers_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/subscribers`,
        subscription_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/subscription`,
        commits_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/commits{/sha}`,
        git_commits_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/git/commits{/sha}`,
        comments_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/comments{/number}`,
        issue_comment_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/issues/comments{/number}`,
        contents_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/contents/{+path}`,
        compare_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/compare/{base}...{head}`,
        merges_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/merges`,
        archive_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/{archive_format}{/ref}`,
        downloads_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/downloads`,
        issues_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/issues{/number}`,
        pulls_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/pulls{/number}`,
        milestones_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/milestones{/number}`,
        notifications_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/notifications{?since,all,participating}`,
        labels_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/labels{/name}`,
        releases_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/releases{/id}`,
        deployments_url: `https://api.github.com/repos/${ownerLogin}/${repoName}/deployments`,
        created_at: getRandomDate(),
        updated_at: now,
        pushed_at: now,
        git_url: `git://github.com/${ownerLogin}/${repoName}.git`,
        ssh_url: `git@github.com:${ownerLogin}/${repoName}.git`,
        clone_url: `https://github.com/${ownerLogin}/${repoName}.git`,
        svn_url: `https://github.com/${ownerLogin}/${repoName}`,
        homepage: getRandomBoolean() ? getRandomUrl() : null,
        size: getRandomInt(100, 50000),
        stargazers_count: getRandomInt(0, 1000),
        watchers_count: getRandomInt(0, 1000),
        language: getRandomBoolean() ? getRandomElement(["TypeScript", "JavaScript", "Python", "Go", "Rust"]) : null,
        has_issues: getRandomBoolean(),
        has_projects: getRandomBoolean(),
        has_downloads: getRandomBoolean(),
        has_wiki: getRandomBoolean(),
        has_pages: getRandomBoolean(),
        has_discussions: getRandomBoolean(),
        forks_count: getRandomInt(0, 100),
        mirror_url: null,
        archived: getRandomBoolean(),
        disabled: getRandomBoolean(),
        open_issues_count: getRandomInt(0, 50),
        license: getRandomBoolean() ? "MIT" : null,
        allow_forking: getRandomBoolean(),
        is_template: getRandomBoolean(),
        web_commit_signoff_required: getRandomBoolean(),
        topics: Array.from({ length: getRandomInt(0, 5) }, () => getRandomString(8)),
        visibility: getRandomBoolean() ? "public" : "private",
        forks: getRandomInt(0, 100),
        open_issues: getRandomInt(0, 50),
        watchers: getRandomInt(0, 1000),
        default_branch: "main",
        temp_clone_token: null,
        network_count: getRandomInt(0, 100),
        subscribers_count: getRandomInt(0, 100),
        html_url: `https://github.com/${ownerLogin}/${repoName}`,
        is_fork: getRandomBoolean(),
    };
};

const getRandomElement = <T>(arr: T[]): T => {
    if (arr.length === 0) {
        throw new Error("Cannot get random element from an empty array.");
    }
    const index = Math.floor(Math.random() * arr.length);
    return arr[index];
};


const generateFakeGithubUsers = (count: number): GithubUser[] => {
    return Array.from({ length: count }, generateFakeGithubUser);
};

const generateFakeGithubRepos = (count: number, ownerLogins: string[]): GithubRepo[] => {
    return Array.from({ length: count }, () => generateFakeGithubRepo(getRandomElement(ownerLogins)));
};


const randomGen = {
    getRandomBoolean,
    getRandomInt,
    getRandomString,
    getRandomUrl,
    getRandomDate,
    getRandomUserType,
    getRandomElement,
    generateFakeGithubUser,
    generateFakeGithubRepo,
    generateFakeGithubUsers,
    generateFakeGithubRepos,
};

export default randomGen;
