import grpc
from concurrent import futures
from SchedulingService.methods import SchedulingAPI
from SchedulingService import scheduling_service_pb2_grpc

server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
scheduling_service_pb2_grpc.add_SchedulingAPIServicer_to_server(SchedulingAPI(), server)
server.add_insecure_port('[::]:50050')
