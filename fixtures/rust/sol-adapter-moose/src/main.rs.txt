use sol_adapter_protocol::{
    ExecutePlanRequest, ExecutePlanRequestV02, ProtocolFailure, ValidatePlanRequest,
    ValidatePlanRequestV02, ADAPTER_PROTOCOL_VERSION, ADAPTER_PROTOCOL_VERSION_0_2,
};
use sol_adapter_transport::{
    decode_request, AdapterTransportMethod, JsonRpcResponse, RequestDisposition, StdioFrameDecoder,
    TransportRequest,
};
use sol_adaptor_moose::execution_v02::ExecutionEnvironment;
use sol_adaptor_moose::FoundationAdapter;
use std::io::{self, Read, Write};
use std::process;

fn main() {
    if let Err(error) = run() {
        eprintln!("adapter transport error: {error}");
        process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let adapter = FoundationAdapter;
    let execution = ExecutionEnvironment::from_environment();
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut input = stdin.lock();
    let mut output = stdout.lock();
    let mut decoder = StdioFrameDecoder::new();
    let mut buffer = [0_u8; 8192];

    loop {
        let count = input.read(&mut buffer).map_err(|error| error.to_string())?;
        if count == 0 {
            decoder.finish().map_err(|error| error.to_string())?;
            return Ok(());
        }

        for frame in decoder.push(&buffer[..count]) {
            let frame = frame.map_err(|error| error.to_string())?;
            if let Some(response) = handle_frame(&adapter, &execution, &frame)? {
                output
                    .write_all(&response)
                    .map_err(|error| error.to_string())?;
                output.flush().map_err(|error| error.to_string())?;
            }
        }
    }
}

fn handle_frame(
    adapter: &FoundationAdapter,
    execution: &ExecutionEnvironment,
    frame: &str,
) -> Result<Option<Vec<u8>>, String> {
    match decode_request(frame) {
        RequestDisposition::Dispatch(request) => Ok(Some(
            dispatch(adapter, execution, &request)?.to_stdio_frame(),
        )),
        RequestDisposition::Reject(response) => Ok(Some(response.to_stdio_frame())),
        RequestDisposition::IgnoreNotification => Ok(None),
    }
}

fn dispatch(
    adapter: &FoundationAdapter,
    execution: &ExecutionEnvironment,
    request: &TransportRequest,
) -> Result<JsonRpcResponse, String> {
    match request.method() {
        AdapterTransportMethod::DescribeAdapter => match adapter.describe_adapter() {
            Ok(description) => success_response(
                request,
                description
                    .to_canonical_json()
                    .map_err(|error| error.to_string())?,
            ),
            Err(failure) => failure_response(request, &failure),
        },
        AdapterTransportMethod::ValidatePlan => {
            let version = match request_protocol_version(request) {
                Ok(version) => version,
                Err(failure) => return failure_response(request, &failure),
            };
            match version {
                ADAPTER_PROTOCOL_VERSION => {
                    let result = parse_validate_request_v01(request)
                        .and_then(|request| adapter.validate_plan(&request));
                    protocol_result(request, result.map(|response| response.to_canonical_json()))
                }
                ADAPTER_PROTOCOL_VERSION_0_2 => {
                    let result = parse_validate_request_v02(request)
                        .and_then(|request| execution.validate_plan_v02(&request));
                    protocol_result(request, result.map(|response| response.to_canonical_json()))
                }
                other => failure_response(request, &unsupported_protocol_failure(other)),
            }
        }
        AdapterTransportMethod::ExecutePlan => {
            let version = match request_protocol_version(request) {
                Ok(version) => version,
                Err(failure) => return failure_response(request, &failure),
            };
            match version {
                ADAPTER_PROTOCOL_VERSION => {
                    let result = parse_execute_request_v01(request)
                        .and_then(|request| adapter.execute_plan(&request));
                    protocol_result(request, result.map(|response| response.to_canonical_json()))
                }
                ADAPTER_PROTOCOL_VERSION_0_2 => {
                    let result = parse_execute_request_v02(request)
                        .and_then(|request| execution.execute_plan_v02(&request));
                    protocol_result(request, result.map(|response| response.to_canonical_json()))
                }
                other => failure_response(request, &unsupported_protocol_failure(other)),
            }
        }
    }
}

fn protocol_result<E: ToString>(
    request: &TransportRequest,
    result: Result<Result<String, E>, ProtocolFailure>,
) -> Result<JsonRpcResponse, String> {
    match result {
        Ok(Ok(canonical)) => success_response(request, canonical),
        Ok(Err(error)) => failure_response(request, &invalid_request_failure(error)),
        Err(failure) => failure_response(request, &failure),
    }
}

fn request_protocol_version(request: &TransportRequest) -> Result<&str, ProtocolFailure> {
    let params = request
        .params()
        .expect("plan transport request always has params");
    params
        .get("adapter_protocol_version")
        .and_then(|value| value.as_str())
        .ok_or_else(|| {
            invalid_request_failure(
                "plan request requires string field `adapter_protocol_version` for explicit version dispatch",
            )
        })
}

fn parse_validate_request_v01(
    request: &TransportRequest,
) -> Result<ValidatePlanRequest, ProtocolFailure> {
    let json = params_json(request);
    ValidatePlanRequest::from_json(&json).map_err(invalid_request_failure)
}

fn parse_validate_request_v02(
    request: &TransportRequest,
) -> Result<ValidatePlanRequestV02, ProtocolFailure> {
    let json = params_json(request);
    ValidatePlanRequestV02::from_json(&json).map_err(invalid_request_failure)
}

fn parse_execute_request_v01(
    request: &TransportRequest,
) -> Result<ExecutePlanRequest, ProtocolFailure> {
    let json = params_json(request);
    ExecutePlanRequest::from_json(&json).map_err(invalid_request_failure)
}

fn parse_execute_request_v02(
    request: &TransportRequest,
) -> Result<ExecutePlanRequestV02, ProtocolFailure> {
    let json = params_json(request);
    ExecutePlanRequestV02::from_json(&json).map_err(invalid_request_failure)
}

fn params_json(request: &TransportRequest) -> String {
    let params = request
        .params()
        .expect("plan transport request always has params");
    serde_json::to_string(params).expect("JSON Value always serializes")
}

fn unsupported_protocol_failure(version: &str) -> ProtocolFailure {
    ProtocolFailure::unsupported_adapter_protocol(format!(
        "adapter does not support Adapter Protocol `{version}` for this request"
    ))
    .expect("static unsupported-protocol detail is valid")
}

fn invalid_request_failure(error: impl ToString) -> ProtocolFailure {
    ProtocolFailure::invalid_request(error.to_string())
        .expect("transport parse error detail produces a valid ProtocolFailure")
}

fn success_response(
    request: &TransportRequest,
    canonical_payload: String,
) -> Result<JsonRpcResponse, String> {
    let payload = serde_json::from_str(&canonical_payload).map_err(|error| error.to_string())?;
    JsonRpcResponse::protocol_success(request.id(), payload).map_err(|error| error.to_string())
}

fn failure_response(
    request: &TransportRequest,
    failure: &ProtocolFailure,
) -> Result<JsonRpcResponse, String> {
    JsonRpcResponse::protocol_failure(request.id(), request.method(), failure)
        .map_err(|error| error.to_string())
}
