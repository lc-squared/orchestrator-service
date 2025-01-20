import os
import sys
import grpc
import asyncio
from concurrent import futures

sys.path.append('/app')

from proto.v1.orchestrator_pb2_grpc import OrchestratorServiceServicer, add_OrchestratorServiceServicer_to_server
from proto.v1.orchestrator_pb2 import ReceiveDocumentResponse, GetProcessStatusResponse

class OrchestratorService(OrchestratorServiceServicer):
    async def ReceiveDocument(self, request, context):
        return ReceiveDocumentResponse(
            process_id="1",
            status="RECEIVED"
        )

    async def GetProcessStatus(self, request, context):
        return GetProcessStatusResponse(
            process_id=request.process_id,
            status="RECEIVED"
        )

async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    add_OrchestratorServiceServicer_to_server(OrchestratorService(), server)
    server.add_insecure_port('[::]:50050')
    await server.start()
    print("Server started on port 50050")
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())