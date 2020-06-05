# Scheduling Service

The service is responsible for planning and executing user tasks on fog devices. It handles all requests for access to fog computing resources, via the Cloudlets Service searches for equipment located nearby the user, and runs necessary applications in isolated containers.

It consists of 3 components:

- **SchedullingService** Python script
- **MongoDB** Database
- **DockerSwarmMaster** Master for container management



### Preparation of Docker Swarm

To start the Docker Swarm Master node a machine running Ubuntu 20.04 is required.

1. Go to the folder with this README.md file

2. Copy the necessary files to the remote host

   ```bash
   scp -r DockerSwarmMaster/ <username>@<host_ip>:/home/<username>/
   ```

3. Connect to a remote host via ssh

   ```bash
   ssh <username>@<host_ip>
   ```

4. Start installing the required components

   During the installation, you need to specify the IP address or domain name of the Docker Registry (see Images Service) in the following format `ip_address`:`port`

   ```bash
   sudo ~/Docker\ Swarm\ Master/install.sh
   ```

5. Add a user to the docker group

   ```bash
   sudo usermod -aG docker $USER && newgrp - docker
   ```


