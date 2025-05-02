# services/github_ingestion.py
import base64
import yaml
import logging
from datetime import datetime, timezone
import uuid

from db.database import get_db_session
from clients.github_client import GitHubClient
from utils.common import parse_datetime, save_json_field, extract_dois_from_text, get_current_time
from services.discovery import record_discovery, start_new_chain
from services.entity_service import update_or_create_repository, update_or_create_org, update_or_create_user, store_doi
from models.models import (
    Repository, Branch, Tag, Commit, Label, Milestone, Release, Webhook, 
    Event, Workflow, WorkflowRun, Issue, IssueComment, PullRequest, PRReviewComment,
    PullRequestReview, DiscoveryEvent, DOI
)

logger = logging.getLogger(__name__)

def parse_citation_cff(session, client, owner, repo_name, repository, chain_id=None, branch_id=None, trigger_input=None, keyword=None):
    """
    Parse CITATION.cff file from a repository and extract DOI information.
    """
    cff_json = client.get_citation_cff(owner, repo_name)
    if not cff_json or "content" not in cff_json:
        logger.info(f"No CITATION.cff found or content is missing for {owner}/{repo_name}.")
        return None
    
    try:
        cff_decoded = base64.b64decode(cff_json["content"]).decode("utf-8", errors="ignore")
        cff_data = yaml.safe_load(cff_decoded)
        if "doi" in cff_data:
            doi_str = cff_data["doi"]
            discovery_details = f"DOI discovered from CITATION.cff in repository '{repository.full_name}'"
            doi_obj = store_doi(
                session, repository.id, doi_str, source="CITATION.cff",
                discovery_method="citation_doi_ingestion",
                discovery_details=discovery_details,
                trigger_input=trigger_input,
                keyword=keyword,
                chain_id=chain_id,
                branch_id=branch_id,
                step=2
            )
            return doi_str
    except Exception as e:
        logger.warning(f"Error parsing CITATION.cff for {owner}/{repo_name}: {e}")
    
    return None

def ingest_github_repository(session, owner: str, repo_name: str, token: str = None, 
                             discovery_method: str = "direct_ingestion", 
                             discovery_details: str = None, trigger_input: str = None,
                             chain_id: str = None, keyword: str = None):
    """
    Ingest a repository from GitHub and record its discovery events.
    This function performs all GitHub-specific ingestion (repository data, branches,
    tags, commits, labels, milestones, releases, webhooks, events, collaborators,
    workflows, workflow runs, issues, PRs, and associated comments/reviews).
    """
    client = GitHubClient(token=token, default_timeout=30)
    repo_data = client.get_repository(owner, repo_name)
    if not repo_data:
        raise ValueError(f"Failed to fetch repository data for {owner}/{repo_name}.")
    
    # Start a new discovery chain for this ingestion session if not provided.
    if chain_id is None:
        chain_id = start_new_chain()
    
    # Generate base branch ID for this repository ingestion
    base_branch_id = str(uuid.uuid4())
    
    # Record the repository (generation event) as step 1.
    if discovery_details is None:
        discovery_details = f"Repository URL: https://github.com/{owner}/{repo_name}"
    
    repository = update_or_create_repository(
        session, client, repo_data,
        discovery_method=discovery_method,
        discovery_details=discovery_details,
        trigger_input=trigger_input,
        keyword=keyword,
        chain_id=chain_id,
        branch_id=base_branch_id,
        step=1
    )
    
    # Record the repository owner as step 2.
    if repo_data["owner"]["type"] == "Organization":
        org = update_or_create_org(
            session, 
            client, 
            repo_data["owner"],
            discovery_method="repository_owner_ingestion",
            discovery_details=f"Organization discovered as owner of repository '{repository.full_name}'",
            trigger_input=trigger_input,
            keyword=keyword,
            chain_id=chain_id,
            branch_id=base_branch_id,
            step=2
        )
    else:
        user = update_or_create_user(
            session, 
            client, 
            repo_data["owner"],
            discovery_method="repository_owner_ingestion",
            discovery_details=f"User discovered as owner of repository '{repository.full_name}'",
            trigger_input=trigger_input,
            keyword=keyword,
            chain_id=chain_id,
            branch_id=base_branch_id,
            step=2
        )
    
    # Record branches (step 2)
    branches = client.get_branches(owner, repo_name)
    for branch_data in branches:
        exists = session.query(Branch).filter_by(name=branch_data["name"], repository_id=repository.id).first()
        if not exists:
            new_branch = Branch(
                name=branch_data["name"],
                commit_sha=branch_data["commit"]["sha"],
                repository_id=repository.id
            )
            new_branch.ingested_at = get_current_time()
            session.add(new_branch)
            record_discovery(
                new_branch, 
                "branch_ingestion", 
                f"Branch from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
    
    # Record tags (step 2)
    tags = client.get_tags(owner, repo_name)
    for tag_data in tags:
        exists = session.query(Tag).filter_by(name=tag_data["name"], repository_id=repository.id).first()
        if not exists:
            new_tag = Tag(
                name=tag_data["name"],
                commit_sha=tag_data["commit"]["sha"],
                repository_id=repository.id
            )
            new_tag.ingested_at = get_current_time()
            session.add(new_tag)
            record_discovery(
                new_tag, 
                "tag_ingestion", 
                f"Tag from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
    
    # Record commits (step 2)
    commits = client.get_commits(owner, repo_name)
    for commit_data in commits[:100]:
        sha = commit_data["sha"]
        exists = session.query(Commit).filter_by(sha=sha).first()
        if not exists:
            commit_info = commit_data.get("commit", {})
            author_info = commit_info.get("author", {})
            committer_info = commit_info.get("committer", {})
            commit_obj = Commit(
                sha=sha,
                message=commit_info.get("message"),
                author_name=author_info.get("name"),
                author_email=author_info.get("email"),
                committer_name=committer_info.get("name"),
                committer_email=committer_info.get("email"),
                date=parse_datetime(author_info.get("date")),
                repository_id=repository.id,
                raw_data=save_json_field(commit_data)
            )
            commit_obj.ingested_at = get_current_time()
            session.add(commit_obj)
            record_discovery(
                commit_obj, 
                "commit_ingestion", 
                f"Commit from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
    
    # Record labels (step 2)
    labels = client.get_labels(owner, repo_name)
    for label_data in labels:
        if not session.query(Label).filter_by(id=label_data["id"]).first():
            label = Label(
                id=label_data["id"],
                name=label_data["name"],
                color=label_data.get("color"),
                description=label_data.get("description"),
                repository_id=repository.id,
                raw_data=save_json_field(label_data)
            )
            label.ingested_at = get_current_time()
            session.add(label)
            record_discovery(
                label, 
                "label_ingestion", 
                f"Label from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
    
    # Record milestones (step 2)
    milestones = client.get_milestones(owner, repo_name)
    for ms_data in milestones:
        if not session.query(Milestone).filter_by(id=ms_data["id"]).first():
            milestone = Milestone(
                id=ms_data["id"],
                title=ms_data["title"],
                description=ms_data.get("description"),
                state=ms_data.get("state"),
                due_on=parse_datetime(ms_data.get("due_on")),
                repository_id=repository.id,
                raw_data=save_json_field(ms_data)
            )
            milestone.ingested_at = get_current_time()
            session.add(milestone)
            record_discovery(
                milestone, 
                "milestone_ingestion", 
                f"Milestone from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
    
    # Record releases (step 2)
    releases = client.get_releases(owner, repo_name)
    for rel_data in releases:
        if not session.query(Release).filter_by(id=rel_data["id"]).first():
            release = Release(
                id=rel_data["id"],
                tag_name=rel_data.get("tag_name"),
                name=rel_data.get("name"),
                body=rel_data.get("body"),
                draft=rel_data.get("draft", False),
                prerelease=rel_data.get("prerelease", False),
                created_at=parse_datetime(rel_data.get("created_at")),
                published_at=parse_datetime(rel_data.get("published_at")),
                repository_id=repository.id,
                raw_data=save_json_field(rel_data)
            )
            release.ingested_at = get_current_time()
            session.add(release)
            record_discovery(
                release, 
                "release_ingestion", 
                f"Release from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
    
    # Record webhooks (step 2)
    webhooks = client.get_webhooks(owner, repo_name)
    for hook_data in webhooks:
        if not session.query(Webhook).filter_by(id=hook_data["id"]).first():
            webhook = Webhook(
                id=hook_data["id"],
                name=hook_data.get("name"),
                config=save_json_field(hook_data.get("config")),
                events=",".join(hook_data.get("events", [])),
                active=hook_data.get("active", False),
                repository_id=repository.id,
                raw_data=save_json_field(hook_data)
            )
            webhook.ingested_at = get_current_time()
            session.add(webhook)
            record_discovery(
                webhook, 
                "webhook_ingestion", 
                f"Webhook from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
    
    # Record events (step 2)
    events = client.get_events(owner, repo_name)
    for event_data in events:
        event_obj = Event(
            type=event_data.get("type"),
            created_at=parse_datetime(event_data.get("created_at")),
            repository_id=repository.id,
            raw_data=save_json_field(event_data)
        )
        event_obj.ingested_at = get_current_time()
        session.add(event_obj)
        record_discovery(
            event_obj, 
            "event_ingestion", 
            f"Event from repo {repository.full_name}", 
            chain_id=chain_id,
            trigger_input=trigger_input, 
            keyword=keyword,
            branch_id=base_branch_id, 
            step=2
        )
    
    # Record collaborators (step 2)
    collaborators = client.get_collaborators(owner, repo_name)
    for collab in collaborators:
        collab_user = update_or_create_user(
            session, 
            client, 
            collab,
            discovery_method="collaborator_ingestion",
            discovery_details=f"User discovered as collaborator on repository '{repository.full_name}'",
            trigger_input=trigger_input,
            keyword=keyword,
            chain_id=chain_id,
            branch_id=base_branch_id,
            step=2
        )
    
    # Record workflows (step 2)
    workflows = client.get_workflows(owner, repo_name)
    for wf in workflows:
        if not session.query(Workflow).filter_by(id=wf["id"]).first():
            workflow = Workflow(
                id=wf["id"],
                name=wf.get("name"),
                state=wf.get("state"),
                repository_id=repository.id,
                raw_data=save_json_field(wf)
            )
            workflow.ingested_at = get_current_time()
            session.add(workflow)
            record_discovery(
                workflow, 
                "workflow_ingestion", 
                f"Workflow from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
    
    # Record workflow runs (step 2)
    workflow_runs = client.get_workflow_runs(owner, repo_name)
    for run in workflow_runs:
        if not session.query(WorkflowRun).filter_by(id=run["id"]).first():
            wrun = WorkflowRun(
                id=run["id"],
                name=run.get("name"),
                status=run.get("status"),
                conclusion=run.get("conclusion"),
                created_at=parse_datetime(run.get("created_at")),
                updated_at=parse_datetime(run.get("updated_at")),
                repository_id=repository.id,
                raw_data=save_json_field(run)
            )
            wrun.ingested_at = get_current_time()
            session.add(wrun)
            record_discovery(
                wrun, 
                "workflow_run_ingestion", 
                f"Workflow run from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
    
    # Process issues and their comments (step 2)
    issues_url = f"{client.BASE_URL}/repos/{owner}/{repo_name}/issues"
    issues = client.get_all_pages(issues_url, params={"state": "all"})
    for issue_data in issues:
        if "pull_request" in issue_data:
            continue
        user = update_or_create_user(
            session, client, issue_data["user"],
            discovery_method="issue_ingestion",
            discovery_details=f"Issue discovered from issue {issue_data['number']} on repository '{repository.full_name}'",
            trigger_input=trigger_input,
            keyword=keyword,
            chain_id=chain_id,
            branch_id=base_branch_id,
            step=2
        )
        
        if not session.query(Issue).filter_by(id=issue_data["id"]).first():
            issue = Issue(
                id=issue_data["id"],
                number=issue_data["number"],
                title=issue_data["title"],
                body=issue_data.get("body"),
                state=issue_data["state"],
                created_at=parse_datetime(issue_data["created_at"]),
                updated_at=parse_datetime(issue_data["updated_at"]),
                closed_at=parse_datetime(issue_data.get("closed_at")),
                user_id=user.id if user else None,
                repository_id=repository.id,
                raw_data=save_json_field(issue_data)
            )
            issue.ingested_at = get_current_time()
            session.add(issue)
            record_discovery(
                issue, 
                "issue_ingestion", 
                f"Issue from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
            
            session.commit()
            comments_url = f"{client.BASE_URL}/repos/{owner}/{repo_name}/issues/{issue_data['number']}/comments"
            comments = client.get_all_pages(comments_url)
            for comment_data in comments:
                comment_user = update_or_create_user(
                    session, client, comment_data.get("user"),
                    discovery_method="issue_comment_ingestion",
                    discovery_details=f"Issue comment on issue {issue.number} from repo {repository.full_name}",
                    trigger_input=trigger_input,
                    keyword=keyword,
                    chain_id=chain_id,
                    branch_id=base_branch_id,
                    step=2
                )
                
                if comment_user is None:
                    continue
                if not session.query(IssueComment).filter_by(id=comment_data["id"]).first():
                    comment = IssueComment(
                        id=comment_data["id"],
                        body=comment_data["body"],
                        created_at=parse_datetime(comment_data["created_at"]),
                        updated_at=parse_datetime(comment_data["updated_at"]),
                        user_id=comment_user.id,
                        issue_id=issue.id,
                        raw_data=save_json_field(comment_data)
                    )
                    comment.ingested_at = get_current_time()
                    session.add(comment)
                    record_discovery(
                        comment, 
                        "issue_comment_ingestion", 
                        f"Issue comment on issue {issue.number}", 
                        chain_id=chain_id,
                        trigger_input=trigger_input, 
                        keyword=keyword,
                        branch_id=base_branch_id, 
                        step=2
                    )
            session.commit()
    
    # Process pull requests and their comments/reviews (step 2)
    prs_url = f"{client.BASE_URL}/repos/{owner}/{repo_name}/pulls"
    pull_requests = client.get_all_pages(prs_url, params={"state": "all"})
    for pr_data in pull_requests:
        user = update_or_create_user(
            session, client, pr_data["user"],
            discovery_method="pr_ingestion",
            discovery_details=f"PR from repo {repository.full_name}",
            trigger_input=trigger_input,
            keyword=keyword,
            chain_id=chain_id,
            branch_id=base_branch_id,
            step=2
        )
        
        if not session.query(PullRequest).filter_by(id=pr_data["id"]).first():
            pr = PullRequest(
                id=pr_data["id"],
                number=pr_data["number"],
                title=pr_data["title"],
                body=pr_data.get("body"),
                state=pr_data["state"],
                created_at=parse_datetime(pr_data["created_at"]),
                updated_at=parse_datetime(pr_data["updated_at"]),
                merged_at=parse_datetime(pr_data.get("merged_at")),
                user_id=user.id if user else None,
                repository_id=repository.id,
                raw_data=save_json_field(pr_data)
            )
            pr.ingested_at = get_current_time()
            session.add(pr)
            record_discovery(
                pr, 
                "pr_ingestion", 
                f"PR from repo {repository.full_name}", 
                chain_id=chain_id,
                trigger_input=trigger_input, 
                keyword=keyword,
                branch_id=base_branch_id, 
                step=2
            )
            
            session.commit()
            pr_comments_url = f"{client.BASE_URL}/repos/{owner}/{repo_name}/pulls/{pr_data['number']}/comments"
            pr_comments = client.get_all_pages(pr_comments_url)
            for pr_comment_data in pr_comments:
                comment_user = update_or_create_user(
                    session, client, pr_comment_data.get("user"),
                    discovery_method="pr_comment_ingestion",
                    discovery_details=f"User discovered from PR comment on PR {pr_data['number']} in repo {repository.full_name}",
                    trigger_input=trigger_input,
                    keyword=keyword,
                    chain_id=chain_id,
                    branch_id=base_branch_id,
                    step=2
                )
                
                if comment_user is None:
                    continue
                if not session.query(PRReviewComment).filter_by(id=pr_comment_data["id"]).first():
                    pr_comment = PRReviewComment(
                        id=pr_comment_data["id"],
                        body=pr_comment_data["body"],
                        created_at=parse_datetime(pr_comment_data["created_at"]),
                        updated_at=parse_datetime(pr_comment_data["updated_at"]),
                        user_id=comment_user.id,
                        pr_id=pr.id,
                        raw_data=save_json_field(pr_comment_data)
                    )
                    pr_comment.ingested_at = get_current_time()
                    session.add(pr_comment)
                    record_discovery(
                        pr_comment, 
                        "pr_comment_ingestion", 
                        f"PR comment on PR {pr.number}", 
                        chain_id=chain_id,
                        trigger_input=trigger_input, 
                        keyword=keyword,
                        branch_id=base_branch_id, 
                        step=2
                    )
            pr_reviews_url = f"{client.BASE_URL}/repos/{owner}/{repo_name}/pulls/{pr_data['number']}/reviews"
            pr_reviews = client.get(pr_reviews_url)
            if pr_reviews and isinstance(pr_reviews, list):
                for review_data in pr_reviews:
                    if not session.query(PullRequestReview).filter_by(id=review_data["id"]).first():
                        review_user = update_or_create_user(
                            session, client, review_data.get("user"),
                            discovery_method="pr_review_ingestion",
                            discovery_details=f"User discovered from PR review on PR {pr_data['number']} in repo {repository.full_name}",
                            trigger_input=trigger_input,
                            keyword=keyword,
                            chain_id=chain_id,
                            branch_id=base_branch_id,
                            step=2
                        )
                        
                        if review_user is None:
                            continue
                        new_review = PullRequestReview(
                            id=review_data["id"],
                            user_id=review_user.id,
                            pr_id=pr.id,
                            state=review_data["state"],
                            submitted_at=parse_datetime(review_data.get("submitted_at")),
                            body=review_data.get("body"),
                            raw_data=save_json_field(review_data)
                        )
                        new_review.ingested_at = get_current_time()
                        session.add(new_review)
                        record_discovery(
                            new_review, 
                            "pr_review_ingestion", 
                            f"PR review on PR {pr.number}", 
                            chain_id=chain_id,
                            trigger_input=trigger_input, 
                            keyword=keyword,
                            branch_id=base_branch_id, 
                            step=2
                        )
                session.commit()
    
    # Process Readme and CITATION.cff
    readme = client.get_readme(owner, repo_name)
    readme_dois = []
    if readme and "content" in readme:
        decoded_readme = base64.b64decode(readme["content"]).decode("utf-8", errors="ignore")
        readme_dois = extract_dois_from_text(decoded_readme)
        for doi_str in readme_dois:
            doi_obj = store_doi(
                session, repository.id, doi_str, source="README",
                discovery_method="readme_doi_ingestion",
                discovery_details=f"DOI discovered from README in repository '{repository.full_name}'",
                trigger_input=trigger_input,
                keyword=keyword,
                chain_id=chain_id,
                branch_id=base_branch_id,
                step=2
            )
        repository.raw_data = "\nReadme: " + save_json_field(readme)
        repository.ingested_at = get_current_time()
    
    logger.info("Attempting to fetch CITATION.cff...")
    citation_doi = parse_citation_cff(
        session, client, owner, repo_name, repository,
        chain_id=chain_id,
        branch_id=base_branch_id,
        trigger_input=trigger_input,
        keyword=keyword
    )
    
    new_dois = set(readme_dois)
    if citation_doi:
        new_dois.add(citation_doi)
    if not new_dois:
        if repository.dois:
            repository.dois.clear()
    
    logger.info("Fetching discussions...")
    client.get_discussions(owner, repo_name)
    logger.info("GitHub repository ingestion complete.")
    
    return repository, base_branch_id