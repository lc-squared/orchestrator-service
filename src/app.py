# app.py
import asyncio
import traceback
import grpc
from concurrent import futures

from proto.v1.orchestrator_pb2 import (
    ReceiveDocumentResponse,
    GetProcessStatusResponse
)
from proto.v1.orchestrator_pb2_grpc import (
    OrchestratorServiceServicer,
    add_OrchestratorServiceServicer_to_server
)

from proto.v1.document_pb2 import (
    ProcessDocumentRequest,
    GetProcessedDocumentRequest
)
from proto.v1.document_pb2_grpc import DocumentServiceStub

from proto.v1.logic_pb2 import (
    AnalyzeDocumentRequest,
    GetAnalysisStatusRequest
)
from proto.v1.logic_pb2_grpc import LogicServiceStub


class OrchestratorService(OrchestratorServiceServicer):
    def __init__(self):
        self.processes = {}
        # If you're running all containers via Docker Compose:
        self.document_channel = grpc.aio.insecure_channel("document-service:50051")
        self.logic_channel = grpc.aio.insecure_channel("logic-service:50052")

        # If you’re running everything locally (not Docker), use:
        # self.document_channel = grpc.aio.insecure_channel("localhost:50051")
        # self.logic_channel = grpc.aio.insecure_channel("localhost:50052")

        self.document_client = DocumentServiceStub(self.document_channel)
        self.logic_client = LogicServiceStub(self.logic_channel)

    async def ReceiveDocument(self, request, context):
        """
        Called by the client/test to initiate a new process.
        Creates a process entry with status 'PROCESSING' 
        and schedules background processing of the doc.
        """
        process_id = f"process_{len(self.processes) + 1}"
        self.processes[process_id] = {
            'status': 'PROCESSING',
            'document_id': None,
            'analysis_id': None,
            'error': ''
        }

        # Launch background task
        asyncio.create_task(self.process_document(process_id, request))

        return ReceiveDocumentResponse(
            process_id=process_id,
            status="PROCESSING"
        )

    async def process_document(self, process_id, request):
        """
        The background task that calls DocumentService -> LogicService,
        then updates the status to 'COMPLETED' or 'ERROR'.
        """
        try:
            print(f"Processing document in background: {process_id}")

            # 1) Call DocumentService to process
            doc_resp = await self.document_client.ProcessDocument(
                ProcessDocumentRequest(
                    content=request.content,
                    filename=request.filename,
                    content_type=request.content_type,
                    metadata=request.metadata
                )
            )
            document_id = doc_resp.document_id
            self.processes[process_id]['document_id'] = document_id

            # 2) Get processed doc
            processed_doc = await self.document_client.GetProcessedDocument(
                GetProcessedDocumentRequest(
                    document_id=document_id
                )
            )

            # 3) Call LogicService to analyze
            logic_resp = await self.logic_client.AnalyzeDocument(
                AnalyzeDocumentRequest(
                    document_id=document_id,
                    processed_content=processed_doc.processed_content,
                    document_metadata=processed_doc.extracted_metadata
                )
            )
            analysis_id = logic_resp.analysis_id
            self.processes[process_id]['analysis_id'] = analysis_id

            # Done successfully
            self.processes[process_id]['status'] = 'COMPLETED'
            print(f"Process {process_id} completed successfully!")

        except Exception as e:
            print("Error in process_document:", str(e))
            traceback.print_exc()
            self.processes[process_id]['status'] = 'ERROR'
            self.processes[process_id]['error'] = str(e)

    async def GetProcessStatus(self, request, context):
        """
        Return the process status and optionally logic results if COMPLETED.
        """
        process = self.processes.get(request.process_id)
        if not process:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Process not found")
            return GetProcessStatusResponse()

        resp = GetProcessStatusResponse(
            process_id=request.process_id,
            status=process['status'],
        )

        if process['status'] == 'COMPLETED':
            # Query the logic service for final analysis results:
            logic_status = await self.logic_client.GetAnalysisStatus(
                GetAnalysisStatusRequest(
                    analysis_id=process['analysis_id']
                )
            )

            # Fill the logic results into the response
            resp.results.logic_results.update(logic_status.results)

            # If you'd like to store doc metadata in self.processes, 
            # you can also do something like:
            # doc_meta = ...
            # resp.results.document_metadata.update(doc_meta)

        elif process['status'] == 'ERROR':
            resp.error_message = process.get('error', 'Unknown error')

        return resp


async def serve():
    """
    Start the gRPC server (on port 50050 by default).
    """
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    add_OrchestratorServiceServicer_to_server(OrchestratorService(), server)
    server.add_insecure_port('[::]:50050')
    print("Orchestrator Service starting on port 50050...")
    await server.start()
    await server.wait_for_termination()


if __name__ == '__main__':
    asyncio.run(serve())
