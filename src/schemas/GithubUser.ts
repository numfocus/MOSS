import type { Surreal } from 'surrealdb';

export async function defineGithubUserSchema(db: Surreal) {
  try {
    await db.query(`
      DEFINE TABLE github_user SCHEMAFULL
        PERMISSIONS
          FOR select, create, update, delete FULL;

      DEFINE FIELD login ON github_user TYPE string;
      DEFINE FIELD github_id ON github_user TYPE number;
      DEFINE FIELD node_id ON github_user TYPE string;
      DEFINE FIELD avatar_url ON github_user TYPE string;
      DEFINE FIELD gravatar_id ON github_user TYPE option<string>;
      DEFINE FIELD url ON github_user TYPE option<string>;
      DEFINE FIELD html_url ON github_user TYPE string;
      DEFINE FIELD followers_url ON github_user TYPE option<string>;
      DEFINE FIELD following_url ON github_user TYPE option<string>;
      DEFINE FIELD gists_url ON github_user TYPE option<string>;
      DEFINE FIELD starred_url ON github_user TYPE option<string>;
      DEFINE FIELD subscriptions_url ON github_user TYPE option<string>;
      DEFINE FIELD organizations_url ON github_user TYPE option<string>;
      DEFINE FIELD repos_url ON github_user TYPE option<string>;
      DEFINE FIELD events_url ON github_user TYPE option<string>;
      DEFINE FIELD received_events_url ON github_user TYPE option<string>;
      DEFINE FIELD type ON github_user TYPE string;
      DEFINE FIELD site_admin ON github_user TYPE boolean;
      DEFINE FIELD name ON github_user TYPE option<string>;
      DEFINE FIELD company ON github_user TYPE option<string>;
      DEFINE FIELD blog ON github_user TYPE option<string>;
      DEFINE FIELD location ON github_user TYPE option<string>;
      DEFINE FIELD email ON github_user TYPE option<string>;
      DEFINE FIELD hireable ON github_user TYPE option<boolean>;
      DEFINE FIELD bio ON github_user TYPE option<string>;
      DEFINE FIELD twitter_username ON github_user TYPE option<string>;
      DEFINE FIELD public_repos ON github_user TYPE option<number>;
      DEFINE FIELD public_gists ON github_user TYPE option<number>;
      DEFINE FIELD followers ON github_user TYPE option<number>;
      DEFINE FIELD following ON github_user TYPE option<number>;
      DEFINE FIELD created_at ON github_user TYPE option<string>;
      DEFINE FIELD updated_at ON github_user TYPE option<string>;
      DEFINE FIELD contributions ON github_user TYPE option<number>;
      
      -- Set login as the record ID
      DEFINE INDEX login_idx ON github_user FIELDS login UNIQUE;
    `);
    console.log("Defined github_user table schema from GithubUser.ts.");
  } catch (err) {
    console.error("Error defining github_user table schema:", err);
  }
}
