use std::collections::BTreeSet;
use std::fmt::{Display, Formatter};

#[derive(Debug, Clone, PartialEq)]
pub struct MooseInputModel {
    pub mesh: GeneratedLineMesh,
    pub variables: Vec<ScalarVariable>,
    pub operators: Vec<MooseOperator>,
    pub materials: Vec<ConstantMaterialProperty>,
    pub boundary_conditions: Vec<DirichletBoundary>,
    pub executioner: Executioner,
    pub outputs: Outputs,
}

#[derive(Debug, Clone, PartialEq)]
pub struct GeneratedLineMesh {
    pub nx: u32,
    pub xmin: f64,
    pub xmax: f64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScalarVariable {
    pub name: String,
    pub order: VariableOrder,
    pub family: VariableFamily,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VariableOrder {
    First,
    Second,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VariableFamily {
    Lagrange,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MooseOperator {
    Diffusion {
        name: String,
        variable: String,
    },
    HeatConduction {
        name: String,
        variable: String,
        thermal_conductivity_property: String,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub struct ConstantMaterialProperty {
    pub name: String,
    pub property: String,
    pub value: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DirichletBoundary {
    pub name: String,
    pub variable: String,
    pub boundary: String,
    pub value: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Executioner {
    Steady,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Outputs {
    pub exodus: bool,
}

impl MooseInputModel {
    pub fn validate(&self) -> Result<(), IrError> {
        if self.mesh.nx == 0 {
            return Err(IrError::InvalidMesh(
                "nx must be greater than zero".to_owned(),
            ));
        }
        require_finite("mesh.xmin", self.mesh.xmin)?;
        require_finite("mesh.xmax", self.mesh.xmax)?;
        if self.mesh.xmax <= self.mesh.xmin {
            return Err(IrError::InvalidMesh(
                "xmax must be greater than xmin".to_owned(),
            ));
        }

        if self.variables.is_empty() {
            return Err(IrError::InvalidModel(
                "at least one scalar variable is required".to_owned(),
            ));
        }
        if self.operators.is_empty() {
            return Err(IrError::InvalidModel(
                "at least one operator is required".to_owned(),
            ));
        }

        let mut variable_names = BTreeSet::new();
        for variable in &self.variables {
            require_identifier("variable", &variable.name)?;
            if !variable_names.insert(variable.name.as_str()) {
                return Err(IrError::DuplicateName(variable.name.clone()));
            }
        }

        let mut material_names = BTreeSet::new();
        let mut properties = BTreeSet::new();
        for material in &self.materials {
            require_identifier("material", &material.name)?;
            require_identifier("material property", &material.property)?;
            require_finite("material value", material.value)?;
            if !material_names.insert(material.name.as_str()) {
                return Err(IrError::DuplicateName(material.name.clone()));
            }
            if !properties.insert(material.property.as_str()) {
                return Err(IrError::DuplicateProperty(material.property.clone()));
            }
        }

        let mut operator_names = BTreeSet::new();
        for operator in &self.operators {
            let (name, variable) = match operator {
                MooseOperator::Diffusion { name, variable } => (name, variable),
                MooseOperator::HeatConduction {
                    name,
                    variable,
                    thermal_conductivity_property,
                } => {
                    require_identifier(
                        "thermal conductivity property",
                        thermal_conductivity_property,
                    )?;
                    if !properties.contains(thermal_conductivity_property.as_str()) {
                        return Err(IrError::MissingMaterialProperty(
                            thermal_conductivity_property.clone(),
                        ));
                    }
                    (name, variable)
                }
            };
            require_identifier("operator", name)?;
            require_identifier("operator variable", variable)?;
            if !operator_names.insert(name.as_str()) {
                return Err(IrError::DuplicateName(name.clone()));
            }
            if !variable_names.contains(variable.as_str()) {
                return Err(IrError::UnknownVariable(variable.clone()));
            }
        }

        let mut bc_names = BTreeSet::new();
        for bc in &self.boundary_conditions {
            require_identifier("boundary condition", &bc.name)?;
            require_identifier("boundary variable", &bc.variable)?;
            require_identifier("boundary", &bc.boundary)?;
            require_finite("boundary value", bc.value)?;
            if !bc_names.insert(bc.name.as_str()) {
                return Err(IrError::DuplicateName(bc.name.clone()));
            }
            if !variable_names.contains(bc.variable.as_str()) {
                return Err(IrError::UnknownVariable(bc.variable.clone()));
            }
        }

        Ok(())
    }

    pub fn to_moose_input(&self) -> Result<String, IrError> {
        self.validate()?;

        let mut variables: Vec<_> = self.variables.iter().collect();
        variables.sort_by(|left, right| left.name.cmp(&right.name));
        let mut operators: Vec<_> = self.operators.iter().collect();
        operators.sort_by(|left, right| operator_name(left).cmp(operator_name(right)));
        let mut materials: Vec<_> = self.materials.iter().collect();
        materials.sort_by(|left, right| left.name.cmp(&right.name));
        let mut bcs: Vec<_> = self.boundary_conditions.iter().collect();
        bcs.sort_by(|left, right| left.name.cmp(&right.name));

        let mut output = String::new();
        output.push_str("# Adapter-local backend-only MOOSE IR. Not canonical SOL semantics.\n");
        output.push_str("[Mesh]\n");
        output.push_str("  type = GeneratedMesh\n");
        output.push_str("  dim = 1\n");
        output.push_str(&format!("  nx = {}\n", self.mesh.nx));
        output.push_str(&format!("  xmin = {}\n", format_real(self.mesh.xmin)?));
        output.push_str(&format!("  xmax = {}\n", format_real(self.mesh.xmax)?));
        output.push_str("[]\n\n");

        output.push_str("[Variables]\n");
        for variable in variables {
            output.push_str(&format!("  [{}]\n", variable.name));
            output.push_str(&format!("    order = {}\n", variable.order));
            output.push_str(&format!("    family = {}\n", variable.family));
            output.push_str("  []\n");
        }
        output.push_str("[]\n\n");

        output.push_str("[Kernels]\n");
        for operator in operators {
            match operator {
                MooseOperator::Diffusion { name, variable } => {
                    output.push_str(&format!("  [{name}]\n"));
                    output.push_str("    type = Diffusion\n");
                    output.push_str(&format!("    variable = {variable}\n"));
                    output.push_str("  []\n");
                }
                MooseOperator::HeatConduction {
                    name,
                    variable,
                    thermal_conductivity_property,
                } => {
                    output.push_str(&format!("  [{name}]\n"));
                    output.push_str("    type = HeatConduction\n");
                    output.push_str(&format!("    variable = {variable}\n"));
                    output.push_str(&format!(
                        "    thermal_conductivity = {thermal_conductivity_property}\n"
                    ));
                    output.push_str("  []\n");
                }
            }
        }
        output.push_str("[]\n\n");

        if !materials.is_empty() {
            output.push_str("[Materials]\n");
            for material in materials {
                output.push_str(&format!("  [{}]\n", material.name));
                output.push_str("    type = GenericConstantMaterial\n");
                output.push_str(&format!(
                    "    prop_names = {}\n",
                    quote_moose_string(&material.property)
                ));
                output.push_str(&format!(
                    "    prop_values = {}\n",
                    quote_moose_string(&format_real(material.value)?)
                ));
                output.push_str("  []\n");
            }
            output.push_str("[]\n\n");
        }

        output.push_str("[BCs]\n");
        for bc in bcs {
            output.push_str(&format!("  [{}]\n", bc.name));
            output.push_str("    type = DirichletBC\n");
            output.push_str(&format!("    variable = {}\n", bc.variable));
            output.push_str(&format!(
                "    boundary = {}\n",
                quote_moose_string(&bc.boundary)
            ));
            output.push_str(&format!("    value = {}\n", format_real(bc.value)?));
            output.push_str("  []\n");
        }
        output.push_str("[]\n\n");

        output.push_str("[Executioner]\n");
        match self.executioner {
            Executioner::Steady => output.push_str("  type = Steady\n"),
        }
        output.push_str("[]\n\n");

        output.push_str("[Outputs]\n");
        output.push_str(&format!(
            "  exodus = {}\n",
            if self.outputs.exodus { "true" } else { "false" }
        ));
        output.push_str("[]\n");

        Ok(output)
    }
}

fn operator_name(operator: &MooseOperator) -> &str {
    match operator {
        MooseOperator::Diffusion { name, .. } | MooseOperator::HeatConduction { name, .. } => name,
    }
}

fn require_identifier(label: &'static str, value: &str) -> Result<(), IrError> {
    if value.is_empty()
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-')
    {
        return Err(IrError::InvalidIdentifier {
            label,
            value: value.to_owned(),
        });
    }
    Ok(())
}

fn require_finite(label: &'static str, value: f64) -> Result<(), IrError> {
    if value.is_finite() {
        Ok(())
    } else {
        Err(IrError::NonFinite { label })
    }
}

fn format_real(value: f64) -> Result<String, IrError> {
    require_finite("numeric value", value)?;
    if value == 0.0 {
        Ok("0".to_owned())
    } else {
        Ok(value.to_string())
    }
}

fn quote_moose_string(value: &str) -> String {
    let escaped = value.replace('\\', "\\\\").replace('\'', "\\'");
    format!("'{escaped}'")
}

impl Display for VariableOrder {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::First => formatter.write_str("FIRST"),
            Self::Second => formatter.write_str("SECOND"),
        }
    }
}

impl Display for VariableFamily {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Lagrange => formatter.write_str("LAGRANGE"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IrError {
    InvalidMesh(String),
    InvalidModel(String),
    InvalidIdentifier { label: &'static str, value: String },
    DuplicateName(String),
    DuplicateProperty(String),
    UnknownVariable(String),
    MissingMaterialProperty(String),
    NonFinite { label: &'static str },
}

impl Display for IrError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidMesh(detail) => write!(formatter, "invalid mesh: {detail}"),
            Self::InvalidModel(detail) => write!(formatter, "invalid model: {detail}"),
            Self::InvalidIdentifier { label, value } => {
                write!(formatter, "invalid {label} identifier `{value}`")
            }
            Self::DuplicateName(name) => write!(formatter, "duplicate object name `{name}`"),
            Self::DuplicateProperty(property) => {
                write!(formatter, "duplicate material property `{property}`")
            }
            Self::UnknownVariable(variable) => write!(formatter, "unknown variable `{variable}`"),
            Self::MissingMaterialProperty(property) => {
                write!(formatter, "missing material property `{property}`")
            }
            Self::NonFinite { label } => write!(formatter, "{label} must be finite"),
        }
    }
}

impl std::error::Error for IrError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn real_format_normalizes_negative_zero() {
        assert_eq!(format_real(-0.0).unwrap(), "0");
    }

    #[test]
    fn moose_string_escaping_is_deterministic() {
        assert_eq!(quote_moose_string("a'b\\c"), "'a\\'b\\\\c'");
    }
}
