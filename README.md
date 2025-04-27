
## Local set up
### Install fnm (Fast Node Manager)
[fnm](https://github.com/Schniz/fnm)

### Install Node
```bash
fnm install 23
fnm use 23
```

### Install Bun
[Bun](https://bun.sh/docs/installation)

### Use Bun to install dependencies
```bash
bun install
```

### Update .env with Github API key
[Generate Github API](https://github.com/settings/personal-access-tokens)
[Github API Docs](https://docs.github.com/en)

### Start local application
```bash
bun dev run
```

## Current functionality overview
1. Bottom right, show DB status, connect to db
2. In Data Worker, enter a github user login, Add task
3. refresh queue
4. execute task
5. In View, click refresh users to see the fretched data
6. click fetch repos to get all repos of this user

- DataView, back and forth between users, their repos, and collaborators thereof spawns a bigraph

- Graph View

- Schema Manager, other file formats