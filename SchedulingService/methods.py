import os
import grpc
import docker
import pymongo
from SchedulingService import scheduling_service_pb2, scheduling_service_pb2_grpc


class SchedulingAPI(scheduling_service_pb2_grpc.SchedulingAPIServicer):
    mongo_client = pymongo.MongoClient('mongodb://scheduling_service:scheduling_service_pwd@SchedulingServiceDB:27017/scheduling_service')
    scheduling_service_db = mongo_client.scheduling_service
    clusters_collection = scheduling_service_db.clusters

    swarm_manager_url = os.environ.get('DOCKER_SWARM_MANAGER')
    registry_url = os.environ.get('DOCKER_REGISTRY_URL')
    docker_client = docker.DockerClient(base_url=swarm_manager_url)

    images_service_stub = scheduling_service_pb2_grpc.ImagesAPIStub(grpc.insecure_channel('ImagesService:50050'))  # gRPC stub to work with Images Service
    cloudlets_service_stub = scheduling_service_pb2_grpc.CloudletsAPIStub(grpc.insecure_channel('CloudletsService:50050'))  # gRPC stub to work with Cloudlets Service

    # Создает новый кластер IoT-устройств
    def CreateCluster(self, request, context):
        # Authorization in the Docker Registry to allow workers to access images of fog applications
        self.docker_client.login(username='scheduling_service', password='testing1', registry=self.registry_url)

        # Check the existence of the image of fog application
        images_service_response = self.images_service_stub.Find(scheduling_service_pb2.Image(name=request.image))
        if images_service_response.status.code != 200:
            status = scheduling_service_pb2.Response(code=images_service_response.status.code, message=images_service_response.status.message)
            return scheduling_service_pb2.ResponseWithCluster(status=status)

        # Searching for the nearest fog devices
        cloudlets_service_response = self.cloudlets_service_stub.FindNearest(scheduling_service_pb2.Cloudlet(latitude=request.coordinates.latitude,
                                                                                                             longitude=request.coordinates.longitude))
        if cloudlets_service_response.status.code != 200:
            status = scheduling_service_pb2.Response(code=cloudlets_service_response.status.code, message=cloudlets_service_response.status.message)
            return scheduling_service_pb2.ResponseWithCluster(status=status)
        nearest_cloudlets_id = []
        for cloudlet in cloudlets_service_response.cloudlets:
            nearest_cloudlets_id.append(cloudlet.id)

        endpoint_spec = {'Ports': []}
        # Define required ports for the fog application
        try:
            image_tag = request.image.split(':')
            self.docker_client.images.pull(self.registry_url + '/' + image_tag[0], tag='latest' if len(image_tag) == 1 else image_tag[1])
            image = self.docker_client.images.get(self.registry_url + '/' + request.image)
            container_config = image.attrs.get('ContainerConfig')
            if container_config.get('ExposedPorts'):
                for key, _ in container_config.get('ExposedPorts').items():
                    keys = key.split('/')
                    endpoint_spec['Ports'].append({'PublishedPort': None, 'TargetPort': int(keys[0]), 'Protocol': keys[1], 'PublishMode': 'host'})
        except docker.errors.APIError as error:
            status = scheduling_service_pb2.Response(code=500, message=str(error))
            return scheduling_service_pb2.ResponseWithCluster(status=status)
        except docker.errors.ImageNotFound:
            status = scheduling_service_pb2.Response(code=404, message='Image with this name not found.')
            return scheduling_service_pb2.ResponseWithCluster(status=status)

        # Creating a cluster of IoT devices (Swarm service)
        cluster = self.docker_client.services.create(endpoint_spec=endpoint_spec,
                                                     mode=docker.types.ServiceMode('replicated', replicas=0),
                                                     image=self.registry_url + '/' + request.image)
        try:
            # Writing cluster nodes in the database
            self.clusters_collection.update_one({'_id': cluster.attrs.get("ID")}, {'$set': {'cloudlets': nearest_cloudlets_id}}, upsert=True)

            # Labeling the nearest fog nodes
            for cloudlet_id in nearest_cloudlets_id:
                cloudlet_labels = self.docker_client.nodes.get(cloudlet_id).attrs.get('Spec').get('Labels')
                cloudlet_labels[cluster.attrs.get('ID')] = 'True'
                self.docker_client.nodes.get(cloudlet_id).update({'Availability': 'active', 'Labels': cloudlet_labels, 'Role': 'worker'})
            # Starting the cluster of IoT devices
            cluster.update(constraints=[f'node.labels.{cluster.attrs.get("ID")}==True'], mode=docker.types.ServiceMode('replicated', replicas=1))
        except Exception as error:
            cluster.remove()
            status = scheduling_service_pb2.Response(code=500, message='An internal server error occurred. ' + str(error))
            return scheduling_service_pb2.ResponseWithCluster(status=status)

        # Collecting information about the cluster of IoT devices
        cluster_task = cluster.tasks()[0]
        state = cluster_task.get('Status').get('State')

        status = scheduling_service_pb2.Response(code=201, message='Cluster of IoT devices has been created successfully.')
        return scheduling_service_pb2.ResponseWithCluster(status=status,
                                                          cluster=scheduling_service_pb2.Cluster(id=cluster.attrs.get("ID"), state=state))

    # Returns the cluster state of IoT devices
    def ClusterState(self, request, context):
        try:
            cluster = self.docker_client.services.get(request.id)
        except docker.errors.NotFound:
            status = scheduling_service_pb2.Response(code=404, message='IoT devices cluster with specified id not found.')
            return scheduling_service_pb2.ResponseWithCluster(status=status)
        except docker.errors.APIError or docker.errors.InvalidVersion as error:
            status = scheduling_service_pb2.Response(code=500, message='An internal server error occurred. ' + str(error))
            return scheduling_service_pb2.ResponseWithCluster(status=status)

        # Collecting information about the cluster of IoT devices
        cluster_task = cluster.tasks()[0]
        state = cluster_task.get('Status').get('State')
        port_status = cluster_task.get('Status').get('PortStatus')
        exposed_ports = []
        if len(port_status):
            for port in port_status.get('Ports'):
                exposed_ports.append(scheduling_service_pb2.ExposedPort(published_port=port.get('PublishedPort'),
                                                                        target_port=port.get('TargetPort'),
                                                                        protocol=port.get('Protocol')))
        worker_node = cluster_task.get('NodeID')
        cloudlet_ip = ''
        if worker_node:
            cloudlet_ip = self.docker_client.nodes.get(worker_node).attrs.get('Status').get('Addr')
        image = cluster_task.get('Spec').get('ContainerSpec').get('Image')[len(self.registry_url + '/'):]

        status = scheduling_service_pb2.Response(code=200, message='IoT devices cluster was found.')
        return scheduling_service_pb2.ResponseWithCluster(status=status,
                                                          cluster=scheduling_service_pb2.Cluster(id=cluster.attrs.get("ID"),
                                                                                                 image=image,
                                                                                                 cloudlet_ip=cloudlet_ip,
                                                                                                 state=state,
                                                                                                 exposed_ports=exposed_ports))

    # Removes an existing IoT device cluster
    def RemoveCluster(self, request, context):
        if not request.id:
            return scheduling_service_pb2.Response(code=422, message='Cluster id parameter is required.')

        # Removing the cluster of IoT devices
        try:
            cluster = self.docker_client.services.get(request.id)
            cluster.remove()
        except docker.errors.NotFound:
            return scheduling_service_pb2.Response(code=404, message='IoT devices cluster with specified id not found.')
        except docker.errors.APIError or docker.errors.InvalidVersion as error:
            return scheduling_service_pb2.Response(code=500, message='An internal server error occurred. ' + str(error))

        try:
            search = self.clusters_collection.find_one({'_id': request.id})
            if search:
                nearest_cloudlets = search.get('cloudlets')
                # Removing labels on fog nodes
                for cloudlet in nearest_cloudlets:
                    cloudlet_labels = self.docker_client.nodes.get(cloudlet).attrs.get('Spec').get('Labels')
                    cloudlet_labels.pop(request.id)
                    self.docker_client.nodes.get(cloudlet).update({'Availability': 'active', 'Labels': cloudlet_labels, 'Role': 'worker'})
            # Removing a record from the database
            self.clusters_collection.remove({'_id': request.id})
        except Exception as error:
            return scheduling_service_pb2.Response(code=500, message='An internal server error occurred. ' + str(error))

        return scheduling_service_pb2.Response(code=200, message='The IoT devices cluster has been removed.')

    # Returns the Docker Swarm Manager IP address and token to add a new worker
    def SwarmManager(self, request, context):
        manager = scheduling_service_pb2.Manager()
        try:
            manager.address = self.docker_client.info()['Swarm']['RemoteManagers'][0]['Addr']
            manager.join_worker_token = self.docker_client.swarm.attrs['JoinTokens']['Worker']
        except docker.errors.APIError as error:
            return scheduling_service_pb2.ResponseWithManager(status=scheduling_service_pb2.Response(code=500, message=str(error)))
        return scheduling_service_pb2.ResponseWithManager(status=scheduling_service_pb2.Response(code=200), manager=manager)
