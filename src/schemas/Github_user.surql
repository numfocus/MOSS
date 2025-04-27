DEFINE TABLE github_user SCHEMAFULL
    PERMISSIONS
        FOR create FULL
        FOR select FULL
        FOR update FULL
        FOR delete FULL;

DEFINE FIELD id ON github_user TYPE int; -- GitHub's ID
DEFINE FIELD login ON github_user TYPE string;
DEFINE FIELD node_id ON github_user TYPE string;
DEFINE FIELD avatar_url ON github_user TYPE string;
DEFINE FIELD gravatar_id ON github_user TYPE option<string>;
DEFINE FIELD url ON github_user TYPE string;
DEFINE FIELD html_url ON github_user TYPE string;
DEFINE FIELD followers_url ON github_user TYPE string;
DEFINE FIELD following_url ON github_user TYPE string;
DEFINE FIELD gists_url ON github_user TYPE string;
DEFINE FIELD starred_url ON github_user TYPE string;
DEFINE FIELD subscriptions_url ON github_user TYPE string;
DEFINE FIELD organizations_url ON github_user TYPE string;
DEFINE FIELD repos_url ON github_user TYPE string;
DEFINE FIELD events_url ON github_user TYPE string;
DEFINE FIELD received_events_url ON github_user TYPE string;
DEFINE FIELD type ON github_user TYPE string;
DEFINE FIELD user_view_type ON github_user TYPE string;
DEFINE FIELD site_admin ON github_user TYPE bool;
DEFINE FIELD name ON github_user TYPE option<string>;
DEFINE FIELD company ON github_user TYPE option<string>;
DEFINE FIELD blog ON github_user TYPE string;
DEFINE FIELD location ON github_user TYPE string;
DEFINE FIELD email ON github_user TYPE option<string>;
DEFINE FIELD hireable ON github_user TYPE option<bool>;
DEFINE FIELD bio ON github_user TYPE text;
DEFINE FIELD twitter_username ON github_user TYPE option<string>;
DEFINE FIELD public_repos ON github_user TYPE int;
DEFINE FIELD public_gists ON github_user TYPE int;
DEFINE FIELD followers ON github_user TYPE int;
DEFINE FIELD following ON github_user TYPE int;
DEFINE FIELD created_at ON github_user TYPE datetime;
DEFINE FIELD updated_at ON github_user TYPE datetime;

-- Define indexes for unique fields
DEFINE INDEX unique_id ON github_user COLUMNS id UNIQUE; -- Index on GitHub's ID
DEFINE INDEX unique_login ON github_user COLUMNS login UNIQUE; -- Index on GitHub's login
