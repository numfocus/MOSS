from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Table, Float
from sqlalchemy.orm import relationship
from sqlalchemy_continuum import make_versioned
from datetime import datetime, timezone
import uuid

make_versioned(user_cls=None)
Base = declarative_base()

# --- Mixin for Ingestion Timestamp ---
class IngestedAtMixin:
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

# --- New Audit Table for Discovery Events ---
class DiscoveryEvent(Base):
    __tablename__ = 'discovery_events'
    id = Column(Integer, primary_key=True)
    chain_id = Column(String, nullable=False)          # Unique per ingestion session.
    branch_id = Column(String, nullable=False)         # Unique per discovery branch.
    step_number = Column(Integer, nullable=False)      # Depth relative to the trigger event.
    discovery_method = Column(String, nullable=False)
    details = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    ingestion_type = Column(String)                    # "direct ingestion" or "keyword ingestion"
    url = Column(String)                               # Populated for direct ingestion.
    keyword = Column(String)                           # Populated for keyword ingestion.
    object_type = Column(String, nullable=False)       # e.g. "Repository", "DOI", etc.
    object_id = Column(String, nullable=False)         # Stored as a string for flexibility.

    def __repr__(self):
        return (f"<DiscoveryEvent(chain_id='{self.chain_id}', branch_id='{self.branch_id}', "
                f"step_number={self.step_number}, object_type='{self.object_type}', "
                f"object_id='{self.object_id}')>")

# --- GitHub Models ---

class User(IngestedAtMixin, Base):
    __tablename__ = 'users'
    __versioned__ = {}
    id = Column(Integer, primary_key=True)  # GitHub user id
    login = Column(String, unique=True, index=True)
    name = Column(String)
    bio = Column(Text)
    avatar_url = Column(String)
    html_url = Column(String)
    type = Column(String)  # "User" or "Organization"
    site_admin = Column(Boolean)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    public_repos = Column(Integer)
    public_gists = Column(Integer)
    followers = Column(Integer)
    following = Column(Integer)
    email = Column(String)
    blog = Column(String)
    company = Column(String)
    location = Column(String)
    twitter_username = Column(String)
    raw_data = Column(Text)

    # Relationships
    issues = relationship('Issue', back_populates='user')
    pull_requests = relationship('PullRequest', back_populates='user')
    issue_comments = relationship('IssueComment', back_populates='user')
    pr_review_comments = relationship('PRReviewComment', back_populates='user')
    pull_request_reviews = relationship('PullRequestReview', back_populates='user')

    def __repr__(self):
        return f"<User(login='{self.login}', id={self.id})>"

class Organization(IngestedAtMixin, Base):
    __tablename__ = 'organizations'
    __versioned__ = {}
    id = Column(Integer, primary_key=True)  # GitHub organization id
    login = Column(String, unique=True, index=True)
    name = Column(String)
    description = Column(Text)
    raw_data = Column(Text)

    def __repr__(self):
        return f"<Organization(login='{self.login}', id={self.id})>"

class Repository(IngestedAtMixin, Base):
    __tablename__ = 'repositories'
    __versioned__ = {}
    id = Column(Integer, primary_key=True)  # GitHub repository id
    name = Column(String)
    full_name = Column(String, unique=True)
    owner_id = Column(Integer)  # Could be user or org ID
    private = Column(Boolean)
    description = Column(Text)
    homepage = Column(String)
    language = Column(String)
    topics = Column(Text)       # Comma-separated list from GitHub topics
    license = Column(Text)      # JSON string or license name
    visibility = Column(String)
    default_branch = Column(String)
    archived = Column(Boolean)
    disabled = Column(Boolean)
    fork = Column(Boolean)
    forks_count = Column(Integer)
    network_count = Column(Integer)
    watchers_count = Column(Integer)
    stargazers_count = Column(Integer)
    subscribers_count = Column(Integer)
    html_url = Column(String)
    clone_url = Column(String)
    ssh_url = Column(String)
    svn_url = Column(String)
    git_url = Column(String)
    mirror_url = Column(String)
    issues_url = Column(String)
    pulls_url = Column(String)
    commits_url = Column(String)
    branches_url = Column(String)
    tags_url = Column(String)
    contributors_url = Column(String)
    collaborators_url = Column(String)
    downloads_url = Column(String)
    size = Column(Integer)
    open_issues_count = Column(Integer)
    has_issues = Column(Boolean)
    has_wiki = Column(Boolean)
    has_downloads = Column(Boolean)
    has_projects = Column(Boolean)
    has_pages = Column(Boolean)
    is_template = Column(Boolean)
    raw_data = Column(Text)

    # Relationships – explicitly tie the DOI relationship to this repository.
    dois = relationship('DOI', back_populates='repository', cascade="all, delete-orphan", foreign_keys='DOI.repository_id')
    issues = relationship('Issue', back_populates='repository')
    pull_requests = relationship('PullRequest', back_populates='repository')
    branches = relationship('Branch', back_populates='repository')
    tags = relationship('Tag', back_populates='repository')
    commits = relationship('Commit', back_populates='repository')
    labels = relationship('Label', back_populates='repository')
    milestones = relationship('Milestone', back_populates='repository')
    releases = relationship('Release', back_populates='repository')
    webhooks = relationship('Webhook', back_populates='repository')
    events = relationship('Event', back_populates='repository')
    workflows = relationship('Workflow', back_populates='repository')
    workflow_runs = relationship('WorkflowRun', back_populates='repository')

    def __repr__(self):
        return f"<Repository(full_name='{self.full_name}', id={self.id})>"

class Branch(IngestedAtMixin, Base):
    __tablename__ = 'branches'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    commit_sha = Column(String)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    repository = relationship('Repository', back_populates='branches')

    def __repr__(self):
        return f"<Branch(name='{self.name}')>"

class Tag(IngestedAtMixin, Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    commit_sha = Column(String)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    repository = relationship('Repository', back_populates='tags')

    def __repr__(self):
        return f"<Tag(name='{self.name}')>"

class Commit(IngestedAtMixin, Base):
    __tablename__ = 'commits'
    sha = Column(String, primary_key=True)
    message = Column(Text)
    author_name = Column(String)
    author_email = Column(String)
    committer_name = Column(String)
    committer_email = Column(String)
    date = Column(DateTime)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    repository = relationship('Repository', back_populates='commits')
    raw_data = Column(Text)

    def __repr__(self):
        return f"<Commit(sha='{self.sha}', author='{self.author_name}', committer='{self.committer_name}')>"

class Issue(IngestedAtMixin, Base):
    __tablename__ = 'issues'
    id = Column(Integer, primary_key=True)  # GitHub issue id
    number = Column(Integer, index=True)
    title = Column(String)
    body = Column(Text)
    state = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    closed_at = Column(DateTime)
    user_id = Column(Integer, ForeignKey('users.id'))
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    raw_data = Column(Text)

    user = relationship('User', back_populates='issues')
    repository = relationship('Repository', back_populates='issues')
    comments = relationship('IssueComment', back_populates='issue')

    def __repr__(self):
        return f"<Issue(number={self.number}, title='{self.title}')>"

class PullRequest(IngestedAtMixin, Base):
    __tablename__ = 'pull_requests'
    id = Column(Integer, primary_key=True)  # GitHub PR id
    number = Column(Integer, index=True)
    title = Column(String)
    body = Column(Text)
    state = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    merged_at = Column(DateTime)
    user_id = Column(Integer, ForeignKey('users.id'))
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    raw_data = Column(Text)

    user = relationship('User', back_populates='pull_requests')
    repository = relationship('Repository', back_populates='pull_requests')
    review_comments = relationship('PRReviewComment', back_populates='pull_request')
    reviews = relationship('PullRequestReview', back_populates='pull_request')

    def __repr__(self):
        return f"<PullRequest(number={self.number}, title='{self.title}')>"

class IssueComment(IngestedAtMixin, Base):
    __tablename__ = 'issue_comments'
    id = Column(Integer, primary_key=True)  # GitHub comment id
    body = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    user_id = Column(Integer, ForeignKey('users.id'))
    issue_id = Column(Integer, ForeignKey('issues.id'))
    raw_data = Column(Text)

    user = relationship('User', back_populates='issue_comments')
    issue = relationship('Issue', back_populates='comments')

    def __repr__(self):
        return f"<IssueComment(id={self.id})>"

class PRReviewComment(IngestedAtMixin, Base):
    __tablename__ = 'pr_review_comments'
    id = Column(Integer, primary_key=True)  # GitHub review comment id
    body = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    user_id = Column(Integer, ForeignKey('users.id'))
    pr_id = Column(Integer, ForeignKey('pull_requests.id'))
    raw_data = Column(Text)

    user = relationship('User', back_populates='pr_review_comments')
    pull_request = relationship('PullRequest', back_populates='review_comments')

    def __repr__(self):
        return f"<PRReviewComment(id={self.id})>"

class PullRequestReview(IngestedAtMixin, Base):
    __tablename__ = 'pull_request_reviews'
    id = Column(Integer, primary_key=True)  # GitHub review id
    user_id = Column(Integer, ForeignKey('users.id'))
    pr_id = Column(Integer, ForeignKey('pull_requests.id'))
    state = Column(String)
    submitted_at = Column(DateTime)
    body = Column(Text)
    raw_data = Column(Text)

    user = relationship("User", back_populates="pull_request_reviews")
    pull_request = relationship("PullRequest", back_populates="reviews")

    def __repr__(self):
        return f"<PullRequestReview(id={self.id}, state='{self.state}')>"

class Label(IngestedAtMixin, Base):
    __tablename__ = 'labels'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    color = Column(String)
    description = Column(Text)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    raw_data = Column(Text)

    repository = relationship('Repository', back_populates='labels')

    def __repr__(self):
        return f"<Label(name='{self.name}')>"

class Milestone(IngestedAtMixin, Base):
    __tablename__ = 'milestones'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(Text)
    state = Column(String)
    due_on = Column(DateTime)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    raw_data = Column(Text)

    repository = relationship('Repository', back_populates='milestones')

    def __repr__(self):
        return f"<Milestone(title='{self.title}')>"

class Release(IngestedAtMixin, Base):
    __tablename__ = 'releases'
    id = Column(Integer, primary_key=True)
    tag_name = Column(String)
    name = Column(String)
    body = Column(Text)
    draft = Column(Boolean)
    prerelease = Column(Boolean)
    created_at = Column(DateTime)
    published_at = Column(DateTime)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    raw_data = Column(Text)

    repository = relationship('Repository', back_populates='releases')

    def __repr__(self):
        return f"<Release(tag_name='{self.tag_name}')>"

class Webhook(IngestedAtMixin, Base):
    __tablename__ = 'webhooks'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    config = Column(Text)
    events = Column(Text)  # Comma-separated events list
    active = Column(Boolean)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    raw_data = Column(Text)

    repository = relationship('Repository', back_populates='webhooks')

    def __repr__(self):
        return f"<Webhook(name='{self.name}', id={self.id})>"

class Event(IngestedAtMixin, Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String)
    created_at = Column(DateTime)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    raw_data = Column(Text)

    repository = relationship('Repository', back_populates='events')

    def __repr__(self):
        return f"<Event(type='{self.type}')>"

class Workflow(IngestedAtMixin, Base):
    __tablename__ = 'workflows'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    state = Column(String)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    raw_data = Column(Text)

    repository = relationship('Repository', back_populates='workflows')

    def __repr__(self):
        return f"<Workflow(name='{self.name}', id={self.id})>"

class WorkflowRun(IngestedAtMixin, Base):
    __tablename__ = 'workflow_runs'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    status = Column(String)
    conclusion = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    repository_id = Column(Integer, ForeignKey('repositories.id'))
    raw_data = Column(Text)

    repository = relationship('Repository', back_populates='workflow_runs')

    def __repr__(self):
        return f"<WorkflowRun(id={self.id})>"

class DOI(IngestedAtMixin, Base):
    __tablename__ = 'dois'
    __versioned__ = {}
    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False)
    doi = Column(String, index=True, nullable=False)
    source = Column(String, nullable=True)
    doi_metadata = Column(Text, nullable=True)
    
    repository = relationship('Repository', back_populates='dois')
    
    def __repr__(self):
        return f"<DOI(doi='{self.doi}', repo_id={self.repository_id}, source='{self.source}')>"

# --- OpenAlex Models and Association Tables ---

openalex_work_authors = Table(
    'openalex_work_authors', Base.metadata,
    Column('work_id', Integer, ForeignKey('openalex_works.id')),
    Column('author_id', Integer, ForeignKey('openalex_authors.id'))
)

openalex_author_institutions = Table(
    'openalex_author_institutions', Base.metadata,
    Column('author_id', Integer, ForeignKey('openalex_authors.id')),
    Column('institution_id', Integer, ForeignKey('openalex_institutions.id'))
)

openalex_work_topics = Table(
    'openalex_work_topics', Base.metadata,
    Column('work_id', Integer, ForeignKey('openalex_works.id')),
    Column('topic_id', Integer, ForeignKey('openalex_topics.id'))
)

openalex_citations = Table(
    'openalex_citations', Base.metadata,
    Column('citing_work_id', Integer, ForeignKey('openalex_works.id'), primary_key=True),
    Column('cited_work_id', Integer, ForeignKey('openalex_works.id'), primary_key=True)
)

class OpenAlexWork(IngestedAtMixin, Base):
    __tablename__ = 'openalex_works'
    id = Column(Integer, primary_key=True, autoincrement=True)
    openalex_id = Column(String, unique=True, index=True)
    doi = Column(String, index=True)
    title = Column(String)
    publication_year = Column(Integer)
    abstract = Column(Text)
    type = Column(String)
    url = Column(String)
    fully_fetched = Column(Boolean, default=True)
    raw_data = Column(Text)

    venue_id = Column(Integer, ForeignKey('openalex_venues.id'))
    venue = relationship("OpenAlexVenue", back_populates="works")

    authors = relationship("OpenAlexAuthor", secondary=openalex_work_authors, back_populates="works")
    topics = relationship("OpenAlexTopic", secondary=openalex_work_topics, back_populates="works")
    cited_works = relationship(
        "OpenAlexWork",
        secondary=openalex_citations,
        primaryjoin=id == openalex_citations.c.citing_work_id,
        secondaryjoin=id == openalex_citations.c.cited_work_id,
        backref="citing_works"
    )

    def __repr__(self):
        return f"<OpenAlexWork(doi='{self.doi}', title='{self.title}')>"

class OpenAlexAuthor(IngestedAtMixin, Base):
    __tablename__ = 'openalex_authors'
    id = Column(Integer, primary_key=True, autoincrement=True)
    openalex_id = Column(String, unique=True, index=True)
    display_name = Column(String)
    orcid = Column(String)
    works_count = Column(Integer)
    raw_data = Column(Text)

    works = relationship("OpenAlexWork", secondary=openalex_work_authors, back_populates="authors")
    institutions = relationship("OpenAlexInstitution", secondary=openalex_author_institutions, back_populates="authors")

    def __repr__(self):
        return f"<OpenAlexAuthor(display_name='{self.display_name}')>"

class OpenAlexVenue(IngestedAtMixin, Base):
    __tablename__ = 'openalex_venues'
    id = Column(Integer, primary_key=True, autoincrement=True)
    openalex_id = Column(String, unique=True, index=True)
    display_name = Column(String)
    publisher = Column(String)
    url = Column(String)
    raw_data = Column(Text)

    works = relationship("OpenAlexWork", back_populates="venue")

    def __repr__(self):
        return f"<OpenAlexVenue(display_name='{self.display_name}')>"

class OpenAlexInstitution(IngestedAtMixin, Base):
    __tablename__ = 'openalex_institutions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    openalex_id = Column(String, unique=True, index=True)
    display_name = Column(String)
    country_code = Column(String)
    url = Column(String)
    raw_data = Column(Text)

    authors = relationship("OpenAlexAuthor", secondary=openalex_author_institutions, back_populates="institutions")

    def __repr__(self):
        return f"<OpenAlexInstitution(display_name='{self.display_name}')>"

class OpenAlexTopic(IngestedAtMixin, Base):
    __tablename__ = 'openalex_topics'
    id = Column(Integer, primary_key=True, autoincrement=True)
    openalex_id = Column(String, unique=True, index=True)
    display_name = Column(String)
    description = Column(Text)
    domain_id = Column(String)
    domain_display_name = Column(String)
    field_id = Column(String)
    field_display_name = Column(String)
    subfield_id = Column(String)
    subfield_display_name = Column(String)
    updated_date = Column(DateTime)
    works_count = Column(Integer)
    keywords = Column(Text)  # Comma-separated keywords
    raw_data = Column(Text)
    
    works = relationship("OpenAlexWork", secondary=openalex_work_topics, back_populates="topics")

    def __repr__(self):
        return f"<OpenAlexTopic(display_name='{self.display_name}')>"
    
class RepositoryInstitutionAnalysis(IngestedAtMixin, Base):
    """Stores results from running Association Confidence Filters on repositories."""
    __tablename__ = 'repository_institution_analyses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, ForeignKey('repositories.id'), nullable=False)
    institution_name = Column(String, nullable=False, index=True)
    filter_name = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=False)
    evidence = Column(Text)  # JSON string
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    keywords_used = Column(Text)  # Comma-separated list of keywords that led to this repository
    
    # Relationships
    repository = relationship("Repository", backref="institution_analyses")
    
    def __repr__(self):
        return f"<RepositoryInstitutionAnalysis(repo={self.repository_id}, institution='{self.institution_name}', score={self.confidence_score:.2f})>"

class AnalysisSession(Base):
    """Tracks a complete institution analysis session."""
    __tablename__ = 'analysis_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, unique=True, nullable=False)  # UUID for the session
    institution_name = Column(String, nullable=False)
    analysis_type = Column(String, nullable=False)  # 'repository' or 'people'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String, default='initiated')  # 'initiated', 'surfacing', 'acf', 'analysis', 'completed'
    parameters = Column(Text)  # JSON string of parameters used
    
    # Relationships
    surfacing_results = relationship("SurfacingResult", back_populates="session")
    acf_results = relationship("ACFResult", back_populates="session")

class SurfacingResult(Base):
    """Stores results of a surfacing operation."""
    __tablename__ = 'surfacing_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('analysis_sessions.id'), nullable=False)
    algorithm = Column(String, nullable=False)
    parameters = Column(Text)  # JSON string of parameters used
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    result_count = Column(Integer, default=0)
    result_summary = Column(Text)  # JSON string summary of results
    
    # Relationships
    session = relationship("AnalysisSession", back_populates="surfacing_results")
    repositories = relationship("SurfacedRepository", back_populates="surfacing_result")
    people = relationship("SurfacedPerson", back_populates="surfacing_result")

class SurfacedRepository(Base):
    """A repository surfaced during institution analysis."""
    __tablename__ = 'surfaced_repositories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    surfacing_id = Column(Integer, ForeignKey('surfacing_results.id'), nullable=False)
    repository_id = Column(Integer, ForeignKey('repositories.id'), nullable=False)
    discovery_method = Column(String, nullable=False)
    discovery_details = Column(Text)
    surface_score = Column(Float, default=0.0)  # Initial relevance score
    
    # Relationships
    surfacing_result = relationship("SurfacingResult", back_populates="repositories")
    repository = relationship("Repository")

class SurfacedPerson(Base):
    """A person surfaced during institution analysis."""
    __tablename__ = 'surfaced_people'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    surfacing_id = Column(Integer, ForeignKey('surfacing_results.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    openalex_author_id = Column(Integer, ForeignKey('openalex_authors.id'), nullable=True)
    name = Column(String)
    email = Column(String)
    discovery_method = Column(String, nullable=False)
    discovery_details = Column(Text)
    surface_score = Column(Float, default=0.0)  # Initial relevance score
    
    # Relationships
    surfacing_result = relationship("SurfacingResult", back_populates="people")
    user = relationship("User")
    openalex_author = relationship("OpenAlexAuthor")

class ACFResult(Base):
    """Stores results of an ACF operation."""
    __tablename__ = 'acf_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('analysis_sessions.id'), nullable=False)
    surfacing_id = Column(Integer, ForeignKey('surfacing_results.id'), nullable=False)
    filter_name = Column(String, nullable=False)
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    parameters = Column(Text)  # JSON string of parameters used
    result_summary = Column(Text)  # JSON string summary of results
    
    # Relationships
    session = relationship("AnalysisSession", back_populates="acf_results")
    surfacing_result = relationship("SurfacingResult")
    repository_results = relationship("ACFRepositoryResult", back_populates="acf_result")
    people_results = relationship("ACFPersonResult", back_populates="acf_result")

class ACFRepositoryResult(Base):
    """ACF result for a specific repository."""
    __tablename__ = 'acf_repository_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    acf_id = Column(Integer, ForeignKey('acf_results.id'), nullable=False)
    repository_id = Column(Integer, ForeignKey('repositories.id'), nullable=False)
    confidence_score = Column(Float, default=0.0)
    evidence = Column(Text)  # JSON string of evidence
    
    # Relationships
    acf_result = relationship("ACFResult", back_populates="repository_results")
    repository = relationship("Repository")

class ACFPersonResult(Base):
    """ACF result for a specific person."""
    __tablename__ = 'acf_person_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    acf_id = Column(Integer, ForeignKey('acf_results.id'), nullable=False)
    surfaced_person_id = Column(Integer, ForeignKey('surfaced_people.id'), nullable=False)
    confidence_score = Column(Float, default=0.0)
    evidence = Column(Text)  # JSON string of evidence
    
    # Relationships
    acf_result = relationship("ACFResult", back_populates="people_results")
    surfaced_person = relationship("SurfacedPerson")