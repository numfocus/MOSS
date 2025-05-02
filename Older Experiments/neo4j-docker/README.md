# Deploy neo4j locally using Docker

1. Make sure Docker is installed: https://docs.docker.com/engine/install/
2. Create a file called '.env' in your 'neo4j-docker' directory
   - See [neo4j-docker/env-example](), feel free to change the password
3. Navigate to your neo4j-docker directory and deploy the container using:
   ```
   docker compose up -d
   ```
   > Notes: 
   > - The '-d' argument tells Docker to run the containers detached (as a daemon) and is optional.
   > - You may need to use sudo if you have not configured your user to be in the docker group.
   > - Also, if you find yourself doing this over and over trying to get the password right, make sure to delete the folder created by docker between runs ;)