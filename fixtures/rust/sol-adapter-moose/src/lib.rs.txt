#![forbid(unsafe_code)]

pub mod backend;
pub mod execution_v02;
pub mod ir;
pub mod realization_v02;

use crate::execution_v02::{MOOSE_TARGET, THERMAL_CAPABILITY_V02};
use sol_adapter_protocol::{
    protocol_diagnostic, ActionExecutionReport, ActionExecutionState, AdapterBootstrap,
    AdapterDescription, AdapterProtocolDiagnosticContext, CapabilityDeclaration,
    ExecutePlanRequest, ExecutePlanResponse, ExecutionOutcome, PreflightOutcome, ProtocolFailure,
    ProtocolOperation, SideEffectEvidence, TargetDeclaration, ValidatePlanRequest,
    ValidatePlanResponse, ADAPTER_PROTOCOL_VERSION, ADAPTER_PROTOCOL_VERSION_0_2,
    DIAGNOSTIC_EXECUTION_REJECTED, DIAGNOSTIC_MISSING_CAPABILITY, DIAGNOSTIC_TARGET_MISMATCH,
};
use sol_public_contract::{Diagnostic, PUBLIC_CONTRACT_VERSION, PUBLIC_CONTRACT_VERSION_0_2};

/// Backward-compatible 0.1 adapter surface plus the explicitly proven Realization 0.2 target.
///
/// The 0.1 validate/execute methods remain intentionally non-realizing because Protocol 0.1
/// carries no RealizationSpec. Phase 4 adds the separate authoritative Protocol 0.2 runtime in
/// `execution_v02`; the shared description advertises both frozen 0.1 support and the explicit
/// 0.2 realization boundary required by the SOL M0.8 handoff.
#[derive(Debug, Clone, Copy, Default)]
pub struct FoundationAdapter;

impl FoundationAdapter {
    pub fn describe_adapter(&self) -> Result<AdapterDescription, ProtocolFailure> {
        let description = AdapterDescription {
            bootstrap: AdapterBootstrap {
                adapter_id: "sol.adapter.moose".to_owned(),
                adapter_version: env!("CARGO_PKG_VERSION").to_owned(),
                supported_adapter_protocol_versions: Some(vec![
                    ADAPTER_PROTOCOL_VERSION.to_owned(),
                    ADAPTER_PROTOCOL_VERSION_0_2.to_owned(),
                ]),
                supported_public_contract_versions: Some(vec![
                    PUBLIC_CONTRACT_VERSION.to_owned(),
                    PUBLIC_CONTRACT_VERSION_0_2.to_owned(),
                ]),
                extensions: Default::default(),
            },
            targets: vec![TargetDeclaration {
                target: MOOSE_TARGET.to_owned(),
                capabilities: vec![CapabilityDeclaration {
                    capability: THERMAL_CAPABILITY_V02.to_owned(),
                    revision: None,
                    extensions: Default::default(),
                }],
                extensions: Default::default(),
            }],
            extensions: Default::default(),
        };

        let canonical = description.to_canonical_json().map_err(|error| {
            operation_failure(
                ProtocolOperation::DescribeAdapter,
                error,
                SideEffectEvidence::None,
            )
        })?;
        AdapterDescription::from_json(&canonical).map_err(|error| {
            operation_failure(
                ProtocolOperation::DescribeAdapter,
                error,
                SideEffectEvidence::None,
            )
        })
    }

    pub fn validate_plan(
        &self,
        request: &ValidatePlanRequest,
    ) -> Result<ValidatePlanResponse, ProtocolFailure> {
        let canonical = request.to_canonical_json().map_err(|error| {
            ProtocolFailure::invalid_request(error.to_string())
                .expect("non-blank request error produces ProtocolFailure")
        })?;
        let request = ValidatePlanRequest::from_json(&canonical).map_err(|error| {
            ProtocolFailure::invalid_request(error.to_string())
                .expect("non-blank request error produces ProtocolFailure")
        })?;

        let diagnostics = vec![
            protocol_diagnostic(
                DIAGNOSTIC_TARGET_MISMATCH,
                "Protocol 0.1 has no canonical realization payload; use the explicit 0.2 RealizationSpec boundary for MOOSE thermal realization",
                AdapterProtocolDiagnosticContext {
                    target: Some(request.target.target.clone()),
                    ..Default::default()
                },
            ),
            protocol_diagnostic(
                DIAGNOSTIC_MISSING_CAPABILITY,
                "canonical MOOSE thermal realization is operational only through Adapter Protocol 0.2 + Public Contract 0.2",
                AdapterProtocolDiagnosticContext::default(),
            ),
        ]
        .into_iter()
        .collect::<Result<Vec<_>, _>>()
        .map_err(|error| {
            operation_failure(
                ProtocolOperation::ValidatePlan,
                error,
                SideEffectEvidence::None,
            )
        })?;

        ValidatePlanResponse::new(false, false, PreflightOutcome::Rejected, diagnostics).map_err(
            |error| {
                operation_failure(
                    ProtocolOperation::ValidatePlan,
                    error,
                    SideEffectEvidence::None,
                )
            },
        )
    }

    pub fn execute_plan(
        &self,
        request: &ExecutePlanRequest,
    ) -> Result<ExecutePlanResponse, ProtocolFailure> {
        let canonical = request.to_canonical_json().map_err(|error| {
            ProtocolFailure::invalid_request(error.to_string())
                .expect("non-blank request error produces ProtocolFailure")
        })?;
        let request = ExecutePlanRequest::from_json(&canonical).map_err(|error| {
            ProtocolFailure::invalid_request(error.to_string())
                .expect("non-blank request error produces ProtocolFailure")
        })?;

        if request.plan.actions.is_empty() {
            return Err(
                ProtocolFailure::compatibility_not_established(
                    "Protocol 0.1 carries no RealizationSpec and the empty plan has no action reports for a rejected execution response",
                )
                .expect("static compatibility detail is valid"),
            );
        }

        let mut response = ExecutePlanResponse {
            adapter_protocol_version: ADAPTER_PROTOCOL_VERSION.to_owned(),
            execution: ExecutionOutcome::Rejected,
            execution_batches: Vec::new(),
            action_reports: request
                .plan
                .actions
                .iter()
                .map(|action| ActionExecutionReport {
                    action_id: action.id.clone(),
                    state: ActionExecutionState::NotStarted,
                    effects: Vec::new(),
                    diagnostics: Vec::new(),
                    provenance: None,
                    extensions: Default::default(),
                })
                .collect(),
            effects: Vec::new(),
            diagnostics: vec![Diagnostic::error(
                DIAGNOSTIC_EXECUTION_REJECTED,
                None,
                "authoritative MOOSE realization requires Adapter Protocol 0.2 + Public Contract 0.2 RealizationSpec",
            )],
            provenance: None,
            extensions: Default::default(),
        };

        response.validate_against(&request).map_err(|error| {
            operation_failure(
                ProtocolOperation::ExecutePlan,
                error,
                SideEffectEvidence::None,
            )
        })?;
        Ok(response)
    }
}

fn operation_failure(
    operation: ProtocolOperation,
    error: impl ToString,
    side_effects: SideEffectEvidence,
) -> ProtocolFailure {
    let failure = ProtocolFailure::operational(error.to_string(), side_effects)
        .expect("adapter error detail is non-blank");
    failure
        .validate_for(operation)
        .expect("side-effect evidence is valid for operation");
    failure
}

#[cfg(test)]
mod tests {
    use super::FoundationAdapter;
    use sol_adapter_protocol::{
        ActionExecutionState, ExecutePlanRequest, ExecutionOutcome, PreflightOutcome,
        ValidatePlanRequest, ADAPTER_PROTOCOL_VERSION, ADAPTER_PROTOCOL_VERSION_0_2,
    };
    use sol_public_contract::{PUBLIC_CONTRACT_VERSION, PUBLIC_CONTRACT_VERSION_0_2};

    const REQUEST_BODY: &str = r#"{
        "adapter_protocol_version":"0.1",
        "target":{
            "public_contract_version":"0.1",
            "target":"moose",
            "required_capabilities":["thermal.solve"]
        },
        "plan":{
            "public_contract_version":"0.1",
            "actions":[{"id":"opaque.action","dependencies":[]}]
        }
    }"#;

    #[test]
    fn description_declares_frozen_v01_and_explicit_v02_target_support() {
        let description = FoundationAdapter.describe_adapter().unwrap();
        assert_eq!(
            description.bootstrap.supported_adapter_protocol_versions,
            Some(vec![
                ADAPTER_PROTOCOL_VERSION.to_owned(),
                ADAPTER_PROTOCOL_VERSION_0_2.to_owned()
            ])
        );
        assert_eq!(
            description.bootstrap.supported_public_contract_versions,
            Some(vec![
                PUBLIC_CONTRACT_VERSION.to_owned(),
                PUBLIC_CONTRACT_VERSION_0_2.to_owned()
            ])
        );
        assert_eq!(description.targets.len(), 1);
        assert_eq!(description.targets[0].target, "moose");
        assert_eq!(description.targets[0].capabilities.len(), 1);
        assert_eq!(
            description.targets[0].capabilities[0].capability,
            "thermal.steady_conduction"
        );
    }

    #[test]
    fn v01_preflight_remains_rejected_without_realization_spec_semantics() {
        let request = ValidatePlanRequest::from_json(REQUEST_BODY).unwrap();
        let response = FoundationAdapter.validate_plan(&request).unwrap();
        assert!(!response.target_compatible);
        assert!(!response.capabilities_satisfied);
        assert_eq!(response.preflight, PreflightOutcome::Rejected);
        assert_eq!(response.diagnostics.len(), 2);
    }

    #[test]
    fn v01_execute_remains_rejected_before_side_effects() {
        let request = ExecutePlanRequest::from_json(REQUEST_BODY).unwrap();
        let response = FoundationAdapter.execute_plan(&request).unwrap();
        assert_eq!(response.execution, ExecutionOutcome::Rejected);
        assert!(response.execution_batches.is_empty());
        assert!(response.effects.is_empty());
        assert_eq!(response.action_reports.len(), 1);
        assert_eq!(
            response.action_reports[0].state,
            ActionExecutionState::NotStarted
        );
    }
}
