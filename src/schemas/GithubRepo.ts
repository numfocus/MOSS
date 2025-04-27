import type { Surreal } from 'surrealdb';

export async function defineGithubRepoSchema(db: Surreal) {
  try {
    await db.query(`
      DEFINE TABLE github_repo SCHEMAFULL
        PERMISSIONS
          FOR select, create, update, delete FULL;

      DEFINE FIELD github_id ON github_repo TYPE number;
      DEFINE FIELD node_id ON github_repo TYPE string;
      DEFINE FIELD name ON github_repo TYPE string;
      DEFINE FIELD full_name ON github_repo TYPE string;
      DEFINE FIELD owner ON github_repo TYPE string;
      DEFINE FIELD description ON github_repo TYPE string;
      DEFINE FIELD is_fork ON github_repo TYPE boolean;
      DEFINE FIELD url ON github_repo TYPE string;
      DEFINE FIELD forks_url ON github_repo TYPE string;
      DEFINE FIELD keys_url ON github_repo TYPE string;
      DEFINE FIELD collaborators_url ON github_repo TYPE string;
      DEFINE FIELD teams_url ON github_repo TYPE string;
      DEFINE FIELD hooks_url ON github_repo TYPE string;
      DEFINE FIELD issue_events_url ON github_repo TYPE string;
      DEFINE FIELD events_url ON github_repo TYPE string;
      DEFINE FIELD assignees_url ON github_repo TYPE string;
      DEFINE FIELD branches_url ON github_repo TYPE string;
      DEFINE FIELD tags_url ON github_repo TYPE string;
      DEFINE FIELD blobs_url ON github_repo TYPE string;
      DEFINE FIELD git_tags_url ON github_repo TYPE string;
      DEFINE FIELD git_refs_url ON github_repo TYPE string;
      DEFINE FIELD trees_url ON github_repo TYPE string;
      DEFINE FIELD statuses_url ON github_repo TYPE string;
      DEFINE FIELD languages_url ON github_repo TYPE string;
      DEFINE FIELD stargazers_url ON github_repo TYPE string;
      DEFINE FIELD contributors_url ON github_repo TYPE string;
      DEFINE FIELD subscribers_url ON github_repo TYPE string;
      DEFINE FIELD subscription_url ON github_repo TYPE string;
      DEFINE FIELD commits_url ON github_repo TYPE string;
      DEFINE FIELD git_commits_url ON github_repo TYPE string;
      DEFINE FIELD comments_url ON github_repo TYPE string;
      DEFINE FIELD issue_comment_url ON github_repo TYPE string;
      DEFINE FIELD contents_url ON github_repo TYPE string;
      DEFINE FIELD compare_url ON github_repo TYPE string;
      DEFINE FIELD merges_url ON github_repo TYPE string;
      DEFINE FIELD archive_url ON github_repo TYPE string;
      DEFINE FIELD downloads_url ON github_repo TYPE string;
      DEFINE FIELD issues_url ON github_repo TYPE string;
      DEFINE FIELD pulls_url ON github_repo TYPE string;
      DEFINE FIELD milestones_url ON github_repo TYPE string;
      DEFINE FIELD notifications_url ON github_repo TYPE string;
      DEFINE FIELD labels_url ON github_repo TYPE string;
      DEFINE FIELD releases_url ON github_repo TYPE string;
      DEFINE FIELD deployments_url ON github_repo TYPE string;
      DEFINE FIELD created_at ON github_repo TYPE string;
      DEFINE FIELD updated_at ON github_repo TYPE string;
      DEFINE FIELD pushed_at ON github_repo TYPE string;
      DEFINE FIELD git_url ON github_repo TYPE string;
      DEFINE FIELD ssh_url ON github_repo TYPE string;
      DEFINE FIELD clone_url ON github_repo TYPE string;
      DEFINE FIELD svn_url ON github_repo TYPE string;
      DEFINE FIELD homepage ON github_repo TYPE string;
      DEFINE FIELD size ON github_repo TYPE number;
      DEFINE FIELD stargazers_count ON github_repo TYPE number;
      DEFINE FIELD watchers_count ON github_repo TYPE number;
      DEFINE FIELD language ON github_repo TYPE string;
      DEFINE FIELD has_issues ON github_repo TYPE boolean;
      DEFINE FIELD has_projects ON github_repo TYPE boolean;
      DEFINE FIELD has_downloads ON github_repo TYPE boolean;
      DEFINE FIELD has_wiki ON github_repo TYPE boolean;
      DEFINE FIELD has_pages ON github_repo TYPE boolean;
      DEFINE FIELD has_discussions ON github_repo TYPE boolean;
      DEFINE FIELD forks_count ON github_repo TYPE number;
      DEFINE FIELD mirror_url ON github_repo TYPE string;
      DEFINE FIELD archived ON github_repo TYPE boolean;
      DEFINE FIELD disabled ON github_repo TYPE boolean;
      DEFINE FIELD open_issues_count ON github_repo TYPE number;
      DEFINE FIELD license ON github_repo TYPE string;
      DEFINE FIELD allow_forking ON github_repo TYPE boolean;
      DEFINE FIELD is_template ON github_repo TYPE boolean;
      DEFINE FIELD web_commit_signoff_required ON github_repo TYPE boolean;
      DEFINE FIELD topics ON github_repo TYPE array;
      DEFINE FIELD visibility ON github_repo TYPE string;
      DEFINE FIELD forks ON github_repo TYPE number;
      DEFINE FIELD open_issues ON github_repo TYPE number;
      DEFINE FIELD watchers ON github_repo TYPE number;
      DEFINE FIELD default_branch ON github_repo TYPE string;
      DEFINE FIELD temp_clone_token ON github_repo TYPE string;
      DEFINE FIELD network_count ON github_repo TYPE number;
      DEFINE FIELD subscribers_count ON github_repo TYPE number;
      DEFINE FIELD html_url ON github_repo TYPE string;
    `);
    console.log("Defined github_repo table schema from GithubRepo.ts.");
  } catch (err) {
    console.error("Error defining github_repo table schema:", err);
  }
}
